#!/usr/bin/env python3
"""
Claude Usage Data Collector
Parses ~/.claude/ local data and outputs structured JSON for the Plasma widget.
Runs periodically via systemd timer or called directly.
"""

import json
import os
import glob
import sys
import urllib.request
import urllib.error
import http.cookiejar
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

CLAUDE_DIR = Path.home() / ".claude"
OUTPUT_FILE = CLAUDE_DIR / "widget-data.json"
STATUS_CACHE_FILE = CLAUDE_DIR / "widget-status-prev.json"
CONFIG_FILE = CLAUDE_DIR / "widget-config.json"

# Anthropic pricing (per 1M tokens) — May 2025 public prices
PRICING = {
    "claude-opus-4-6":            {"input": 15.00, "output": 75.00, "cache_read": 1.50,  "cache_create": 18.75},
    "claude-sonnet-4-6":          {"input":  3.00, "output": 15.00, "cache_read": 0.30,  "cache_create":  3.75},
    "claude-sonnet-4-5-20250929": {"input":  3.00, "output": 15.00, "cache_read": 0.30,  "cache_create":  3.75},
    "claude-haiku-4-5-20251001":  {"input":  0.80, "output":  4.00, "cache_read": 0.08,  "cache_create":  1.00},
}

MODEL_DISPLAY = {
    "claude-opus-4-6":            "Opus",
    "claude-sonnet-4-6":          "Sonnet",
    "claude-sonnet-4-5-20250929": "Sonnet 4.5",
    "claude-haiku-4-5-20251001":  "Haiku",
}

MODEL_COLORS = {
    "Opus":       "#D97706",
    "Sonnet":     "#2563EB",
    "Sonnet 4.5": "#6366F1",
    "Haiku":      "#10B981",
}

# Statuspage.io component IDs → short display names
COMPONENT_SHORT_NAMES = {
    "rwppv331jlwc": "claude.ai",
    "0qbwn08sd68x": "Platform",
    "k8w3r06qmzrp": "API",
    "yyzkbfz2thpt": "Claude Code",
    "bpp5gb3hpjcl": "Cowork",
    "0scnb50nvy53": "Gov",
}


def calculate_cost(model, input_t, output_t, cache_read_t, cache_create_t):
    """Calculate cost in USD for a given model and token counts."""
    p = PRICING.get(model)
    if not p:
        return 0.0
    return (
        (input_t / 1_000_000) * p["input"]
        + (output_t / 1_000_000) * p["output"]
        + (cache_read_t / 1_000_000) * p["cache_read"]
        + (cache_create_t / 1_000_000) * p["cache_create"]
    )


def load_stats_cache():
    """Load the stats-cache.json file."""
    path = CLAUDE_DIR / "stats-cache.json"
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def parse_timestamp(ts):
    """Parse a timestamp value (int ms, float, or ISO-8601 string) to datetime."""
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts, tz=timezone.utc)
    elif isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def parse_sessions_in_window(cutoff_utc, end_utc=None):
    """Parse JSONL session files for records within a time window.

    Returns: (model_tokens, sessions_list, message_count, sonnet_only_tokens)
    """
    if end_utc is None:
        end_utc = datetime.now(timezone.utc)

    model_tokens = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_create": 0
    })
    sonnet_tokens = defaultdict(lambda: {
        "input": 0, "output": 0, "cache_read": 0, "cache_create": 0
    })
    sessions = []
    session_set = set()
    total_messages = 0

    # Skip files not modified recently (optimization)
    mtime_cutoff = (cutoff_utc - timedelta(hours=1)).timestamp()

    projects_dir = CLAUDE_DIR / "projects"
    if not projects_dir.exists():
        return model_tokens, sessions, total_messages, sonnet_tokens

    for jsonl_file in projects_dir.rglob("*.jsonl"):
        # Skip old files
        try:
            if jsonl_file.stat().st_mtime < mtime_cutoff:
                continue
        except OSError:
            continue

        is_subagent = "subagents" in str(jsonl_file)
        project_name = jsonl_file.parts[-2] if not is_subagent else jsonl_file.parts[-3]
        if project_name.startswith("-"):
            project_name = project_name[1:].replace("-", "/")

        try:
            with open(jsonl_file) as f:
                session_has_window = False
                session_messages = 0
                session_start = None

                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    rec_type = record.get("type", "")
                    msg = record.get("message", {})

                    # Parse timestamp
                    ts = record.get("timestamp")
                    rec_date = parse_timestamp(ts) if ts else None
                    if not rec_date:
                        continue

                    # Check if within window
                    if rec_date < cutoff_utc or rec_date > end_utc:
                        continue

                    if session_start is None:
                        session_start = rec_date
                    session_has_window = True

                    # Count messages
                    if rec_type in ("user", "assistant") or msg.get("role") in ("user", "assistant"):
                        session_messages += 1
                        if msg.get("role") == "assistant":
                            total_messages += 1

                    # Extract token usage
                    usage = msg.get("usage", {})
                    model = msg.get("model", "")
                    if usage and model:
                        inp = usage.get("input_tokens", 0)
                        out = usage.get("output_tokens", 0)
                        cr = usage.get("cache_read_input_tokens", 0)
                        cc = usage.get("cache_creation_input_tokens", 0)

                        model_tokens[model]["input"] += inp
                        model_tokens[model]["output"] += out
                        model_tokens[model]["cache_read"] += cr
                        model_tokens[model]["cache_create"] += cc

                        # Track Sonnet-only usage
                        if "sonnet" in model.lower():
                            sonnet_tokens[model]["input"] += inp
                            sonnet_tokens[model]["output"] += out
                            sonnet_tokens[model]["cache_read"] += cr
                            sonnet_tokens[model]["cache_create"] += cc

                if session_has_window and not is_subagent:
                    sid = jsonl_file.stem
                    if sid not in session_set:
                        session_set.add(sid)
                        sessions.append({
                            "id": sid[:8],
                            "project": project_name,
                            "messages": session_messages,
                            "start": session_start.isoformat() if session_start else "",
                        })

        except (PermissionError, OSError):
            continue

    return dict(model_tokens), sessions, total_messages, dict(sonnet_tokens)


def compute_window_cost(model_tokens):
    """Compute total cost from model token dict."""
    total = 0.0
    for model, t in model_tokens.items():
        total += calculate_cost(model, t["input"], t["output"], t["cache_read"], t["cache_create"])
    return total


def compute_window_output_tokens(model_tokens):
    """Sum output tokens across all models (primary rate limit metric)."""
    return sum(t["output"] for t in model_tokens.values())


def get_claude_cookies():
    """Extract all claude.ai cookies from Firefox for API auth."""
    import sqlite3
    import shutil
    firefox_dir = Path.home() / ".mozilla" / "firefox"
    if not firefox_dir.exists():
        return ""
    for profile in firefox_dir.iterdir():
        cookie_db = profile / "cookies.sqlite"
        if cookie_db.exists():
            try:
                tmp_db = Path("/tmp/claude_cookies.sqlite")
                shutil.copy2(cookie_db, tmp_db)
                conn = sqlite3.connect(str(tmp_db))
                cursor = conn.execute(
                    "SELECT name, value FROM moz_cookies WHERE host LIKE '%claude.ai%'"
                )
                pairs = [f"{name}={value}" for name, value in cursor.fetchall()]
                conn.close()
                tmp_db.unlink(missing_ok=True)
                if pairs:
                    return "; ".join(pairs)
            except Exception:
                continue
    return ""


def load_config():
    """Load widget config from ~/.claude/widget-config.json."""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass
    return {}


def save_config(cfg):
    """Persist widget config."""
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2))
    except Exception:
        pass


def detect_org_id(cookies):
    """Auto-detect org_id from lastActiveOrg cookie or /api/organizations."""
    # 1. Try lastActiveOrg cookie (fastest)
    for pair in cookies.split(";"):
        pair = pair.strip()
        if pair.startswith("lastActiveOrg="):
            val = pair.split("=", 1)[1].strip()
            if len(val) > 10:
                return val

    # 2. Fallback: query /api/organizations
    try:
        req = urllib.request.Request("https://claude.ai/api/organizations")
        req.add_header("Cookie", cookies)
        req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0")
        req.add_header("anthropic-client-platform", "web_claude_ai")
        with urllib.request.urlopen(req, timeout=10) as resp:
            orgs = json.loads(resp.read().decode())
            if orgs and isinstance(orgs, list):
                return orgs[0].get("uuid") or orgs[0].get("id", "")
    except Exception:
        pass
    return ""


def get_org_id(cookies=""):
    """Return org_id from config, or detect and save it."""
    cfg = load_config()
    org_id = cfg.get("org_id", "")
    if org_id:
        return org_id

    if not cookies:
        cookies = get_claude_cookies()
    org_id = detect_org_id(cookies)
    if org_id:
        cfg["org_id"] = org_id
        save_config(cfg)
    return org_id


def _api_request(path):
    """Make an authenticated request to claude.ai API."""
    cookies = get_claude_cookies()
    if not cookies:
        return None

    org_id = get_org_id(cookies)
    if not org_id:
        return None

    url = f"https://claude.ai/api/organizations/{org_id}/{path}"
    req = urllib.request.Request(url)
    req.add_header("Cookie", cookies)
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0")
    req.add_header("anthropic-client-platform", "web_claude_ai")
    req.add_header("anthropic-client-version", "1.0.0")

    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return json.loads(resp.read().decode())
    except Exception:
        return None


def fetch_usage_from_api():
    """Fetch usage/utilization data with five_hour, seven_day, etc."""
    return _api_request("usage")


def fetch_credits_from_api():
    """Fetch prepaid credits balance."""
    return _api_request("prepaid/credits")


def fetch_overage_data():
    """Fetch extra usage (overage) spend limit and credit grant."""
    spend_limit = _api_request("overage_spend_limit")
    credit_grant = _api_request("overage_credit_grant")
    if not spend_limit and not credit_grant:
        return None
    result = {}
    if spend_limit:
        currency = spend_limit.get("currency", "USD")
        result["enabled"] = spend_limit.get("is_enabled", False)
        result["monthlyLimit"] = spend_limit.get("monthly_credit_limit", 0) / 100
        result["usedCredits"] = spend_limit.get("used_credits", 0) / 100
        result["currency"] = currency
        result["disabledReason"] = spend_limit.get("disabled_reason", "")
        result["outOfCredits"] = spend_limit.get("out_of_credits", False)
    if credit_grant:
        result["grantAvailable"] = credit_grant.get("available", False)
        result["grantAmount"] = credit_grant.get("amount_minor_units", 0) / 100
        result["grantCurrency"] = credit_grant.get("currency", "USD")
    return result


def fetch_service_status():
    """Fetch Claude service health from status.claude.com (Statuspage.io API)."""
    try:
        req = urllib.request.Request("https://status.claude.com/api/v2/summary.json")
        req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return None

    # Showcase components only (the main ones)
    components = []
    for c in data.get("components", []):
        if c.get("showcase", False):
            components.append({
                "id": c["id"],
                "name": COMPONENT_SHORT_NAMES.get(c["id"], c["name"].split(" ")[0]),
                "status": c["status"],
            })

    # Active (non-resolved) incidents
    active_incidents = []
    for inc in data.get("incidents", []):
        if inc.get("resolved_at") is None:
            updates = inc.get("incident_updates", [])
            latest_body = updates[0].get("body", "") if updates else ""
            active_incidents.append({
                "name": inc["name"],
                "status": inc["status"],
                "impact": inc.get("impact", ""),
                "latest_update": latest_body,
                "started_at": inc.get("started_at", ""),
                "url": inc.get("shortlink", ""),
            })

    overall = data.get("status", {})
    return {
        "indicator": overall.get("indicator", "none"),
        "description": overall.get("description", "All Systems Operational"),
        "updated_at": data.get("page", {}).get("updated_at", ""),
        "components": components,
        "active_incidents": active_incidents,
    }


def notify_status_change(new_status):
    """Send KDE desktop notification when Claude service status changes."""
    if new_status is None:
        return

    new_indicator = new_status.get("indicator", "none")
    prev_indicator = "none"

    if STATUS_CACHE_FILE.exists():
        try:
            prev = json.loads(STATUS_CACHE_FILE.read_text())
            prev_indicator = prev.get("indicator", "none")
        except Exception:
            pass

    # Save current state
    try:
        STATUS_CACHE_FILE.write_text(json.dumps({"indicator": new_indicator}))
    except Exception:
        pass

    # Only notify on change
    if new_indicator == prev_indicator:
        return

    import subprocess

    if new_indicator == "none":
        title = "Claude Status"
        body = "All Systems Operational"
        urgency = "normal"
    else:
        title = "Claude Status Alert"
        incidents = new_status.get("active_incidents", [])
        body = incidents[0]["name"] if incidents else new_status.get("description", "Service issue detected")
        urgency = "critical" if new_indicator in ("major", "critical") else "normal"

    try:
        subprocess.run(
            ["notify-send", "--urgency", urgency, "--icon", "claude-logo",
             "--app-name", "Claude Status", title, body],
            check=False, timeout=5
        )
    except Exception:
        pass


def detect_adaptive_thinking():
    """Check Claude Code settings for adaptive thinking / 1M context."""
    settings_file = CLAUDE_DIR / "settings.json"
    result = {"adaptive_thinking": True, "context_1m": True}
    if settings_file.exists():
        try:
            settings = json.loads(settings_file.read_text())
            env = settings.get("env", {})
            result["adaptive_thinking"] = env.get("CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING", "0") != "1"
            result["context_1m"] = env.get("CLAUDE_CODE_DISABLE_1M_CONTEXT", "0") != "1"
        except Exception:
            pass
    return result


def calculate_error_rate(hours=2):
    """Count API errors in recent JSONL files (429, 529, overloaded, etc.)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    mtime_cutoff = (cutoff - timedelta(hours=1)).timestamp()
    errors = {"rate_limit": 0, "overloaded": 0, "server_error": 0, "other": 0, "total": 0}

    projects_dir = CLAUDE_DIR / "projects"
    if not projects_dir.exists():
        return errors

    for jsonl_file in projects_dir.rglob("*.jsonl"):
        try:
            if jsonl_file.stat().st_mtime < mtime_cutoff:
                continue
        except OSError:
            continue
        try:
            with open(jsonl_file) as f:
                for line in f:
                    if '"api_error"' not in line and '"error"' not in line:
                        continue
                    try:
                        record = json.loads(line.strip())
                    except json.JSONDecodeError:
                        continue
                    ts = record.get("timestamp")
                    rec_date = parse_timestamp(ts) if ts else None
                    if not rec_date or rec_date < cutoff:
                        continue
                    if record.get("subtype") != "api_error" and record.get("type") != "system":
                        continue
                    err = record.get("error", {})
                    status = err.get("status", 0)
                    nested = err.get("error", {}).get("error", {})
                    err_type = str(nested.get("type", ""))

                    errors["total"] += 1
                    if status == 429 or "rate_limit" in err_type:
                        errors["rate_limit"] += 1
                    elif status == 529 or "overloaded" in err_type:
                        errors["overloaded"] += 1
                    elif status >= 500:
                        errors["server_error"] += 1
                    else:
                        errors["other"] += 1
        except (PermissionError, OSError):
            continue
    return errors


def calculate_burn_rate():
    """Token consumption rate (tokens/hour) for rolling 2h window."""
    now = datetime.now(timezone.utc)
    two_h = now - timedelta(hours=2)
    tokens, _, _, _ = parse_sessions_in_window(two_h, now)
    total_output = sum(t["output"] for t in tokens.values())
    total_all = sum(
        t["input"] + t["output"] + t["cache_read"] + t["cache_create"]
        for t in tokens.values()
    )
    return {
        "output_per_hour": round(total_output / 2),
        "total_per_hour": round(total_all / 2),
    }


def compute_dumbness_score(service_status, session_pct, error_rate, adaptive_config):
    """Composite 'dumbness' score: 0 (genius) to 100 (braindead).

    Combines: service health + rate limit pressure + API errors + config issues.
    """
    score = 0
    reasons = []

    # Service health (0-40 pts)
    if service_status:
        ind = service_status.get("indicator", "none")
        if ind == "critical":
            score += 40; reasons.append("Critical outage")
        elif ind == "major":
            score += 30; reasons.append("Major outage")
        elif ind == "minor":
            score += 15; reasons.append("Degraded service")

    # Session utilization pressure (0-25 pts)
    if session_pct > 90:
        score += 25; reasons.append("Session >90%")
    elif session_pct > 80:
        score += 15; reasons.append("Session >80%")
    elif session_pct > 60:
        score += 5

    # Recent API errors (0-20 pts)
    total_err = error_rate.get("total", 0)
    if total_err > 10:
        score += 20; reasons.append(f"{total_err} errors/2h")
    elif total_err > 3:
        score += 10; reasons.append(f"{total_err} errors/2h")
    elif total_err > 0:
        score += 5

    # Adaptive thinking: ON is worse (causes lazy responses)
    if adaptive_config.get("adaptive_thinking", True):
        score += 8; reasons.append("Adaptive thinking ON (lazy responses)")
    if not adaptive_config.get("context_1m", True):
        score += 3; reasons.append("1M context OFF")

    score = min(100, score)
    if score < 10:
        level = "genius"
    elif score < 25:
        level = "smart"
    elif score < 50:
        level = "slow"
    elif score < 75:
        level = "dumb"
    else:
        level = "braindead"

    return {"score": score, "level": level, "reasons": reasons}


def calculate_latency(hours=2):
    """Average response latency (seconds) from user→assistant timestamp gaps."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    mtime_cutoff = (cutoff - timedelta(hours=1)).timestamp()
    gaps = []

    projects_dir = CLAUDE_DIR / "projects"
    if not projects_dir.exists():
        return {"avgSeconds": 0, "sampleSize": 0}

    for jsonl_file in projects_dir.rglob("*.jsonl"):
        if "subagents" in str(jsonl_file):
            continue
        try:
            if jsonl_file.stat().st_mtime < mtime_cutoff:
                continue
        except OSError:
            continue
        try:
            last_user_ts = None
            with open(jsonl_file) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = record.get("timestamp")
                    rec_date = parse_timestamp(ts) if ts else None
                    if not rec_date or rec_date < cutoff:
                        last_user_ts = None
                        continue
                    role = record.get("message", {}).get("role", "") or record.get("type", "")
                    if role == "user":
                        last_user_ts = rec_date
                    elif role == "assistant" and last_user_ts:
                        delta = (rec_date - last_user_ts).total_seconds()
                        if 0.5 < delta < 300:  # reasonable range
                            gaps.append(delta)
                        last_user_ts = None
                    if len(gaps) >= 50:
                        break
        except (PermissionError, OSError):
            continue
        if len(gaps) >= 50:
            break

    avg = round(sum(gaps) / len(gaps), 1) if gaps else 0
    return {"avgSeconds": avg, "sampleSize": len(gaps)}


def calculate_streak():
    """Count consecutive days with Claude usage ending today."""
    stats = load_stats_cache()
    active_dates = set()
    if stats:
        for d in stats.get("dailyActivity", []):
            if d.get("sessionCount", 0) > 0:
                active_dates.add(d["date"])

    today = datetime.now().strftime("%Y-%m-%d")
    # Today might not be in stats-cache yet, check if we have sessions
    # (caller will pass today_has_sessions flag)
    return active_dates, today


def _compute_streak(active_dates, today, today_has_sessions):
    """Walk backwards counting consecutive active days."""
    if today_has_sessions:
        active_dates.add(today)
    streak = 0
    d = datetime.now()
    for _ in range(365):
        date_str = d.strftime("%Y-%m-%d")
        if date_str in active_dates:
            streak += 1
        else:
            break
        d -= timedelta(days=1)
    return {"days": streak, "includesToday": today_has_sessions}


def predict_limit_eta(session_pct, reset_minutes):
    """Predict when session limit will hit 100% at current rate."""
    if session_pct <= 0 or session_pct >= 100:
        return None
    elapsed = (5 * 60) - reset_minutes  # minutes into the 5h window
    if elapsed <= 5:
        return None  # not enough data
    rate_per_min = session_pct / elapsed
    if rate_per_min <= 0:
        return None
    minutes_to_100 = int((100 - session_pct) / rate_per_min)
    if minutes_to_100 > 600:
        return None  # too far away to be useful
    if minutes_to_100 >= 60:
        label = f"~{minutes_to_100 // 60}h {minutes_to_100 % 60}m"
    else:
        label = f"~{minutes_to_100}m"
    return {"minutesToLimit": minutes_to_100, "label": label}


def get_claude_code_version():
    """Get installed Claude Code version."""
    import subprocess as _sp
    try:
        r = _sp.run(["claude", "--version"], capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip().split("\n")[0].strip()
    except Exception:
        pass
    return ""


def build_rate_limits():
    """Fetch rate limits from Claude.ai API (real data).

    Falls back to local estimates if API is unavailable.
    """
    now = datetime.now(timezone.utc)

    # Try real API first
    api_data = fetch_usage_from_api()
    credits_data = fetch_credits_from_api()

    if api_data:
        five_hour = api_data.get("five_hour", {})
        seven_day = api_data.get("seven_day", {})
        seven_day_sonnet = api_data.get("seven_day_sonnet", {})

        # Calculate reset time
        resets_at = five_hour.get("resets_at", "")
        reset_minutes = 0
        if resets_at:
            try:
                reset_dt = datetime.fromisoformat(resets_at)
                delta = reset_dt - now
                reset_minutes = max(0, int(delta.total_seconds() / 60))
            except ValueError:
                pass

        # Weekly all models reset
        weekly_resets_at = seven_day.get("resets_at", "")
        weekly_reset_label = ""
        if weekly_resets_at:
            try:
                wr_dt = datetime.fromisoformat(weekly_resets_at)
                weekly_reset_label = wr_dt.strftime("%a %I:%M %p")
            except ValueError:
                pass

        # Weekly Sonnet reset
        sonnet_resets_at = (seven_day_sonnet or {}).get("resets_at", "")
        sonnet_reset_label = ""
        if sonnet_resets_at:
            try:
                sr_dt = datetime.fromisoformat(sonnet_resets_at)
                sonnet_reset_label = sr_dt.strftime("%a %I:%M %p")
            except ValueError:
                pass

        result = {
            "session": {
                "percentUsed": five_hour.get("utilization", 0),
                "resetsInMinutes": reset_minutes,
                "windowHours": 5,
            },
            "weeklyAll": {
                "percentUsed": seven_day.get("utilization", 0),
                "resetsLabel": weekly_reset_label,
            },
            "weeklySonnet": {
                "percentUsed": (seven_day_sonnet or {}).get("utilization", 0),
                "resetsLabel": sonnet_reset_label,
            },
            "plan": "Max (20x)",
            "source": "api",
        }

        # Add credits info (full details)
        if credits_data:
            amount = credits_data.get("amount", 0)
            currency = credits_data.get("currency", "USD")
            auto_reload = credits_data.get("auto_reload_settings")
            pending = credits_data.get("pending_invoice_amount_cents")
            result["credits"] = {
                "amount": amount / 100,
                "currency": currency,
                "autoReload": auto_reload is not None,
                "autoReloadSettings": auto_reload,
                "pendingInvoice": (pending / 100) if pending else 0,
            }

        # Extra usage / overage
        overage = fetch_overage_data()
        if overage:
            result["extraUsage"] = overage

        return result

    # Fallback: estimate from local data
    five_h_cutoff = now - timedelta(hours=5)
    five_h_tokens, _, _, _ = parse_sessions_in_window(five_h_cutoff, now)
    five_h_output = compute_window_output_tokens(five_h_tokens)

    week_cutoff = now - timedelta(days=7)
    week_tokens, _, _, week_sonnet = parse_sessions_in_window(week_cutoff, now)
    week_output = compute_window_output_tokens(week_tokens)
    week_sonnet_output = compute_window_output_tokens(week_sonnet)

    SESSION_LIMIT = 4_000_000
    WEEKLY_ALL_LIMIT = 40_000_000
    WEEKLY_SONNET_LIMIT = 80_000_000

    return {
        "session": {
            "percentUsed": round(min(100, five_h_output / SESSION_LIMIT * 100), 1),
            "resetsInMinutes": 300,
            "windowHours": 5,
        },
        "weeklyAll": {
            "percentUsed": round(min(100, week_output / WEEKLY_ALL_LIMIT * 100), 1),
            "resetsLabel": "",
        },
        "weeklySonnet": {
            "percentUsed": round(min(100, week_sonnet_output / WEEKLY_SONNET_LIMIT * 100), 1),
            "resetsLabel": "",
        },
        "plan": "Max (20x)",
        "source": "local_estimate",
    }


def build_widget_data():
    """Build the complete widget data JSON."""
    stats = load_stats_cache()
    now = datetime.now(timezone.utc)

    # Today's data (midnight UTC to now)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_tokens, today_sessions, today_msg_count, _ = parse_sessions_in_window(today_start, now)

    # Rate limits
    rate_limits = build_rate_limits()

    # Service health from status.claude.com
    service_status = fetch_service_status()
    notify_status_change(service_status)

    # New metrics
    error_rate = calculate_error_rate()
    burn_rate = calculate_burn_rate()
    adaptive_config = detect_adaptive_thinking()
    session_pct = rate_limits.get("session", {}).get("percentUsed", 0)
    reset_mins = rate_limits.get("session", {}).get("resetsInMinutes", 0)
    dumbness = compute_dumbness_score(service_status, session_pct, error_rate, adaptive_config)
    latency = calculate_latency()
    active_dates, today_str = calculate_streak()
    limit_eta = predict_limit_eta(session_pct, reset_mins)
    cc_version = get_claude_code_version()

    # Today's summary
    today_total_input = 0
    today_total_output = 0
    today_total_cache_read = 0
    today_total_cache_create = 0
    today_total_cost = 0.0
    model_breakdown = []

    for model, tokens in today_tokens.items():
        display = MODEL_DISPLAY.get(model, model.split("-")[1].title() if "-" in model else model)
        color = MODEL_COLORS.get(display, "#9CA3AF")
        cost = calculate_cost(model, tokens["input"], tokens["output"], tokens["cache_read"], tokens["cache_create"])
        total_tokens = tokens["input"] + tokens["output"] + tokens["cache_read"] + tokens["cache_create"]

        today_total_input += tokens["input"]
        today_total_output += tokens["output"]
        today_total_cache_read += tokens["cache_read"]
        today_total_cache_create += tokens["cache_create"]
        today_total_cost += cost

        model_breakdown.append({
            "model": display,
            "color": color,
            "input": tokens["input"],
            "output": tokens["output"],
            "cacheRead": tokens["cache_read"],
            "cacheCreate": tokens["cache_create"],
            "totalTokens": total_tokens,
            "cost": round(cost, 4),
        })

    # Sort by cost descending
    model_breakdown.sort(key=lambda x: x["cost"], reverse=True)

    # Calculate percentages
    grand_total_tokens = sum(m["totalTokens"] for m in model_breakdown)
    for m in model_breakdown:
        m["percentage"] = round((m["totalTokens"] / grand_total_tokens * 100) if grand_total_tokens > 0 else 0, 1)

    # 7-day trend from stats-cache
    trend_7d = []
    if stats:
        daily_tokens = {d["date"]: d["tokensByModel"] for d in stats.get("dailyModelTokens", [])}
        daily_activity = {d["date"]: d for d in stats.get("dailyActivity", [])}

        for i in range(7, -1, -1):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            day_label = (datetime.now() - timedelta(days=i)).strftime("%a")
            tokens_by_model = daily_tokens.get(day, {})
            total = sum(tokens_by_model.values())
            activity = daily_activity.get(day, {})
            trend_7d.append({
                "date": day,
                "label": day_label,
                "tokens": total,
                "messages": activity.get("messageCount", 0),
                "sessions": activity.get("sessionCount", 0),
            })

    # Lifetime stats
    lifetime = {}
    if stats:
        lifetime = {
            "totalSessions": stats.get("totalSessions", 0),
            "totalMessages": stats.get("totalMessages", 0),
            "firstSession": stats.get("firstSessionDate", ""),
            "longestSession": stats.get("longestSession", {}),
            "peakHours": stats.get("hourCounts", {}),
        }

        lifetime_cost = 0.0
        model_usage = stats.get("modelUsage", {})
        for model, usage in model_usage.items():
            lifetime_cost += calculate_cost(
                model,
                usage.get("inputTokens", 0),
                usage.get("outputTokens", 0),
                usage.get("cacheReadInputTokens", 0),
                usage.get("cacheCreationInputTokens", 0),
            )
        lifetime["totalCostUSD"] = round(lifetime_cost, 2)

        total_lt = sum(
            u.get("inputTokens", 0) + u.get("outputTokens", 0)
            + u.get("cacheReadInputTokens", 0) + u.get("cacheCreationInputTokens", 0)
            for u in model_usage.values()
        )
        lifetime["totalTokens"] = total_lt

    # Cache efficiency
    cache_total = today_total_cache_read + today_total_cache_create + today_total_input
    cache_hit_rate = (today_total_cache_read / cache_total * 100) if cache_total > 0 else 0

    widget_data = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "rateLimits": rate_limits,
        "today": {
            "inputTokens": today_total_input,
            "outputTokens": today_total_output,
            "cacheReadTokens": today_total_cache_read,
            "cacheCreateTokens": today_total_cache_create,
            "totalTokens": today_total_input + today_total_output + today_total_cache_read + today_total_cache_create,
            "costUSD": round(today_total_cost, 4),
            "messages": today_msg_count,
            "sessions": len(today_sessions),
            "cacheHitRate": round(cache_hit_rate, 1),
        },
        "modelBreakdown": model_breakdown,
        "sessions": sorted(today_sessions, key=lambda s: s.get("start", ""), reverse=True)[:10],
        "trend7d": trend_7d,
        "lifetime": lifetime,
        "serviceStatus": service_status,
        "errorRate": error_rate,
        "burnRate": burn_rate,
        "adaptiveThinking": adaptive_config,
        "dumbness": dumbness,
        "latency": latency,
        "responseQuality": {
            "avgTokensPerResponse": round(today_total_output / today_msg_count) if today_msg_count > 0 else 0,
            "totalResponses": today_msg_count,
        },
        "streak": _compute_streak(active_dates, today_str, len(today_sessions) > 0),
        "limitEta": limit_eta,
        "claudeCodeVersion": cc_version,
    }

    return widget_data


TEST_STATES = {
    "genius":    {"score": 5,  "level": "genius",    "reasons": []},
    "smart":     {"score": 15, "level": "smart",     "reasons": ["Adaptive thinking OFF"]},
    "slow":      {"score": 35, "level": "slow",      "reasons": ["Degraded service", "3 errors/2h"]},
    "dumb":      {"score": 60, "level": "dumb",      "reasons": ["Degraded service", "Session >80%", "5 errors/2h"]},
    "braindead": {"score": 85, "level": "braindead",  "reasons": ["Critical outage", "Session >90%", "12 errors/2h", "Adaptive thinking OFF"]},
}


def main():
    try:
        data = build_widget_data()

        # --test-state override for HITL testing
        for arg in sys.argv:
            if arg.startswith("--test-state="):
                state = arg.split("=", 1)[1]
                if state in TEST_STATES:
                    data["dumbness"] = TEST_STATES[state]
                    if state in ("slow", "dumb", "braindead"):
                        data["serviceStatus"]["indicator"] = "minor" if state == "slow" else "major"
                        data["rateLimits"]["session"]["percentUsed"] = 65 if state == "slow" else 84 if state == "dumb" else 95
                        data["errorRate"]["total"] = 3 if state == "slow" else 5 if state == "dumb" else 12

        # Atomic write
        tmp_path = str(OUTPUT_FILE) + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, OUTPUT_FILE)
        if "--verbose" in sys.argv:
            print(json.dumps(data, indent=2))
        else:
            cost = data["today"]["costUSD"]
            tokens = data["today"]["totalTokens"]
            sessions = data["today"]["sessions"]
            state_str = ""
            for arg in sys.argv:
                if arg.startswith("--test-state="):
                    state_str = f" [SIM: {arg.split('=')[1]}]"
            print(f"OK: ${cost:.2f} | {tokens:,} tokens | {sessions} sessions{state_str}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
