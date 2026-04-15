#!/usr/bin/env python3
"""
Claude Usage Data Collector for KDE Plasma Widget
Fetches real-time usage limits from claude.ai API and local Claude Code data.
"""

import json
import os
import sys
import urllib.request
import sqlite3
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import defaultdict

CLAUDE_DIR = Path.home() / ".claude"
CONFIG_FILE = CLAUDE_DIR / "widget-config.json"
OUTPUT_FILE = CLAUDE_DIR / "widget-data.json"

PRICING = {
    "claude-opus-4-6":            {"input": 15.00, "output": 75.00, "cache_read": 1.50,  "cache_create": 18.75},
    "claude-sonnet-4-6":          {"input":  3.00, "output": 15.00, "cache_read": 0.30,  "cache_create":  3.75},
    "claude-sonnet-4-5-20250929": {"input":  3.00, "output": 15.00, "cache_read": 0.30,  "cache_create":  3.75},
    "claude-haiku-4-5-20251001":  {"input":  0.80, "output":  4.00, "cache_read": 0.08,  "cache_create":  1.00},
}

MODEL_DISPLAY = {
    "claude-opus-4-6": "Opus", "claude-sonnet-4-6": "Sonnet",
    "claude-sonnet-4-5-20250929": "Sonnet 4.5", "claude-haiku-4-5-20251001": "Haiku",
}

MODEL_COLORS = {
    "Opus": "#D97706", "Sonnet": "#2563EB", "Sonnet 4.5": "#6366F1", "Haiku": "#10B981",
}


# ─── Config ───

def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ─── Cookie extraction (Firefox + Chromium) ───

def get_claude_cookies():
    """Extract claude.ai cookies from the user's browser."""
    cookies = _try_firefox_cookies()
    if cookies:
        return cookies
    cookies = _try_chromium_cookies()
    return cookies or ""

def _try_firefox_cookies():
    firefox_dir = Path.home() / ".mozilla" / "firefox"
    if not firefox_dir.exists():
        return ""
    for profile in sorted(firefox_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        cookie_db = profile / "cookies.sqlite"
        if not cookie_db.exists():
            continue
        try:
            tmp = Path("/tmp/.claude-widget-cookies.sqlite")
            shutil.copy2(cookie_db, tmp)
            conn = sqlite3.connect(str(tmp))
            rows = conn.execute("SELECT name, value FROM moz_cookies WHERE host LIKE '%claude.ai%'").fetchall()
            conn.close()
            tmp.unlink(missing_ok=True)
            if rows:
                return "; ".join(f"{n}={v}" for n, v in rows)
        except Exception:
            continue
    return ""

def _try_chromium_cookies():
    """Best-effort Chromium cookie read (unencrypted only — Linux often encrypts)."""
    for browser_dir in ["google-chrome", "chromium", "BraveSoftware/Brave-Browser"]:
        cookie_db = Path.home() / ".config" / browser_dir / "Default" / "Cookies"
        if not cookie_db.exists():
            continue
        try:
            tmp = Path("/tmp/.claude-widget-chromium-cookies.sqlite")
            shutil.copy2(cookie_db, tmp)
            conn = sqlite3.connect(str(tmp))
            rows = conn.execute(
                "SELECT name, value FROM cookies WHERE host_key LIKE '%claude.ai%' AND value != ''"
            ).fetchall()
            conn.close()
            tmp.unlink(missing_ok=True)
            if rows:
                return "; ".join(f"{n}={v}" for n, v in rows)
        except Exception:
            continue
    return ""


# ─── Org ID auto-detection ───

def detect_org_id(cookies):
    """Auto-detect organization ID from claude.ai API."""
    cfg = load_config()
    if cfg.get("org_id"):
        return cfg["org_id"]

    # Try to find in cookies (lastActiveOrg cookie)
    for part in cookies.split(";"):
        part = part.strip()
        if part.startswith("lastActiveOrg="):
            org_id = part.split("=", 1)[1]
            cfg["org_id"] = org_id
            save_config(cfg)
            return org_id

    # Try API
    try:
        req = urllib.request.Request("https://claude.ai/api/organizations")
        req.add_header("Cookie", cookies)
        req.add_header("Content-Type", "application/json")
        req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64; rv:145.0) Gecko/20100101 Firefox/145.0")
        resp = urllib.request.urlopen(req, timeout=10)
        orgs = json.loads(resp.read().decode())
        if orgs and len(orgs) > 0:
            org_id = orgs[0].get("uuid", "")
            if org_id:
                cfg["org_id"] = org_id
                save_config(cfg)
                return org_id
    except Exception:
        pass

    return None


# ─── API requests ───

def _api_get(cookies, org_id, path):
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


# ─── Plan detection ───

def detect_plan(cookies, org_id):
    """Detect the user's plan from credentials or API."""
    # Check Claude Code credentials
    creds_file = CLAUDE_DIR / ".credentials.json"
    if creds_file.exists():
        try:
            with open(creds_file) as f:
                creds = json.load(f)
            oauth = creds.get("claudeAiOauth", {})
            sub = oauth.get("subscriptionType", "")
            tier = oauth.get("rateLimitTier", "")
            if sub and tier:
                multiplier = ""
                if "20x" in tier:
                    multiplier = " (20x)"
                elif "5x" in tier:
                    multiplier = " (5x)"
                return f"{sub.title()}{multiplier}"
        except Exception:
            pass
    return "Pro"


# ─── Local JSONL parsing ───

def parse_timestamp(ts):
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts, tz=timezone.utc)
    elif isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None

def calculate_cost(model, inp, out, cr, cc):
    p = PRICING.get(model)
    if not p:
        return 0.0
    return (inp/1e6)*p["input"] + (out/1e6)*p["output"] + (cr/1e6)*p["cache_read"] + (cc/1e6)*p["cache_create"]

def load_stats_cache():
    path = CLAUDE_DIR / "stats-cache.json"
    return json.load(open(path)) if path.exists() else None

def parse_sessions_in_window(cutoff, end=None):
    if end is None:
        end = datetime.now(timezone.utc)
    model_tokens = defaultdict(lambda: {"input": 0, "output": 0, "cache_read": 0, "cache_create": 0})
    sessions, session_set, total_msgs = [], set(), 0
    mtime_cutoff = (cutoff - timedelta(hours=1)).timestamp()
    projects = CLAUDE_DIR / "projects"
    if not projects.exists():
        return dict(model_tokens), sessions, total_msgs

    for jf in projects.rglob("*.jsonl"):
        try:
            if jf.stat().st_mtime < mtime_cutoff:
                continue
        except OSError:
            continue
        is_sub = "subagents" in str(jf)
        proj = jf.parts[-2] if not is_sub else jf.parts[-3]
        if proj.startswith("-"):
            proj = proj[1:].replace("-", "/")
        try:
            with open(jf) as f:
                has_window, msgs, start = False, 0, None
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = parse_timestamp(rec.get("timestamp"))
                    if not ts or ts < cutoff or ts > end:
                        continue
                    if start is None:
                        start = ts
                    has_window = True
                    rt = rec.get("type", "")
                    msg = rec.get("message", {})
                    if rt in ("user", "assistant") or msg.get("role") in ("user", "assistant"):
                        msgs += 1
                        if msg.get("role") == "assistant":
                            total_msgs += 1
                    usage = msg.get("usage", {})
                    model = msg.get("model", "")
                    if usage and model:
                        model_tokens[model]["input"] += usage.get("input_tokens", 0)
                        model_tokens[model]["output"] += usage.get("output_tokens", 0)
                        model_tokens[model]["cache_read"] += usage.get("cache_read_input_tokens", 0)
                        model_tokens[model]["cache_create"] += usage.get("cache_creation_input_tokens", 0)
                if has_window and not is_sub and jf.stem not in session_set:
                    session_set.add(jf.stem)
                    sessions.append({"id": jf.stem[:8], "project": proj, "messages": msgs,
                                     "start": start.isoformat() if start else ""})
        except (PermissionError, OSError):
            continue
    return dict(model_tokens), sessions, total_msgs


# ─── Rate limits ───

def build_rate_limits(cookies, org_id, plan_name):
    now = datetime.now(timezone.utc)

    if cookies and org_id:
        api = _api_get(cookies, org_id, "usage")
        credits = _api_get(cookies, org_id, "prepaid/credits")

        if api:
            fh = api.get("five_hour", {})
            sd = api.get("seven_day", {})
            ss = api.get("seven_day_sonnet") or {}

            def reset_mins(iso):
                try:
                    return max(0, int((datetime.fromisoformat(iso) - now).total_seconds() / 60))
                except Exception:
                    return 0

            def reset_label(iso):
                try:
                    return datetime.fromisoformat(iso).strftime("%a %I:%M %p")
                except Exception:
                    return ""

            result = {
                "session": {"percentUsed": fh.get("utilization", 0),
                            "resetsInMinutes": reset_mins(fh.get("resets_at", "")), "windowHours": 5},
                "weeklyAll": {"percentUsed": sd.get("utilization", 0),
                              "resetsLabel": reset_label(sd.get("resets_at", ""))},
                "weeklySonnet": {"percentUsed": ss.get("utilization", 0),
                                 "resetsLabel": reset_label(ss.get("resets_at", ""))},
                "plan": plan_name, "source": "api",
            }
            if credits:
                amt = credits.get("amount", 0)
                cur = credits.get("currency", "USD")
                result["credits"] = {"amount": amt / 100, "currency": cur}
            return result

    # Fallback: local estimate
    fh_t, _, _ = parse_sessions_in_window(now - timedelta(hours=5), now)
    wk_t, _, _ = parse_sessions_in_window(now - timedelta(days=7), now)
    fh_out = sum(t["output"] for t in fh_t.values())
    wk_out = sum(t["output"] for t in wk_t.values())
    return {
        "session": {"percentUsed": round(min(100, fh_out / 4e6 * 100), 1), "resetsInMinutes": 300, "windowHours": 5},
        "weeklyAll": {"percentUsed": round(min(100, wk_out / 40e6 * 100), 1), "resetsLabel": ""},
        "weeklySonnet": {"percentUsed": 0, "resetsLabel": ""},
        "plan": plan_name, "source": "local_estimate",
    }


# ─── Main builder ───

def build_widget_data():
    stats = load_stats_cache()
    now = datetime.now(timezone.utc)

    # Auth
    cookies = get_claude_cookies()
    org_id = detect_org_id(cookies) if cookies else None
    plan = detect_plan(cookies, org_id) if org_id else "Unknown"

    # Rate limits (API or fallback)
    rate_limits = build_rate_limits(cookies, org_id, plan)

    # Today's local data
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_tokens, today_sessions, today_msgs = parse_sessions_in_window(today_start, now)

    model_breakdown = []
    for model, t in today_tokens.items():
        display = MODEL_DISPLAY.get(model, model.split("-")[1].title() if "-" in model else model)
        color = MODEL_COLORS.get(display, "#9CA3AF")
        cost = calculate_cost(model, t["input"], t["output"], t["cache_read"], t["cache_create"])
        total = t["input"] + t["output"] + t["cache_read"] + t["cache_create"]
        model_breakdown.append({"model": display, "color": color, "totalTokens": total, "cost": round(cost, 4)})
    model_breakdown.sort(key=lambda x: x["cost"], reverse=True)
    grand = sum(m["totalTokens"] for m in model_breakdown)
    for m in model_breakdown:
        m["percentage"] = round((m["totalTokens"] / grand * 100) if grand > 0 else 0, 1)

    # 7-day trend
    trend_7d = []
    if stats:
        dt = {d["date"]: d["tokensByModel"] for d in stats.get("dailyModelTokens", [])}
        da = {d["date"]: d for d in stats.get("dailyActivity", [])}
        for i in range(7, -1, -1):
            day = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            trend_7d.append({"date": day, "label": (datetime.now() - timedelta(days=i)).strftime("%a"),
                             "tokens": sum(dt.get(day, {}).values()),
                             "messages": da.get(day, {}).get("messageCount", 0)})

    # Lifetime
    lifetime = {}
    if stats:
        lifetime = {"totalSessions": stats.get("totalSessions", 0),
                     "totalMessages": stats.get("totalMessages", 0),
                     "firstSession": stats.get("firstSessionDate", "")}

    return {"generatedAt": now.isoformat(), "rateLimits": rate_limits,
            "today": {"sessions": len(today_sessions), "messages": today_msgs},
            "modelBreakdown": model_breakdown, "trend7d": trend_7d, "lifetime": lifetime}


def setup():
    """Interactive first-time setup."""
    print("═══ Claude Usage Widget Setup ═══\n")
    print("This widget needs access to your claude.ai session to fetch usage data.")
    print("It reads cookies from your browser (Firefox/Chrome) automatically.\n")

    cookies = get_claude_cookies()
    if not cookies:
        print("ERROR: No claude.ai cookies found in Firefox or Chrome.")
        print("Please log in to https://claude.ai in your browser first, then re-run setup.")
        sys.exit(1)

    print("✓ Found claude.ai session cookies")
    org_id = detect_org_id(cookies)
    if not org_id:
        print("ERROR: Could not detect organization ID.")
        print("Please visit https://claude.ai/settings and re-run setup.")
        sys.exit(1)

    print(f"✓ Organization ID: {org_id}")
    plan = detect_plan(cookies, org_id)
    print(f"✓ Plan: {plan}")

    usage = _api_get(cookies, org_id, "usage")
    if usage:
        print(f"✓ API connection working (session: {usage.get('five_hour', {}).get('utilization', '?')}% used)")
    else:
        print("⚠ API returned no data — will use local estimates")

    save_config({"org_id": org_id, "setup_done": True})
    print("\n✓ Setup complete! Config saved to ~/.claude/widget-config.json")


def main():
    if "--setup" in sys.argv:
        setup()
        return

    try:
        data = build_widget_data()
        tmp = str(OUTPUT_FILE) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, OUTPUT_FILE)
        if "--verbose" in sys.argv:
            print(json.dumps(data, indent=2))
        else:
            src = data["rateLimits"].get("source", "?")
            pct = data["rateLimits"]["session"]["percentUsed"]
            print(f"OK: {pct}% session | source={src}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
