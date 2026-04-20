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
import ctypes
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


def _get_chrome_key_windows():
    """Get Chrome cookie decryption key on Windows.

    Chrome 80+ stores AES-256-GCM key in Local State, encrypted with DPAPI.
    Returns raw key bytes or None.
    """
    try:
        import base64
        local_state_paths = [
            Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "Local State",
            Path.home() / "AppData" / "Local" / "Chromium" / "User Data" / "Local State",
        ]
        for ls_path in local_state_paths:
            if not ls_path.exists():
                continue
            with open(ls_path, "r", encoding="utf-8") as f:
                local_state = json.load(f)
            encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
            # Remove "DPAPI" prefix (5 bytes)
            encrypted_key = encrypted_key[5:]
            import ctypes
            import ctypes.wintypes

            class DATA_BLOB(ctypes.Structure):
                _fields_ = [("cbData", ctypes.wintypes.DWORD),
                            ("pbData", ctypes.POINTER(ctypes.c_char))]

            blob_in = DATA_BLOB(len(encrypted_key), ctypes.create_string_buffer(encrypted_key, len(encrypted_key)))
            blob_out = DATA_BLOB()
            if ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
            ):
                key = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                return key
        return None
    except Exception:
        return None


def _decrypt_chrome_value_windows(encrypted_value, key):
    """Decrypt Chrome cookie on Windows (AES-256-GCM, Chrome 80+)."""
    if not encrypted_value or len(encrypted_value) < 4:
        return None
    prefix = encrypted_value[:3]
    if prefix not in (b"v10", b"v11"):
        return None
    nonce = encrypted_value[3:15]
    ciphertext_tag = encrypted_value[15:]
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aes = AESGCM(key)
        plaintext = aes.decrypt(nonce, ciphertext_tag, None)
        return plaintext.decode("utf-8")
    except Exception:
        return None


def _get_chrome_key(chrome_dir, is_mac=False):
    """Derive Chrome cookie decryption key on Linux/macOS.

    Tries GNOME Keyring, KWallet, then falls back to 'peanuts'.
    Returns 16-byte AES key derived via PBKDF2.
    macOS uses 1003 iterations; Linux uses 1.
    """
    import hashlib
    import subprocess as _sp

    password = None

    # --- GNOME Keyring via secret-tool ---
    # Try v2 then v1 schemas, for both Chrome and Chromium
    gnome_lookups = [
        ("chrome_libsecret_os_crypt_password_v2", "chrome"),
        ("chrome_libsecret_os_crypt_password_v1", "chrome"),
        ("chrome_libsecret_os_crypt_password_v2", "chromium"),
        ("chrome_libsecret_os_crypt_password_v1", "chromium"),
    ]
    for schema, app in gnome_lookups:
        if password:
            break
        try:
            result = _sp.run(
                ["secret-tool", "lookup", "xdg:schema", schema, "application", app],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                password = result.stdout.strip()
                break
        except (FileNotFoundError, _sp.TimeoutExpired, OSError):
            continue

    # --- KWallet ---
    if not password:
        kwallet_lookups = [
            ("Chrome Safe Storage", "Chrome Keys"),
            ("Chrome Safe Storage", "Passwords"),
            ("Chromium Safe Storage", "Chromium Keys"),
            ("Chromium Safe Storage", "Passwords"),
        ]
        for storage_name, folder in kwallet_lookups:
            if password:
                break
            try:
                result = _sp.run(
                    ["kwallet-query", "-r", storage_name,
                     "-f", folder, "kdewallet"],
                    capture_output=True, timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    password = result.stdout.strip()
                    if "--verbose" in sys.argv:
                        print(f"[chrome] Got key from KWallet: {folder}/{storage_name}")
                    break
            except (FileNotFoundError, _sp.TimeoutExpired, OSError):
                continue

    # --- Fallback ---
    if not password:
        password = b"peanuts"
    if isinstance(password, str):
        password = password.encode("utf-8")
    elif isinstance(password, bytes):
        # Ensure consistent encoding for bytes from keyring
        try:
            password = password.decode("utf-8").encode("utf-8")
        except UnicodeDecodeError:
            pass

    # macOS uses 1003 iterations; Linux uses 1
    iterations = 1003 if is_mac else 1
    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", iterations, dklen=16)


def _decrypt_chrome_value(encrypted_value, key):
    """Decrypt a Chrome encrypted cookie value.

    Handles v10/v11 prefix, AES-128-CBC, PKCS7 unpadding, and
    Chrome 130+ (DB schema >= v24) 32-byte SHA-256 integrity hash.
    Returns decoded UTF-8 string or None.
    """
    if not encrypted_value or len(encrypted_value) < 4:
        return None

    # Strip v10/v11 prefix (3 bytes)
    prefix = encrypted_value[:3]
    if prefix not in (b"v10", b"v11"):
        return None
    ciphertext = encrypted_value[3:]

    iv = b" " * 16  # 16 space characters

    plaintext = None

    # Try cryptography package first
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7

        cipher = Cipher(algorithms.AES128(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()
    except ImportError:
        # Fallback: openssl CLI
        import subprocess as _sp
        try:
            result = _sp.run(
                ["openssl", "enc", "-aes-128-cbc", "-d",
                 "-K", key.hex(), "-iv", iv.hex(), "-nopad"],
                input=ciphertext, capture_output=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout:
                padded = result.stdout
                # Manual PKCS7 unpadding
                pad_len = padded[-1]
                if 1 <= pad_len <= 16 and padded[-pad_len:] == bytes([pad_len]) * pad_len:
                    plaintext = padded[:-pad_len]
                else:
                    plaintext = padded
        except (FileNotFoundError, _sp.TimeoutExpired, OSError):
            return None
    except Exception:
        return None

    if plaintext is None:
        return None

    # Chrome 130+ (DB schema >= v24): 32-byte SHA-256 integrity hash prepended.
    # Try with hash stripped first; if that fails UTF-8, try without stripping.
    if len(plaintext) > 32:
        stripped = plaintext[32:]
        try:
            return stripped.decode("utf-8")
        except UnicodeDecodeError:
            pass

    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _get_chrome_cookies():
    """Extract claude.ai cookies from Chrome/Chromium.

    Searches multiple browser paths and profiles, decrypts encrypted values.
    Supports Linux, Windows, and macOS paths.
    Returns cookie string or empty string.
    """
    import sqlite3
    import shutil
    import platform
    import tempfile

    is_win = platform.system() == "Windows"
    is_mac = platform.system() == "Darwin"

    if is_win:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        base_dirs = [
            local / "Google" / "Chrome" / "User Data",
            local / "Chromium" / "User Data",
            local / "BraveSoftware" / "Brave-Browser" / "User Data",
        ]
    elif is_mac:
        app_support = Path.home() / "Library" / "Application Support"
        base_dirs = [
            app_support / "Google" / "Chrome",
            app_support / "Chromium",
            app_support / "BraveSoftware" / "Brave-Browser",
        ]
    else:
        base_dirs = [
            Path.home() / ".config" / "google-chrome",
            Path.home() / ".config" / "chromium",
            Path.home() / "snap" / "chromium" / "common" / "chromium",
            Path.home() / ".var" / "app" / "com.google.Chrome" / "config" / "google-chrome",
            Path.home() / ".var" / "app" / "org.chromium.Chromium" / "config" / "chromium",
        ]

    key = None  # lazily derived
    win_key = None  # Windows AES-GCM key

    verbose = "--verbose" in sys.argv

    def _find_cookie_db(profile_dir):
        # Chrome 108+ stores at Profile/Network/Cookies; older at Profile/Cookies
        for rel in (Path("Network") / "Cookies", Path("Cookies")):
            candidate = profile_dir / rel
            if candidate.exists():
                return candidate
        return None

    def _copy_locked_win(src: Path, dst: Path):
        """Copy a file that may be open exclusively by another process (Chrome).

        Uses CreateFileW with FILE_SHARE_READ|WRITE|DELETE so we can open the
        handle regardless of Chrome's lock, then ReadFile/WriteFile in chunks.
        """
        if not is_win:
            shutil.copy2(src, dst)
            return
        GENERIC_READ = 0x80000000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        FILE_SHARE_DELETE = 0x00000004
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x80
        INVALID_HANDLE_VALUE = (1 << 64) - 1  # 0xFFFFFFFFFFFFFFFF on 64-bit

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        CreateFileW = kernel32.CreateFileW
        CreateFileW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ]
        CreateFileW.restype = ctypes.c_uint64

        handle = CreateFileW(
            str(src),
            GENERIC_READ,
            FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
            None, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, None,
        )
        if handle == INVALID_HANDLE_VALUE or handle == 0:
            err = ctypes.get_last_error()
            raise OSError(f"CreateFileW failed for {src}: err={err}")

        try:
            ReadFile = kernel32.ReadFile
            ReadFile.argtypes = [
                ctypes.c_uint64, ctypes.c_void_p, ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p,
            ]
            ReadFile.restype = ctypes.c_int

            buf_size = 65536
            buf = (ctypes.c_char * buf_size)()
            bytes_read = ctypes.c_uint32(0)
            with open(dst, "wb") as out:
                while True:
                    ok = ReadFile(handle, buf, buf_size, ctypes.byref(bytes_read), None)
                    if not ok:
                        raise OSError(f"ReadFile failed: err={ctypes.get_last_error()}")
                    if bytes_read.value == 0:
                        break
                    out.write(bytes(buf[: bytes_read.value]))
        finally:
            CloseHandle = kernel32.CloseHandle
            CloseHandle.argtypes = [ctypes.c_uint64]
            CloseHandle.restype = ctypes.c_int
            CloseHandle(handle)

    for base in base_dirs:
        if not base.exists():
            continue
        if verbose:
            print(f"[chrome] Found browser dir: {base}")
        # Dynamic profile scan: find all dirs containing a Cookies file (new or legacy layout)
        try:
            profile_dirs = [d for d in base.iterdir() if d.is_dir() and _find_cookie_db(d) is not None]
        except PermissionError:
            continue
        for profile_dir in profile_dirs:
            cookie_db = _find_cookie_db(profile_dir)
            if verbose:
                print(f"[chrome] Found cookie DB: {cookie_db}")
            tmp_dir = Path(tempfile.gettempdir())
            tmp_db = tmp_dir / f"claude_chrome_{os.getpid()}.sqlite"
            try:
                # Copy DB + WAL/SHM files (Chrome uses WAL journal mode, file may be locked)
                _copy_locked_win(cookie_db, tmp_db)
                for suffix in ["-wal", "-shm", "-journal"]:
                    wal_src = Path(str(cookie_db) + suffix)
                    wal_dst = Path(str(tmp_db) + suffix)
                    if wal_src.exists():
                        _copy_locked_win(wal_src, wal_dst)
                        if verbose:
                            print(f"[chrome] Copied {suffix} file")

                conn = sqlite3.connect(str(tmp_db))
                cursor = conn.execute(
                    "SELECT name, value, encrypted_value FROM cookies "
                    "WHERE host_key LIKE '%claude.ai%'"
                )
                rows = cursor.fetchall()
                if verbose:
                    print(f"[chrome] Found {len(rows)} claude.ai cookies in {profile_dir.name}")
                pairs = []
                failed = []  # cookies not decrypted by primary key (Linux/mac only)
                for name, value, encrypted_value in rows:
                    if value:
                        pairs.append(f"{name}={value}")
                    elif encrypted_value:
                        if is_win:
                            if win_key is None:
                                win_key = _get_chrome_key_windows()
                            if win_key:
                                decrypted = _decrypt_chrome_value_windows(encrypted_value, win_key)
                            else:
                                decrypted = None
                        else:
                            if key is None:
                                key = _get_chrome_key(base, is_mac=is_mac)
                            decrypted = _decrypt_chrome_value(encrypted_value, key)
                        if decrypted:
                            pairs.append(f"{name}={decrypted}")
                        else:
                            if not is_win:
                                failed.append((name, encrypted_value))
                            if verbose:
                                print(f"[chrome] FAILED to decrypt cookie: {name} (len={len(encrypted_value)})")

                # Keyring key may be stale (Chrome 120+ on KDE/Wayland can fall back to
                # "basic"/peanuts when XDG portal init fails — see os_crypt.portal in
                # Local State). Retry failed cookies with the peanuts fallback key.
                if failed and not pairs:
                    import hashlib as _h
                    iterations = 1003 if is_mac else 1
                    peanuts_key = _h.pbkdf2_hmac("sha1", b"peanuts", b"saltysalt", iterations, dklen=16)
                    if peanuts_key != key:
                        if verbose:
                            print(f"[chrome] Primary key decrypted 0 cookies — retrying with peanuts")
                        for name, ev in failed:
                            decrypted = _decrypt_chrome_value(ev, peanuts_key)
                            if decrypted:
                                pairs.append(f"{name}={decrypted}")
                        if verbose and pairs:
                            print(f"[chrome] Peanuts recovered {len(pairs)} cookies")
                conn.close()
                if pairs:
                    if verbose:
                        print(f"[chrome] Got {len(pairs)} cookies: {[p.split('=')[0] for p in pairs]}")
                    return "; ".join(pairs)
            except Exception as e:
                if verbose:
                    print(f"[chrome] Error reading {cookie_db}: {e}")
                continue
            finally:
                # Always cleanup temp files
                for suffix in ["", "-wal", "-shm", "-journal"]:
                    Path(str(tmp_db) + suffix).unlink(missing_ok=True)
    return ""


def _get_firefox_cookies():
    """Extract claude.ai cookies from Firefox (plain text, no decryption needed).

    Searches native, snap, flatpak, Windows, and macOS Firefox paths.
    Returns cookie string or empty string.
    """
    import sqlite3
    import shutil
    import platform

    firefox_dirs = [
        # Linux
        Path.home() / ".mozilla" / "firefox",
        Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        Path.home() / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
    ]
    if platform.system() == "Windows":
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        firefox_dirs.insert(0, appdata / "Mozilla" / "Firefox" / "Profiles")
    elif platform.system() == "Darwin":
        firefox_dirs.insert(0, Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles")

    import tempfile

    for firefox_dir in firefox_dirs:
        if not firefox_dir.exists():
            continue
        try:
            profiles = [d for d in firefox_dir.iterdir() if d.is_dir()]
        except PermissionError:
            continue
        for profile in profiles:
            cookie_db = profile / "cookies.sqlite"
            if not cookie_db.exists():
                continue
            tmp_dir = Path(tempfile.gettempdir())
            tmp_db = tmp_dir / f"claude_ff_{os.getpid()}.sqlite"
            try:
                shutil.copy2(cookie_db, tmp_db)
                # Copy WAL/SHM files (Firefox uses WAL journal mode)
                for suffix in ["-wal", "-shm", "-journal"]:
                    src = Path(str(cookie_db) + suffix)
                    dst = Path(str(tmp_db) + suffix)
                    if src.exists():
                        shutil.copy2(src, dst)
                conn = sqlite3.connect(str(tmp_db))
                cursor = conn.execute(
                    "SELECT name, value FROM moz_cookies WHERE host LIKE '%claude.ai%'"
                )
                pairs = [f"{name}={value}" for name, value in cursor.fetchall()]
                conn.close()
                if pairs:
                    return "; ".join(pairs)
            except Exception:
                continue
            finally:
                for suffix in ["", "-wal", "-shm", "-journal"]:
                    Path(str(tmp_db) + suffix).unlink(missing_ok=True)
    return ""


def _get_manual_cookies():
    """Read cookie from a manual file at ~/.claude/widget-cookies.txt.

    Accepted formats (one line):
      - bare value: "eyJhbGciOi..." (assumed to be sessionKey)
      - keyed: "sessionKey=eyJ..."
      - full string: "sessionKey=eyJ...; lastActiveOrg=abc"
    """
    path = CLAUDE_DIR / "widget-cookies.txt"
    verbose = "--verbose" in sys.argv
    if not path.exists():
        return ""
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except Exception as e:
        if verbose:
            print(f"[manual] read error: {e}")
        return ""
    if not raw:
        return ""
    if "sessionKey=" in raw:
        cookies = raw
    else:
        cookies = f"sessionKey={raw}"
    if verbose:
        print(f"[manual] using widget-cookies.txt ({len(cookies)} chars)")
    return cookies


def get_claude_cookies():
    """Extract claude.ai cookies for API auth.

    Priority: manual file → Firefox (plain text) → Chrome (encrypted, may be locked).
    Returns cookie string or empty string.
    """
    def _has_session(c):
        return "sessionKey=" in c

    cookies = _get_manual_cookies()
    if cookies and _has_session(cookies):
        return cookies

    cookies = _get_firefox_cookies()
    if cookies and _has_session(cookies):
        return cookies

    cookies = _get_chrome_cookies()
    if cookies and _has_session(cookies):
        return cookies

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
        result["monthlyLimit"] = (spend_limit.get("monthly_credit_limit") or 0) / 100
        result["usedCredits"] = (spend_limit.get("used_credits") or 0) / 100
        result["currency"] = currency
        result["disabledReason"] = spend_limit.get("disabled_reason", "")
        result["outOfCredits"] = spend_limit.get("out_of_credits", False)
    if credit_grant:
        result["grantAvailable"] = credit_grant.get("available", False)
        result["grantAmount"] = (credit_grant.get("amount_minor_units") or 0) / 100
        result["grantCurrency"] = credit_grant.get("currency") or "USD"
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
    import platform

    if new_indicator == "none":
        title = "Claude Status"
        body = "All Systems Operational"
        urgency = "normal"
    else:
        title = "Claude Status Alert"
        incidents = new_status.get("active_incidents", [])
        body = incidents[0]["name"] if incidents else new_status.get("description", "Service issue detected")
        urgency = "critical" if new_indicator in ("major", "critical") else "normal"

    # Only send desktop notifications on Linux with a display server
    if platform.system() != "Linux":
        return
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return

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


def compute_dumbness_score(
    service_status,
    session_pct,
    error_rate,
    adaptive_config,
    weekly_all_pct=0,
    weekly_sonnet_pct=0,
    weekly_opus_pct=0,
    weekly_design_pct=0,
    burn_rate=None,
    latency=None,
):
    """Composite 'dumbness' score: 0 (genius) to 100 (braindead).

    Multi-parameter, continuous-curve scoring. Factors (max 100):
      - Service health             0-30   from status.claude.com
      - Session utilization        0-20   (pct/100)^1.2 * 20 — ramps smoothly
      - Weekly all-models          0-12   (pct/100)^1.1 * 12
      - Weekly Sonnet              0-8    linear pressure above 30%
      - API errors (2h)            0-15   1.8 pts per error, capped
      - Response latency           0-10   degraded feel if consistently slow
      - Burn-rate panic            0-7    session projected to cap before reset
      - Adaptive thinking ON       0-5    tends to produce lazy responses
      - 1M context OFF             0-2    milder penalty
      - Active incidents hint      0-3    "investigating" status even without impact

    Level thresholds are tight on the genius side so a perfectly idle state is
    the only way to hit it; most working sessions land in smart/slow.
    """
    score = 0.0
    reasons = []

    # ── 1. Service health (0-30) ──────────────────────────────────────────
    ind = "none"
    active_incidents = 0
    if service_status:
        ind = service_status.get("indicator", "none")
        active_incidents = len(service_status.get("active_incidents", []))
    if ind == "critical":
        score += 30; reasons.append("Critical outage")
    elif ind == "major":
        score += 22; reasons.append("Major outage")
    elif ind == "minor":
        score += 11; reasons.append("Degraded service")
    elif active_incidents > 0:
        score += 3; reasons.append(f"{active_incidents} incident(s) investigating")

    # ── 2. Session utilization (0-20) ─────────────────────────────────────
    if session_pct > 0:
        pts = min(20.0, (session_pct / 100.0) ** 1.2 * 20.0)
        score += pts
        if session_pct >= 80:
            reasons.append(f"Session {session_pct:.0f}% — near cap")
        elif session_pct >= 50:
            reasons.append(f"Session {session_pct:.0f}%")

    # ── 3. Weekly all-models (0-12) ───────────────────────────────────────
    if weekly_all_pct > 0:
        pts = min(12.0, (weekly_all_pct / 100.0) ** 1.1 * 12.0)
        score += pts
        if weekly_all_pct >= 70:
            reasons.append(f"Weekly {weekly_all_pct:.0f}%")

    # ── 4. Per-model weekly pressure (Sonnet/Opus/Design) (0-8 combined) ──
    model_pressure = 0.0
    if weekly_sonnet_pct > 30:
        model_pressure += (weekly_sonnet_pct - 30) / 8.75
        if weekly_sonnet_pct >= 60:
            reasons.append(f"Sonnet weekly {weekly_sonnet_pct:.0f}%")
    if weekly_opus_pct > 30:
        model_pressure += (weekly_opus_pct - 30) / 8.75
        if weekly_opus_pct >= 60:
            reasons.append(f"Opus weekly {weekly_opus_pct:.0f}%")
    if weekly_design_pct > 30:
        model_pressure += (weekly_design_pct - 30) / 8.75
        if weekly_design_pct >= 60:
            reasons.append(f"Design weekly {weekly_design_pct:.0f}%")
    score += min(8.0, model_pressure)

    # ── 5. API errors in 2h window (0-15) ─────────────────────────────────
    total_err = error_rate.get("total", 0) if error_rate else 0
    rate_limit_err = error_rate.get("rate_limit", 0) if error_rate else 0
    if total_err > 0:
        # Rate-limit errors are 2x as painful as generic ones
        weighted = total_err + rate_limit_err
        pts = min(15.0, weighted * 1.8)
        score += pts
        if total_err >= 5:
            reasons.append(f"{total_err} errors/2h")
        elif total_err >= 2:
            reasons.append(f"{total_err} errors/2h")

    # ── 6. Response latency (0-10) ────────────────────────────────────────
    if latency:
        avg = latency.get("avgSeconds", 0)
        sample = latency.get("sampleSize", 0)
        if sample >= 5 and avg > 0:
            # 8s = 0, 12s = 3, 18s = 7, 25s+ = 10
            if avg > 25:
                pts = 10.0
            elif avg > 8:
                pts = min(10.0, (avg - 8) * 0.7)
            else:
                pts = 0.0
            score += pts
            if avg > 18:
                reasons.append(f"Slow responses ({avg:.0f}s avg)")

    # ── 7. Burn-rate panic (0-7) ──────────────────────────────────────────
    if burn_rate and session_pct > 0:
        output_per_h = burn_rate.get("output_per_hour", 0)
        # High burn + already stressed session = panic. Weight smoothly.
        if output_per_h > 200_000 and session_pct > 30:
            panic = min(7.0, (session_pct - 30) / 10.0 + (output_per_h - 200_000) / 300_000)
            if panic > 0:
                score += panic
                if panic >= 4:
                    reasons.append("High burn rate — limit approaching fast")

    # ── 8. Config penalties ───────────────────────────────────────────────
    if adaptive_config and adaptive_config.get("adaptive_thinking", True):
        score += 5; reasons.append("Adaptive thinking ON (lazy responses)")
    if adaptive_config and not adaptive_config.get("context_1m", True):
        score += 2; reasons.append("1M context OFF")

    score = min(100, int(round(score)))

    # Tight genius band so even light activity moves the needle.
    if score < 5:
        level = "genius"
    elif score < 20:
        level = "smart"
    elif score < 45:
        level = "slow"
    elif score < 70:
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
        five_hour = api_data.get("five_hour") or {}
        seven_day = api_data.get("seven_day") or {}

        # Calculate reset time (parse_timestamp handles Z suffix on Python < 3.11)
        reset_dt = parse_timestamp(five_hour.get("resets_at", ""))
        reset_minutes = max(0, int((reset_dt - now).total_seconds() / 60)) if reset_dt else 0

        # Weekly all models reset
        wr_dt = parse_timestamp(seven_day.get("resets_at", ""))
        weekly_reset_label = wr_dt.strftime("%a %I:%M %p") if wr_dt else ""

        def _weekly_block(payload):
            """Shape a seven_day_* entry. Returns None if the API omitted it (null)."""
            if not payload:
                return None
            d = parse_timestamp(payload.get("resets_at", ""))
            return {
                "percentUsed": payload.get("utilization", 0) or 0,
                "resetsLabel": d.strftime("%a %I:%M %p") if d else "",
            }

        # weeklySonnet is always present for backward compatibility with existing
        # consumers (QML, Tauri JS, PySide6) that read rateLimits.weeklySonnet
        # directly. It defaults to 0% when the API returned null.
        sonnet_payload = api_data.get("seven_day_sonnet") or {}
        ss_dt = parse_timestamp(sonnet_payload.get("resets_at", ""))
        result = {
            "session": {
                "percentUsed": five_hour.get("utilization", 0) or 0,
                "resetsInMinutes": reset_minutes,
                "windowHours": 5,
            },
            "weeklyAll": {
                "percentUsed": seven_day.get("utilization", 0) or 0,
                "resetsLabel": weekly_reset_label,
            },
            "weeklySonnet": {
                "percentUsed": sonnet_payload.get("utilization", 0) or 0,
                "resetsLabel": ss_dt.strftime("%a %I:%M %p") if ss_dt else "",
            },
            "plan": "Max (20x)",
            "source": "api",
        }

        # New per-model weekly blocks (Opus, Claude Design/omelette, OAuth apps,
        # Cowork). Each is omitted when the API returned null so consumers can
        # check `if "weeklyOpus" in rateLimits` cleanly without confusing a real
        # zero with an unavailable metric.
        weekly_opus = _weekly_block(api_data.get("seven_day_opus"))
        if weekly_opus:
            result["weeklyOpus"] = weekly_opus
        # "omelette" is Anthropic's internal codename for the Claude Design surface.
        weekly_design = _weekly_block(api_data.get("seven_day_omelette"))
        if weekly_design:
            result["weeklyDesign"] = weekly_design
        weekly_oauth_apps = _weekly_block(api_data.get("seven_day_oauth_apps"))
        if weekly_oauth_apps:
            result["weeklyOauthApps"] = weekly_oauth_apps
        # "cowork" covers the Claude Code teams / collaboration tier when active.
        weekly_cowork = _weekly_block(api_data.get("seven_day_cowork"))
        if weekly_cowork:
            result["weeklyCowork"] = weekly_cowork

        # Inline extra_usage summary (the `usage` endpoint also carries a quick
        # snapshot; the full shape lives under overage_spend_limit below).
        inline_eu = api_data.get("extra_usage") or {}
        if inline_eu.get("is_enabled"):
            result["extraUsageInline"] = {
                "enabled": True,
                "monthlyLimit": (inline_eu.get("monthly_limit") or 0) / 100,
                "usedCredits": (inline_eu.get("used_credits") or 0) / 100,
                "utilization": inline_eu.get("utilization") or 0,
                "currency": inline_eu.get("currency") or "USD",
            }

        # Add credits info (full details)
        if credits_data:
            amount = credits_data.get("amount") or 0
            currency = credits_data.get("currency") or "USD"
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
    weekly_all_pct = rate_limits.get("weeklyAll", {}).get("percentUsed", 0)
    weekly_sonnet_pct = rate_limits.get("weeklySonnet", {}).get("percentUsed", 0)
    weekly_opus_pct = (rate_limits.get("weeklyOpus") or {}).get("percentUsed", 0)
    weekly_design_pct = (rate_limits.get("weeklyDesign") or {}).get("percentUsed", 0)
    latency = calculate_latency()
    dumbness = compute_dumbness_score(
        service_status, session_pct, error_rate, adaptive_config,
        weekly_all_pct=weekly_all_pct,
        weekly_sonnet_pct=weekly_sonnet_pct,
        weekly_opus_pct=weekly_opus_pct,
        weekly_design_pct=weekly_design_pct,
        burn_rate=burn_rate,
        latency=latency,
    )
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


def run_health_check():
    """Diagnose cookie extraction end-to-end and print a structured report.

    Exit 0 if we can reach the live API, 1 otherwise.
    Designed to be called by installers or manually by users after install.
    """
    import platform
    report = {
        "ok": False,
        "source": None,
        "firefox": {"present": False, "cookies": 0, "hasSessionKey": False, "reason": None},
        "chrome":  {"present": False, "cookies": 0, "decrypted": 0, "keyStrategy": None, "reason": None},
        "winner": None,
        "advice": [],
    }

    # ── Firefox: inspect DB directly (fast, plain text) ──
    import sqlite3, shutil, tempfile
    firefox_dirs = [
        Path.home() / ".mozilla" / "firefox",
        Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        Path.home() / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
    ]
    if platform.system() == "Windows":
        firefox_dirs.insert(0, Path(os.environ.get("APPDATA", Path.home())) / "Mozilla" / "Firefox" / "Profiles")
    elif platform.system() == "Darwin":
        firefox_dirs.insert(0, Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles")

    ff_cookies = _get_firefox_cookies()
    for fd in firefox_dirs:
        if fd.exists():
            report["firefox"]["present"] = True
            break
    if ff_cookies:
        report["firefox"]["cookies"] = ff_cookies.count("=") + (1 if ff_cookies and not ff_cookies.endswith("=") else 0)
        report["firefox"]["cookies"] = len(ff_cookies.split("; "))
        report["firefox"]["hasSessionKey"] = "sessionKey=" in ff_cookies
        if not report["firefox"]["hasSessionKey"]:
            report["firefox"]["reason"] = "cookies present but no sessionKey (not logged in or session expired)"
    elif report["firefox"]["present"]:
        report["firefox"]["reason"] = "profile exists but no claude.ai cookies found"

    # ── Chrome: parallel path that tracks which key strategy wins ──
    is_mac = platform.system() == "Darwin"
    is_win = platform.system() == "Windows"
    if is_win:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        chrome_bases = [local / "Google" / "Chrome" / "User Data",
                        local / "Chromium" / "User Data",
                        local / "BraveSoftware" / "Brave-Browser" / "User Data"]
    elif is_mac:
        asup = Path.home() / "Library" / "Application Support"
        chrome_bases = [asup / "Google" / "Chrome", asup / "Chromium",
                        asup / "BraveSoftware" / "Brave-Browser"]
    else:
        chrome_bases = [Path.home() / ".config" / "google-chrome",
                        Path.home() / ".config" / "chromium",
                        Path.home() / "snap" / "chromium" / "common" / "chromium",
                        Path.home() / ".var" / "app" / "com.google.Chrome" / "config" / "google-chrome",
                        Path.home() / ".var" / "app" / "org.chromium.Chromium" / "config" / "chromium"]
    for cb in chrome_bases:
        if cb.exists():
            report["chrome"]["present"] = True
            chrome_base = cb
            break
    else:
        chrome_base = None

    ch_cookies = _get_chrome_cookies()
    if ch_cookies:
        report["chrome"]["decrypted"] = len(ch_cookies.split("; "))
        report["chrome"]["cookies"] = report["chrome"]["decrypted"]
        report["chrome"]["hasSessionKey"] = "sessionKey=" in ch_cookies
        # Detect which key strategy actually worked, for diagnostic output
        if chrome_base and not is_win:
            primary = _get_chrome_key(chrome_base, is_mac=is_mac)
            import hashlib as _h
            peanuts = _h.pbkdf2_hmac("sha1", b"peanuts", b"saltysalt", 1003 if is_mac else 1, dklen=16)
            report["chrome"]["keyStrategy"] = "peanuts-fallback" if primary != peanuts else "peanuts"
            # If primary isn't peanuts but the fallback recovered cookies, that's the stale-keyring case
            if primary != peanuts:
                # Test primary key against the first encrypted cookie to see if it actually works
                try:
                    import tempfile as _tf
                    db = chrome_base / "Default" / "Cookies"
                    if db.exists():
                        with _tf.NamedTemporaryFile(delete=False, suffix=".sqlite") as t:
                            shutil.copy2(db, t.name)
                            for suf in ("-wal","-shm","-journal"):
                                s = Path(str(db)+suf)
                                if s.exists(): shutil.copy2(s, t.name+suf)
                            cx = sqlite3.connect(t.name)
                            row = cx.execute("SELECT encrypted_value FROM cookies WHERE host_key LIKE '%claude.ai%' AND encrypted_value IS NOT NULL LIMIT 1").fetchone()
                            cx.close()
                        for suf in ("","-wal","-shm","-journal"):
                            Path(t.name+suf).unlink(missing_ok=True)
                        if row and _decrypt_chrome_value(row[0], primary):
                            report["chrome"]["keyStrategy"] = "keyring"
                        else:
                            report["chrome"]["keyStrategy"] = "peanuts-fallback"
                            report["chrome"]["reason"] = "stale keyring entry — Chrome is using basic/peanuts encryption (common on KDE/Wayland when XDG portal fails)"
                except Exception:
                    pass
    elif report["chrome"]["present"]:
        report["chrome"]["reason"] = "profile exists but no claude.ai cookies decrypted"

    # ── Determine winner & API source ──
    cookies = get_claude_cookies()
    if cookies and "sessionKey=" in cookies:
        # Match which browser produced the winning cookies (Firefox is tried first)
        if ff_cookies and "sessionKey=" in ff_cookies:
            report["winner"] = "firefox"
        else:
            report["winner"] = "chrome"
        # Try hitting the API to confirm credentials aren't rejected
        try:
            # reuse existing rate_limits builder — source=='api' means it worked
            rl = build_rate_limits()
            report["source"] = rl.get("source", "local_estimate")
            report["ok"] = report["source"] == "api"
        except Exception as e:
            # Reaching this branch means the API responded but our code crashed
            # processing the payload — it's a collector bug, not an auth problem.
            report["source"] = "local_estimate"
            report["collectorError"] = f"{type(e).__name__}: {e}"
            report["advice"].append(
                f"Collector bug (not an auth failure): {type(e).__name__}: {e}. "
                "Please report this at https://github.com/MrSchrodingers/claude-usage-widget/issues "
                "with the output of: claude-usage-collector.py --verbose"
            )
    else:
        report["source"] = "local_estimate"

    # ── Build actionable advice ──
    if report["ok"]:
        report["advice"].append(f"Live API reachable via {report['winner']}.")
    else:
        if not report["firefox"]["present"] and not report["chrome"]["present"]:
            report["advice"].append("No supported browser profile found. Install Firefox or Chrome and log in to https://claude.ai.")
        if report["firefox"]["present"] and not report["firefox"]["hasSessionKey"]:
            snap_ff_dir = Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox"
            native_ff_dir = Path.home() / ".mozilla" / "firefox"
            if snap_ff_dir.exists() and not native_ff_dir.exists():
                report["advice"].append(
                    "Firefox Snap detected — open https://claude.ai and sign in. "
                    "If you're already logged in and this persists, the Snap sandbox may be blocking reads; "
                    "try the native package (e.g. Mozilla PPA on Ubuntu) or use Chrome."
                )
            else:
                report["advice"].append("Firefox: open https://claude.ai and sign in (no sessionKey cookie found).")
        if report["chrome"]["present"] and report["chrome"].get("keyStrategy") == "peanuts-fallback" and report["chrome"]["decrypted"] == 0:
            report["advice"].append("Chrome: stale KWallet entry blocked decryption. Try: kwallet-query -w 'Chrome Keys' -f 'Chrome Safe Storage' kdewallet  (then restart Chrome).")
        if report["chrome"]["present"] and report["chrome"]["decrypted"] == 0 and report["chrome"].get("reason") != "stale keyring entry — Chrome is using basic/peanuts encryption (common on KDE/Wayland when XDG portal fails)":
            report["advice"].append("Chrome: cookies exist but couldn't be decrypted. Make sure Chrome is fully closed during collection, or try logging in again.")
        if report["winner"] and report["source"] != "api" and not report.get("collectorError"):
            report["advice"].append("Got cookies but API rejected them — session may be expired. Re-login at https://claude.ai.")

    # Machine-readable (stdout) — installers parse this
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        # Human-readable summary
        # Disable ANSI on non-TTY, Windows (pre-PS7), or NO_COLOR per spec
        use_color = sys.stdout.isatty() and platform.system() != "Windows" and not os.environ.get("NO_COLOR")
        if use_color:
            GREEN, RED, AMBER, DIM, NC = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"
        else:
            GREEN = RED = AMBER = DIM = NC = ""
        mark = f"{GREEN}✓{NC}" if report["ok"] else f"{AMBER}!{NC}"
        print(f"{mark} Claude Usage Collector — health check")
        print(f"  Source: {report['source']}  Winner: {report['winner'] or 'none'}")
        for browser in ("firefox", "chrome"):
            b = report[browser]
            if not b["present"]:
                print(f"  {DIM}{browser}: not installed{NC}")
                continue
            status = GREEN+"OK"+NC if (browser == report["winner"]) else AMBER+"skipped"+NC if report["ok"] else RED+"failed"+NC
            extra = []
            if browser == "chrome" and b.get("keyStrategy"):
                extra.append(f"key={b['keyStrategy']}")
            if b.get("cookies"):
                extra.append(f"cookies={b['cookies']}")
            if b.get("decrypted") is not None and browser == "chrome":
                extra.append(f"decrypted={b['decrypted']}")
            # Only show reason when it's actually blocking us (not when fallback succeeded)
            if b.get("reason") and browser != report["winner"]:
                extra.append(f"reason={b['reason']}")
            print(f"  {browser}: {status}  ({', '.join(extra)})" if extra else f"  {browser}: {status}")
        if report["advice"]:
            print()
            for a in report["advice"]:
                print(f"  {DIM}→{NC} {a}")

    sys.exit(0 if report["ok"] else 1)


def main():
    if "--health-check" in sys.argv:
        run_health_check()
        return  # unreachable (run_health_check exits), but explicit

    try:
        data = build_widget_data()

        # --test-state override for HITL testing
        for arg in sys.argv:
            if arg.startswith("--test-state="):
                state = arg.split("=", 1)[1]
                if state in TEST_STATES:
                    data["dumbness"] = TEST_STATES[state]
                    if state in ("slow", "dumb", "braindead"):
                        if not data.get("serviceStatus"):
                            data["serviceStatus"] = {"indicator": "none", "description": "", "components": [], "active_incidents": []}
                        data["serviceStatus"]["indicator"] = "minor" if state == "slow" else "major"
                        if data.get("rateLimits", {}).get("session"):
                            data["rateLimits"]["session"]["percentUsed"] = 65 if state == "slow" else 84 if state == "dumb" else 95
                        if data.get("errorRate") is not None:
                            data["errorRate"]["total"] = 3 if state == "slow" else 5 if state == "dumb" else 12

        # Atomic write with restrictive permissions
        tmp_path = str(OUTPUT_FILE) + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, OUTPUT_FILE)
        try:
            os.chmod(OUTPUT_FILE, 0o600)
        except OSError:
            pass
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
