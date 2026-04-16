# Tauri v2 Cross-Platform Tray App — Core MVP

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Tauri v2 tray app that reads `~/.claude/widget-data.json` and displays Claude usage data in a frameless popup — covering Windows, Ubuntu GNOME, and any non-KDE Linux desktop.

**Architecture:** Rust backend handles tray icon, file watching, and window management. Web frontend (vanilla JS + Vite) renders a frameless popup panel with the same data the KDE plasmoid shows. The Python collector is enhanced with Chrome/Chromium cookie support (Task 0) then the Tauri app consumes its JSON output.

**Tech Stack:** Tauri v2, Rust, Vite, vanilla HTML/CSS/JS, Python 3 (collector). No frontend framework. No charting library.

**Scope:** This plan covers: (1) **Chrome/Chromium cookie support** in the collector (Task 0 — priority fix, benefits existing plasmoid users too), (2) the Tauri core MVP: tray icon, frameless popup, file watching, theme system, header+mascot, session card with SVG progress ring + live countdown, weekly limits card, service health card, dumbness score card, and global shortcut (Linux workaround). The remaining cards (credits, metrics, charts, quick actions) follow the same pattern and are covered in Plan 2.

**XSS Note:** All dynamic data rendered in this app comes exclusively from `widget-data.json`, a local file written by our own Python collector — not from user input or external sources. The data contains numeric values, enum strings, and pre-formatted labels. DOM construction uses template literals for layout convenience; this is safe because the data source is trusted and local-only. If the data source ever changes to accept external input, switch to `textContent` and DOM API calls.

**Data contract:** The app reads `~/.claude/widget-data.json` (written by the existing Python collector every 30s). Top-level keys: `generatedAt`, `rateLimits`, `today`, `modelBreakdown`, `sessions`, `trend7d`, `lifetime`, `serviceStatus`, `errorRate`, `burnRate`, `adaptiveThinking`, `dumbness`, `latency`, `responseQuality`, `streak`, `limitEta`, `claudeCodeVersion`.

---

## File Structure

```
claude-usage-widget/
└── tauri-app/                        # NEW directory (entire Tauri project)
    ├── package.json                  # npm deps (Tauri JS APIs)
    ├── vite.config.js                # Vite dev server config
    ├── index.html                    # Main HTML skeleton
    ├── src/
    │   ├── main.js                   # Entry: event listeners, data store, render orchestration
    │   ├── components/
    │   │   ├── header.js             # Header + mascot sprite + status label
    │   │   ├── session-card.js       # SVG progress ring + countdown + session %
    │   │   ├── weekly-card.js        # Weekly all-models + Sonnet limits
    │   │   ├── health-card.js        # Service health grid + incidents
    │   │   └── dumbness-card.js      # Dumbness score + factors
    │   ├── lib/
    │   │   ├── countdown.js          # Live countdown timer (1s tick)
    │   │   └── theme.js              # Dark/light theme detection + CSS var injection
    │   └── styles/
    │       └── main.css              # All styles (theme vars, cards, progress ring, layout)
    ├── public/
    │   └── sprites/                  # Copied from plasmoid/contents/icons/
    │       ├── claude-logo.png
    │       ├── halo-{0..5}.png       # genius state
    │       ├── smart-{0..5}.png      # smart state
    │       ├── rain-{0..5}.png       # slow state
    │       ├── fire-{0..5}.png       # dumb state
    │       ├── skull-{0..5}.png      # braindead state
    │       └── sun-{0..5}.png        # healthy idle
    └── src-tauri/
        ├── Cargo.toml                # Rust deps (tauri, notify, dirs)
        ├── build.rs                  # Tauri build script
        ├── tauri.conf.json           # App config (frameless window, tray, permissions)
        ├── capabilities/
        │   └── default.json          # Permission grants for plugins
        ├── icons/
        │   └── icon.png              # Tray icon (copy claude-logo.png)
        └── src/
            ├── main.rs               # Binary entry point (one line)
            ├── lib.rs                 # Tauri setup: plugins, tray, file watcher, window mgmt
            └── tray.rs               # Tray icon builder + click/position logic
```

---

## Task 0: Chrome/Chromium Cookie Support in Collector (Priority Fix)

**Files:**
- Modify: `scripts/claude-usage-collector.py` (functions `get_claude_cookies`, add `_get_chrome_cookies`, `_get_chrome_key`, `_decrypt_chrome_value`)

**Why first:** An existing user is blocked because they use Chrome (cookies are encrypted, collector only reads Firefox). This fix benefits BOTH the plasmoid and the future Tauri app since both depend on the collector producing valid data.

**Technical background:** On Linux, Chrome encrypts cookie values with AES-128-CBC. The encryption key is derived via PBKDF2-SHA1 from a password stored in the system keyring (GNOME Keyring or KWallet). If no keyring is available, Chrome falls back to the hardcoded password `peanuts`. Chrome >= DB schema v24 (Chrome 130+) prepends a 32-byte SHA-256 integrity hash to the plaintext before encrypting — this must be stripped after decryption.

- [ ] **Step 1: Add `_get_chrome_key` function**

Insert after `get_claude_cookies` (around line 243):

```python
def _get_chrome_key(chrome_dir):
    """Derive Chrome cookie decryption key on Linux.

    Chrome stores a password in the system keyring (GNOME Keyring or KWallet).
    Falls back to 'peanuts' if no keyring is available.
    Key = PBKDF2-HMAC-SHA1(password, salt='saltysalt', iterations=1, dklen=16).
    """
    import hashlib
    import subprocess as _sp

    password = b"peanuts"  # fallback when no keyring

    # Try GNOME Keyring / SecretService via secret-tool
    for schema_suffix in ("v2", "v1"):
        for app_name in ("chrome", "chromium"):
            try:
                r = _sp.run(
                    ["secret-tool", "lookup",
                     "xdg:schema", f"chrome_libsecret_os_crypt_password_{schema_suffix}",
                     "application", app_name],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0 and r.stdout.strip():
                    password = r.stdout.strip().encode()
                    break
            except Exception:
                continue
        else:
            continue
        break

    # Try KWallet (KDE) if secret-tool didn't find anything
    if password == b"peanuts":
        for wallet_app in ("Chrome", "Chromium"):
            try:
                r = _sp.run(
                    ["kwallet-query", "--read-password",
                     f"{wallet_app} Safe Storage",
                     "--folder", f"{wallet_app} Keys", "kdewallet"],
                    capture_output=True, text=True, timeout=5,
                )
                if r.returncode == 0 and r.stdout.strip():
                    password = r.stdout.strip().encode()
                    break
            except Exception:
                continue

    return hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1, dklen=16)
```

- [ ] **Step 2: Add `_decrypt_chrome_value` function**

```python
def _decrypt_chrome_value(encrypted_value, key):
    """Decrypt a Chrome cookie value (AES-128-CBC, Linux).

    Handles both v10 (peanuts key) and v11 (keyring key) prefixes.
    Chrome DB schema >= v24 prepends 32-byte SHA-256 hash to plaintext.
    """
    if not encrypted_value or len(encrypted_value) < 4:
        return None

    prefix = encrypted_value[:3]
    if prefix not in (b"v10", b"v11"):
        return None

    ciphertext = encrypted_value[3:]
    iv = b" " * 16  # 16 space characters (0x20)

    # Try 'cryptography' package first (most reliable)
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives.padding import PKCS7
        cipher = Cipher(algorithms.AES128(key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        unpadder = PKCS7(128).unpadder()
        plaintext = unpadder.update(padded) + unpadder.finalize()
    except ImportError:
        # Fallback: use openssl CLI (available on all Linux distros)
        import subprocess as _sp
        try:
            r = _sp.run(
                ["openssl", "enc", "-aes-128-cbc", "-d",
                 "-K", key.hex(), "-iv", iv.hex(), "-nopad"],
                input=ciphertext, capture_output=True, timeout=5,
            )
            if r.returncode != 0:
                return None
            padded = r.stdout
            # Manual PKCS7 unpadding
            pad_len = padded[-1] if padded else 0
            if 1 <= pad_len <= 16 and all(b == pad_len for b in padded[-pad_len:]):
                plaintext = padded[:-pad_len]
            else:
                plaintext = padded
        except Exception:
            return None

    # Chrome DB schema >= v24: first 32 bytes are SHA-256 integrity hash
    if len(plaintext) > 32:
        plaintext = plaintext[32:]

    try:
        return plaintext.decode("utf-8")
    except UnicodeDecodeError:
        return None
```

- [ ] **Step 3: Add `_get_chrome_cookies` function**

```python
def _get_chrome_cookies():
    """Extract claude.ai cookies from Chrome/Chromium on Linux."""
    import sqlite3
    import shutil

    # All known Chrome/Chromium paths on Linux (deb, snap, flatpak)
    chrome_paths = [
        ("google-chrome", Path.home() / ".config" / "google-chrome"),
        ("chromium",      Path.home() / ".config" / "chromium"),
        ("chromium-snap", Path.home() / "snap" / "chromium" / "common" / "chromium"),
        ("chrome-flatpak", Path.home() / ".var" / "app" / "com.google.Chrome" / "config" / "google-chrome"),
        ("chromium-flatpak", Path.home() / ".var" / "app" / "org.chromium.Chromium" / "config" / "chromium"),
    ]

    for variant, base_dir in chrome_paths:
        if not base_dir.exists():
            continue

        # Try Default profile, then Profile 1, 2, etc.
        profiles = ["Default"] + [f"Profile {i}" for i in range(1, 6)]
        for profile in profiles:
            cookie_db = base_dir / profile / "Cookies"
            if not cookie_db.exists():
                continue

            try:
                key = _get_chrome_key(base_dir)

                tmp_db = Path("/tmp/claude_chrome_cookies.sqlite")
                shutil.copy2(cookie_db, tmp_db)
                conn = sqlite3.connect(str(tmp_db))
                cursor = conn.execute(
                    "SELECT name, value, encrypted_value FROM cookies "
                    "WHERE host_key LIKE '%claude.ai%'"
                )

                pairs = []
                for name, plain_value, enc_value in cursor.fetchall():
                    if plain_value:
                        pairs.append(f"{name}={plain_value}")
                    elif enc_value:
                        decrypted = _decrypt_chrome_value(enc_value, key)
                        if decrypted:
                            pairs.append(f"{name}={decrypted}")

                conn.close()
                tmp_db.unlink(missing_ok=True)

                if pairs:
                    return "; ".join(pairs)
            except Exception:
                continue

    return ""
```

- [ ] **Step 4: Refactor `get_claude_cookies` to try Firefox then Chrome**

Replace the existing `get_claude_cookies` function (lines 218-242):

```python
def get_claude_cookies():
    """Extract claude.ai cookies. Tries Firefox first, then Chrome/Chromium."""
    # Try Firefox (cookies are plain text — fastest and most reliable)
    cookies = _get_firefox_cookies()
    if cookies:
        return cookies

    # Try Chrome/Chromium (cookies are encrypted)
    cookies = _get_chrome_cookies()
    if cookies:
        return cookies

    return ""


def _get_firefox_cookies():
    """Extract claude.ai cookies from Firefox on Linux."""
    import sqlite3
    import shutil

    # All known Firefox paths on Linux (deb, snap, flatpak)
    firefox_dirs = [
        Path.home() / ".mozilla" / "firefox",
        Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        Path.home() / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
    ]

    for firefox_dir in firefox_dirs:
        if not firefox_dir.exists():
            continue
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
```

- [ ] **Step 5: Add `--verbose` diagnostic output for browser detection**

Find the existing `--verbose` flag handling (search for `--verbose` in the script) and add browser detection info. In the `main()` function, after detecting cookies:

```python
if "--verbose" in sys.argv:
    cookies = get_claude_cookies()
    if cookies:
        # Show which browser provided the cookies (without leaking values)
        cookie_names = [p.split("=")[0].strip() for p in cookies.split(";")]
        print(f"[OK] Cookies found: {', '.join(cookie_names)}")
    else:
        print("[FAIL] No cookies found in Firefox or Chrome/Chromium")
        print("  Checked Firefox: ~/.mozilla/firefox, ~/snap/firefox, ~/.var/app/org.mozilla.firefox")
        print("  Checked Chrome:  ~/.config/google-chrome, ~/.config/chromium, ~/snap/chromium")
```

- [ ] **Step 6: Test with Firefox (regression check)**

Run: `~/.local/bin/claude-usage-collector.py --verbose`
Expected: `[OK] Cookies found: ...` with valid cookie names. Widget data should still update correctly in `~/.claude/widget-data.json`.

- [ ] **Step 7: Test with Chrome (if available)**

If Chrome is installed with claude.ai cookies:
Run: Temporarily rename `~/.mozilla/firefox` to force Chrome fallback, then:
```bash
mv ~/.mozilla/firefox ~/.mozilla/firefox.bak
~/.local/bin/claude-usage-collector.py --verbose
mv ~/.mozilla/firefox.bak ~/.mozilla/firefox
```
Expected: `[OK] Cookies found: ...` from Chrome. If `cryptography` is not installed and `openssl` is the fallback, verify decryption still works.

- [ ] **Step 8: Commit Chrome support**

```bash
cd /home/ti/claude-usage-widget
git add scripts/claude-usage-collector.py
git commit -m "feat: add Chrome/Chromium cookie support (AES-128-CBC decryption)

Supports: Google Chrome, Chromium (native/snap/flatpak), multiple profiles.
Key retrieval: GNOME Keyring (secret-tool) > KWallet > fallback.
Decryption: cryptography package > openssl CLI fallback.
Handles Chrome DB schema v24+ (SHA-256 integrity hash prefix).
Firefox remains the first-choice browser (plain text, no decryption needed).
Also adds snap/flatpak Firefox path probing."
```

---

## Task 1: Install Development Environment

- [ ] **Step 1: Install Rust toolchain**

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source "$HOME/.cargo/env"
```

- [ ] **Step 2: Verify Rust**

Run: `rustc --version && cargo --version`
Expected: `rustc 1.8x.x` and `cargo 1.8x.x`

- [ ] **Step 3: Install Tauri system dependencies (Fedora)**

```bash
sudo dnf install -y webkit2gtk4.1-devel libappindicator-gtk3-devel librsvg2-devel patchelf openssl-devel
```

- [ ] **Step 4: Install Tauri CLI**

```bash
cargo install tauri-cli --version "^2"
```

- [ ] **Step 5: Verify Tauri CLI**

Run: `cargo tauri --version`
Expected: `tauri-cli 2.x.x`

---

## Task 2: Scaffold Tauri v2 Project

**Files:**
- Create: `tauri-app/package.json`
- Create: `tauri-app/vite.config.js`
- Create: `tauri-app/index.html`
- Create: `tauri-app/src/main.js`
- Create: `tauri-app/src/styles/main.css`
- Create: `tauri-app/src-tauri/Cargo.toml`
- Create: `tauri-app/src-tauri/build.rs`
- Create: `tauri-app/src-tauri/tauri.conf.json`
- Create: `tauri-app/src-tauri/capabilities/default.json`
- Create: `tauri-app/src-tauri/src/main.rs`
- Create: `tauri-app/src-tauri/src/lib.rs`

- [ ] **Step 1: Create directory structure**

```bash
cd /home/ti/claude-usage-widget
mkdir -p tauri-app/{src/{components,lib,styles},public/sprites,src-tauri/{src,capabilities,icons}}
```

- [ ] **Step 2: Write package.json**

```json
{
  "name": "claude-usage-tray",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "tauri": "tauri"
  },
  "dependencies": {
    "@tauri-apps/api": "^2",
    "@tauri-apps/plugin-clipboard-manager": "^2",
    "@tauri-apps/plugin-global-shortcut": "^2",
    "@tauri-apps/plugin-notification": "^2",
    "@tauri-apps/plugin-shell": "^2"
  },
  "devDependencies": {
    "vite": "^6"
  }
}
```

- [ ] **Step 3: Write vite.config.js**

```js
import { defineConfig } from "vite";

export default defineConfig({
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    watch: { ignored: ["**/src-tauri/**"] },
  },
});
```

- [ ] **Step 4: Write index.html (minimal skeleton)**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Claude Usage Monitor</title>
  <link rel="stylesheet" href="/src/styles/main.css" />
</head>
<body>
  <div id="app">
    <p style="color:#888;padding:16px;">Loading...</p>
  </div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 5: Write starter main.js**

```js
// src/main.js
document.getElementById("app").textContent = "Claude Usage Tray — scaffold OK";
```

- [ ] **Step 6: Write starter main.css**

```css
/* src/styles/main.css */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
#app { width: 100vw; height: 100vh; overflow: hidden; }
```

- [ ] **Step 7: Write Cargo.toml**

```toml
[package]
name = "claude-usage-tray"
version = "1.0.0"
edition = "2021"

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = ["tray-icon"] }
tauri-plugin-clipboard-manager = "2"
tauri-plugin-global-shortcut = "2"
tauri-plugin-notification = "2"
tauri-plugin-shell = "2"
notify = { version = "7", default-features = false, features = ["macos_fsevent"] }
dirs = "6"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

- [ ] **Step 8: Write build.rs**

```rust
fn main() {
    tauri_build::build();
}
```

- [ ] **Step 9: Write tauri.conf.json**

```json
{
  "productName": "Claude Usage Monitor",
  "version": "1.0.0",
  "identifier": "com.mrschrodingers.claude-usage-tray",
  "build": {
    "frontendDist": "../dist",
    "devUrl": "http://localhost:1420",
    "beforeDevCommand": "npm run dev",
    "beforeBuildCommand": "npm run build"
  },
  "app": {
    "windows": [
      {
        "label": "popup",
        "title": "Claude Usage",
        "width": 400,
        "height": 680,
        "decorations": false,
        "resizable": false,
        "skipTaskbar": true,
        "visible": false,
        "alwaysOnTop": true,
        "transparent": true,
        "shadow": true
      }
    ],
    "trayIcon": {
      "iconPath": "icons/icon.png",
      "tooltip": "Claude Usage Monitor"
    },
    "security": {
      "csp": "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' asset: tauri:"
    }
  },
  "bundle": {
    "active": true,
    "icon": [
      "icons/icon.png"
    ]
  }
}
```

- [ ] **Step 10: Write capabilities/default.json**

```json
{
  "identifier": "default",
  "description": "Default permissions for the app",
  "windows": ["popup"],
  "permissions": [
    "core:default",
    "core:window:default",
    "core:window:allow-show",
    "core:window:allow-hide",
    "core:window:allow-set-focus",
    "core:window:allow-set-position",
    "core:window:allow-close",
    "core:window:allow-is-visible",
    "core:event:default",
    "core:event:allow-listen",
    "core:event:allow-emit",
    "clipboard-manager:allow-write-text",
    "global-shortcut:allow-register",
    "global-shortcut:allow-unregister",
    "global-shortcut:allow-is-registered",
    "notification:default",
    "shell:allow-open"
  ]
}
```

- [ ] **Step 11: Write main.rs**

```rust
// src-tauri/src/main.rs
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    claude_usage_tray_lib::run();
}
```

- [ ] **Step 12: Write minimal lib.rs (just enough to compile)**

```rust
// src-tauri/src/lib.rs

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 13: Copy tray icon**

```bash
cp /home/ti/claude-usage-widget/plasmoid/contents/icons/claude-logo.png \
   /home/ti/claude-usage-widget/tauri-app/src-tauri/icons/icon.png
```

- [ ] **Step 14: Install npm dependencies**

```bash
cd /home/ti/claude-usage-widget/tauri-app && npm install
```

- [ ] **Step 15: Verify it compiles and opens**

Run: `cd /home/ti/claude-usage-widget/tauri-app && cargo tauri dev`
Expected: A hidden window (nothing visible yet — no tray logic). Ctrl+C to stop. First build takes 2-5 min.

- [ ] **Step 16: Commit scaffold**

```bash
cd /home/ti/claude-usage-widget
git add tauri-app/
git commit -m "feat(tauri): scaffold Tauri v2 project with Vite + vanilla JS"
```

---

## Task 3: Tray Icon + Frameless Popup Window

**Files:**
- Create: `tauri-app/src-tauri/src/tray.rs`
- Modify: `tauri-app/src-tauri/src/lib.rs`

- [ ] **Step 1: Write tray.rs**

```rust
// src-tauri/src/tray.rs
use tauri::{
    image::Image,
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    AppHandle, Manager, Runtime,
};

pub fn create_tray<R: Runtime>(app: &AppHandle<R>) -> tauri::Result<()> {
    let icon = Image::from_path("icons/icon.png")
        .or_else(|_| app.default_window_icon().cloned().ok_or(tauri::Error::AssetNotFound("icon".into())))
        .unwrap_or_else(|_| Image::from_bytes(include_bytes!("../icons/icon.png")).unwrap());

    TrayIconBuilder::with_id("main-tray")
        .icon(icon)
        .tooltip("Claude Usage Monitor")
        .menu_on_left_click(false)
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                rect,
                ..
            } = event
            {
                let app = tray.app_handle();
                if let Some(window) = app.get_webview_window("popup") {
                    if window.is_visible().unwrap_or(false) {
                        let _ = window.hide();
                    } else {
                        // Position popup above/below the tray icon
                        let pos = rect.position;
                        let scale = window.scale_factor().unwrap_or(1.0);
                        let win_width = 400.0;
                        let win_height = 680.0;

                        // Place above the tray icon (for bottom panels)
                        // If icon is in top half of screen, place below instead
                        let screen_height = window
                            .current_monitor()
                            .ok()
                            .flatten()
                            .map(|m| m.size().height as f64 / scale)
                            .unwrap_or(1080.0);

                        let x = (pos.x as f64 / scale) - (win_width / 2.0);
                        let y = if (pos.y as f64 / scale) < screen_height / 2.0 {
                            (pos.y as f64 / scale) + (rect.size.height as f64 / scale)
                        } else {
                            (pos.y as f64 / scale) - win_height
                        };

                        let _ = window.set_position(tauri::LogicalPosition::new(x.max(0.0), y.max(0.0)));
                        let _ = window.show();
                        let _ = window.set_focus();
                    }
                }
            }
        })
        .build(app)?;

    Ok(())
}
```

- [ ] **Step 2: Update lib.rs to use tray**

```rust
// src-tauri/src/lib.rs
mod tray;

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            tray::create_tray(app.handle())?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 3: Verify tray icon appears**

Run: `cd /home/ti/claude-usage-widget/tauri-app && cargo tauri dev`
Expected: Claude logo appears in system tray. Left-click on it: frameless popup appears. Left-click again: popup hides. (Note: left-click may not work on GNOME — that is expected, fixed in Task 9.)

- [ ] **Step 4: Commit tray**

```bash
cd /home/ti/claude-usage-widget
git add tauri-app/src-tauri/src/
git commit -m "feat(tauri): tray icon with frameless popup positioning"
```

---

## Task 4: File Watching + Data Events

**Files:**
- Modify: `tauri-app/src-tauri/src/lib.rs`

- [ ] **Step 1: Add file watcher + initial load to lib.rs**

Replace the full `lib.rs` content with:

```rust
// src-tauri/src/lib.rs
mod tray;

use std::path::PathBuf;
use tauri::Emitter;

fn data_file_path() -> PathBuf {
    dirs::home_dir()
        .expect("could not resolve home directory")
        .join(".claude")
        .join("widget-data.json")
}

fn emit_data(app: &tauri::AppHandle) {
    let path = data_file_path();
    if let Ok(contents) = std::fs::read_to_string(&path) {
        let _ = app.emit("widget-data", contents);
    }
}

fn start_file_watcher(app: tauri::AppHandle) {
    let path = data_file_path();

    std::thread::spawn(move || {
        use notify::{Event, EventKind, RecursiveMode, Watcher};

        // Emit initial data
        emit_data(&app);

        let app_clone = app.clone();
        let mut watcher = notify::recommended_watcher(move |res: Result<Event, _>| {
            if let Ok(event) = res {
                if matches!(event.kind, EventKind::Modify(_) | EventKind::Create(_)) {
                    // Small delay to let the writer finish
                    std::thread::sleep(std::time::Duration::from_millis(50));
                    emit_data(&app_clone);
                }
            }
        })
        .expect("failed to create file watcher");

        // Watch the parent directory (more reliable than watching a single file)
        if let Some(parent) = path.parent() {
            let _ = watcher.watch(parent, RecursiveMode::NonRecursive);
        }

        // Keep the watcher alive
        loop {
            std::thread::sleep(std::time::Duration::from_secs(3600));
        }
    });
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_global_shortcut::Builder::new().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            tray::create_tray(app.handle())?;
            start_file_watcher(app.handle().clone());
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 2: Update main.js to listen for data events**

```js
// src/main.js
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";

let data = {};

listen("widget-data", (event) => {
  try {
    data = JSON.parse(event.payload);
    render(data);
  } catch (e) {
    console.error("Failed to parse widget data:", e);
  }
});

// Close popup when it loses focus
getCurrentWindow().onFocusChanged(({ payload: focused }) => {
  if (!focused) {
    getCurrentWindow().hide();
  }
});

function render(d) {
  const app = document.getElementById("app");
  const preview = JSON.stringify(d, null, 2).slice(0, 500);
  app.textContent = preview + "...";
  app.style.cssText = "color:#ccc;padding:16px;font-size:12px;white-space:pre;font-family:monospace;";
}
```

- [ ] **Step 3: Verify data flows end to end**

Run: `cd /home/ti/claude-usage-widget/tauri-app && cargo tauri dev`
Expected: Click tray icon: popup shows raw JSON text from `widget-data.json`. Click outside: popup hides. When the collector updates the file (every 30s), the popup refreshes.

- [ ] **Step 4: Commit file watcher**

```bash
cd /home/ti/claude-usage-widget
git add tauri-app/
git commit -m "feat(tauri): file watcher emits widget-data.json updates to frontend"
```

---

## Task 5: Theme System + Popup Layout Shell

**Files:**
- Modify: `tauri-app/src/styles/main.css`
- Create: `tauri-app/src/lib/theme.js`
- Modify: `tauri-app/index.html`

- [ ] **Step 1: Write the full theme CSS with card system**

```css
/* src/styles/main.css */

/* -- Reset -- */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

/* -- Theme variables -- */
:root {
  --bg: #1a1a2e;
  --bg-card: rgba(255, 255, 255, 0.05);
  --border: rgba(255, 255, 255, 0.08);
  --text: #e0e0e0;
  --text-dim: rgba(255, 255, 255, 0.4);
  --text-muted: rgba(255, 255, 255, 0.6);

  --amber: #D97706;
  --amber-light: #F59E0B;
  --amber-dim: #92400E;
  --blue: #3B82F6;
  --green: #10B981;
  --red: #EF4444;
  --purple: #6366F1;

  --radius: 10px;
  --gap: 10px;
  --pad: 14px;
  --font: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans", sans-serif;
  --font-size: 13px;
}

@media (prefers-color-scheme: light) {
  :root {
    --bg: #f5f5f7;
    --bg-card: rgba(0, 0, 0, 0.04);
    --border: rgba(0, 0, 0, 0.08);
    --text: #1a1a2e;
    --text-dim: rgba(0, 0, 0, 0.35);
    --text-muted: rgba(0, 0, 0, 0.55);
  }
}

/* -- Base -- */
html, body {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: transparent;
  font-family: var(--font);
  font-size: var(--font-size);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

body { background: var(--bg); border-radius: 12px; }

#app {
  width: 100%;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  scroll-behavior: smooth;
  padding: var(--pad);
}

/* -- Cards -- */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: var(--pad);
  margin-bottom: var(--gap);
}

.card-title {
  font-size: 0.82em;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

/* -- Header -- */
.header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: var(--gap);
}

.mascot-container {
  position: relative;
  width: 64px;
  height: 64px;
  flex-shrink: 0;
}

.mascot-container img {
  position: absolute;
  top: 0;
  left: 0;
  width: 64px;
  height: 64px;
  image-rendering: pixelated;
  transition: opacity 0.15s;
}

.header-info { flex: 1; }

.header-title {
  font-size: 1.15em;
  font-weight: 600;
}

.header-status {
  font-size: 0.82em;
  margin-top: 2px;
}

.header-sub {
  font-size: 0.78em;
  color: var(--text-dim);
  margin-top: 2px;
}

/* -- Session progress ring -- */
.session-ring-wrap {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ring-container {
  position: relative;
  width: 80px;
  height: 80px;
  flex-shrink: 0;
}

.ring-container svg { width: 80px; height: 80px; transform: rotate(-90deg); }

.ring-bg { fill: none; stroke: var(--border); stroke-width: 6; }
.ring-fg { fill: none; stroke-width: 6; stroke-linecap: round; transition: stroke-dashoffset 0.5s ease, stroke 0.3s; }

.ring-label {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 1.5em;
  font-weight: 700;
}

.ring-label small { font-size: 0.5em; font-weight: 400; }

.session-details { flex: 1; }

.session-pct { font-size: 0.9em; }
.session-countdown { font-size: 1.6em; font-weight: 700; font-variant-numeric: tabular-nums; }
.session-countdown-label { font-size: 0.78em; color: var(--text-dim); }

/* -- Status dot -- */
.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}

.status-dot.operational { background: var(--green); }
.status-dot.degraded_performance,
.status-dot.partial_outage { background: var(--amber); }
.status-dot.major_outage { background: var(--red); }

/* -- Health grid -- */
.health-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.health-item {
  font-size: 0.85em;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* -- Weekly bars -- */
.weekly-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.weekly-label { font-size: 0.85em; }
.weekly-pct { font-size: 1.05em; font-weight: 600; }
.weekly-reset { font-size: 0.78em; color: var(--text-dim); }

.bar-track {
  width: 100%;
  height: 6px;
  background: var(--border);
  border-radius: 3px;
  margin-top: 3px;
  margin-bottom: 10px;
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

/* -- Dumbness -- */
.dumb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dumb-score {
  font-size: 1.6em;
  font-weight: 700;
}

.dumb-level {
  font-size: 0.9em;
  font-weight: 500;
}

.dumb-reasons {
  font-size: 0.78em;
  color: var(--text-dim);
  margin-top: 6px;
}

/* -- Utility -- */
.text-green { color: var(--green); }
.text-amber { color: var(--amber); }
.text-red { color: var(--red); }
.text-blue { color: var(--blue); }
.text-dim { color: var(--text-dim); }
.text-muted { color: var(--text-muted); }
.fw-bold { font-weight: 600; }
.mt-4 { margin-top: 4px; }
```

- [ ] **Step 2: Write theme.js**

```js
// src/lib/theme.js

export function colorForPercent(pct) {
  if (pct >= 90) return "var(--red)";
  if (pct >= 70) return "var(--amber)";
  return "var(--green)";
}

export function colorForStatus(status) {
  if (status === "operational") return "var(--green)";
  if (status === "degraded_performance" || status === "partial_outage") return "var(--amber)";
  return "var(--red)";
}

export function dumbLevelColor(level) {
  const map = {
    genius: "var(--green)",
    smart: "var(--blue)",
    slow: "var(--amber)",
    dumb: "var(--amber-light)",
    braindead: "var(--red)",
  };
  return map[level] || "var(--text)";
}
```

- [ ] **Step 3: Update index.html with semantic structure**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Claude Usage Monitor</title>
  <link rel="stylesheet" href="/src/styles/main.css" />
</head>
<body>
  <div id="app">
    <div id="header" class="header"></div>
    <div id="session-card" class="card"></div>
    <div id="weekly-card" class="card"></div>
    <div id="health-card" class="card"></div>
    <div id="dumbness-card" class="card"></div>
  </div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 4: Commit theme + layout**

```bash
cd /home/ti/claude-usage-widget
git add tauri-app/
git commit -m "feat(tauri): theme system (dark/light auto) and card layout CSS"
```

---

## Task 6: Header + Mascot Sprite

**Files:**
- Create: `tauri-app/src/components/header.js`
- Copy sprites to: `tauri-app/public/sprites/`

- [ ] **Step 1: Copy sprite assets**

```bash
cp /home/ti/claude-usage-widget/plasmoid/contents/icons/{claude-logo.png,halo-*.png,smart-*.png,rain-*.png,fire-*.png,skull-*.png,sun-*.png} \
   /home/ti/claude-usage-widget/tauri-app/public/sprites/
```

- [ ] **Step 2: Write header.js with animated mascot**

The mascot uses 5 sprite sets (one per dumbness level), each with 6 animation frames. On data update, we swap the active sprite set and restart the frame timer. All images are preloaded to avoid flicker.

```js
// src/components/header.js

const SPRITE_MAP = {
  genius: { prefix: "halo", frames: 6, interval: 120 },
  smart:  { prefix: "smart", frames: 6, interval: 150 },
  slow:   { prefix: "rain", frames: 6, interval: 150 },
  dumb:   { prefix: "fire", frames: 6, interval: 120 },
  braindead: { prefix: "skull", frames: 6, interval: 200 },
};

let spriteFrame = 0;
let spriteTimer = null;
let currentLevel = null;

// Preload all sprite images to avoid flicker
for (const [, cfg] of Object.entries(SPRITE_MAP)) {
  for (let i = 0; i < cfg.frames; i++) {
    const img = new Image();
    img.src = `/sprites/${cfg.prefix}-${i}.png`;
  }
}

export function renderHeader(el, data) {
  const level = data.dumbness?.level ?? "genius";
  const score = data.dumbness?.score ?? 0;
  const source = data.rateLimits?.source === "api" ? "Live" : "Local";
  const sourceClass = source === "Live" ? "text-green" : "text-dim";
  const plan = data.rateLimits?.plan ?? "";

  const labels = {
    genius: "Genius", smart: "Smart", slow: "Slow",
    dumb: "Dumb", braindead: "Braindead",
  };

  const prefix = SPRITE_MAP[level]?.prefix ?? "halo";

  // Only rebuild DOM if needed (avoid flicker on data refresh)
  if (!el.querySelector("#mascot-img")) {
    const mascotDiv = document.createElement("div");
    mascotDiv.className = "mascot-container";
    mascotDiv.id = "mascot";
    const img = document.createElement("img");
    img.id = "mascot-img";
    img.src = "/sprites/" + prefix + "-0.png";
    img.alt = "Clawd mascot";
    mascotDiv.appendChild(img);

    const infoDiv = document.createElement("div");
    infoDiv.className = "header-info";
    infoDiv.id = "header-info";

    el.replaceChildren(mascotDiv, infoDiv);
  }

  // Update info text via textContent (safe)
  const infoDiv = el.querySelector("#header-info");
  infoDiv.replaceChildren();

  const title = document.createElement("div");
  title.className = "header-title";
  title.textContent = "Claude Usage";
  infoDiv.appendChild(title);

  const statusLine = document.createElement("div");
  statusLine.className = "header-status";
  const levelSpan = document.createElement("span");
  levelSpan.style.color = dumbColor(level);
  levelSpan.textContent = labels[level] ?? level;
  const scoreSpan = document.createElement("span");
  scoreSpan.className = "text-dim";
  scoreSpan.textContent = " \u00B7 " + score;
  statusLine.append(levelSpan, scoreSpan);
  infoDiv.appendChild(statusLine);

  const subLine = document.createElement("div");
  subLine.className = "header-sub";
  const srcSpan = document.createElement("span");
  srcSpan.className = sourceClass;
  srcSpan.textContent = source;
  subLine.appendChild(srcSpan);
  if (plan) {
    const planText = document.createTextNode(" \u00B7 " + plan);
    subLine.appendChild(planText);
  }
  infoDiv.appendChild(subLine);

  startSpriteAnimation(level);
}

function startSpriteAnimation(level) {
  if (level === currentLevel) return; // already running correct animation
  currentLevel = level;

  if (spriteTimer) clearInterval(spriteTimer);
  spriteFrame = 0;

  const cfg = SPRITE_MAP[level];
  if (!cfg) return;

  const img = document.getElementById("mascot-img");
  if (!img) return;

  img.src = "/sprites/" + cfg.prefix + "-0.png";

  spriteTimer = setInterval(() => {
    spriteFrame = (spriteFrame + 1) % cfg.frames;
    img.src = "/sprites/" + cfg.prefix + "-" + spriteFrame + ".png";
  }, cfg.interval);
}

function dumbColor(level) {
  const map = {
    genius: "var(--green)", smart: "var(--blue)", slow: "var(--amber)",
    dumb: "var(--amber-light)", braindead: "var(--red)",
  };
  return map[level] || "var(--text)";
}
```

- [ ] **Step 3: Update main.js to wire header**

```js
// src/main.js
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { renderHeader } from "./components/header.js";

let data = {};

listen("widget-data", (event) => {
  try {
    data = JSON.parse(event.payload);
    render(data);
  } catch (e) { console.error(e); }
});

getCurrentWindow().onFocusChanged(({ payload: focused }) => {
  if (!focused) getCurrentWindow().hide();
});

function render(d) {
  renderHeader(document.getElementById("header"), d);
  // Remaining cards show placeholder text for now
  document.getElementById("session-card").textContent = "Session: " + (d.rateLimits?.session?.percentUsed ?? "--") + "%";
}
```

- [ ] **Step 4: Verify sprites render and animate**

Run: `cargo tauri dev`
Expected: Click tray: popup shows animated mascot sprite + "Claude Usage" title + dumbness level/score + Live/Local source. Sprite animates at the correct rate for the current dumbness level.

- [ ] **Step 5: Commit header + mascot**

```bash
cd /home/ti/claude-usage-widget
git add tauri-app/
git commit -m "feat(tauri): header with animated mascot sprite (5 states, 6 frames each)"
```

---

## Task 7: Session Card — SVG Progress Ring + Live Countdown

**Files:**
- Create: `tauri-app/src/components/session-card.js`
- Create: `tauri-app/src/lib/countdown.js`

- [ ] **Step 1: Write countdown.js**

```js
// src/lib/countdown.js

let targetTime = null;
let tickTimer = null;
let onTick = null;

export function startCountdown(resetsInMinutes, callback) {
  onTick = callback;
  // Anchor to absolute target time (avoids drift from setInterval)
  targetTime = Date.now() + resetsInMinutes * 60 * 1000;

  if (tickTimer) clearInterval(tickTimer);
  tickTimer = setInterval(tick, 1000);
  tick(); // immediate first tick
}

export function stopCountdown() {
  if (tickTimer) clearInterval(tickTimer);
  tickTimer = null;
}

function tick() {
  const remaining = Math.max(0, targetTime - Date.now());
  const totalSec = Math.floor(remaining / 1000);
  const h = Math.floor(totalSec / 3600);
  const m = Math.floor((totalSec % 3600) / 60);
  const s = totalSec % 60;

  const label = h > 0
    ? h + "h " + String(m).padStart(2, "0") + "m " + String(s).padStart(2, "0") + "s"
    : m + "m " + String(s).padStart(2, "0") + "s";

  if (onTick) onTick({ h, m, s, totalSec, label });
}
```

- [ ] **Step 2: Write session-card.js**

The progress ring uses an SVG circle with `stroke-dasharray` set to the circumference and `stroke-dashoffset` animated to represent the fill percentage. The ring is rotated -90deg so 0% starts at 12 o'clock.

```js
// src/components/session-card.js
import { startCountdown } from "../lib/countdown.js";
import { colorForPercent } from "../lib/theme.js";

const RADIUS = 34;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS; // ~213.63

export function renderSessionCard(el, data) {
  const session = data.rateLimits?.session ?? {};
  const pct = session.percentUsed ?? 0;
  const resetMin = session.resetsInMinutes ?? 0;
  const color = colorForPercent(pct);
  const offset = CIRCUMFERENCE * (1 - pct / 100);

  // Build DOM safely
  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Session (5h window)";
  el.appendChild(title);

  const wrap = document.createElement("div");
  wrap.className = "session-ring-wrap";

  // SVG ring
  const ringContainer = document.createElement("div");
  ringContainer.className = "ring-container";

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 80 80");

  const bgCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  bgCircle.setAttribute("class", "ring-bg");
  bgCircle.setAttribute("cx", "40");
  bgCircle.setAttribute("cy", "40");
  bgCircle.setAttribute("r", String(RADIUS));

  const fgCircle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
  fgCircle.setAttribute("class", "ring-fg");
  fgCircle.setAttribute("cx", "40");
  fgCircle.setAttribute("cy", "40");
  fgCircle.setAttribute("r", String(RADIUS));
  fgCircle.setAttribute("stroke", color);
  fgCircle.setAttribute("stroke-dasharray", String(CIRCUMFERENCE));
  fgCircle.setAttribute("stroke-dashoffset", String(offset));

  svg.append(bgCircle, fgCircle);
  ringContainer.appendChild(svg);

  const ringLabel = document.createElement("div");
  ringLabel.className = "ring-label";
  ringLabel.style.color = color;
  ringLabel.textContent = Math.round(pct) + "%";
  ringContainer.appendChild(ringLabel);

  // Details
  const details = document.createElement("div");
  details.className = "session-details";

  const pctLine = document.createElement("div");
  pctLine.className = "session-pct";
  const pctBold = document.createElement("span");
  pctBold.className = "fw-bold";
  pctBold.style.color = color;
  pctBold.textContent = pct.toFixed(1) + "%";
  pctLine.append(pctBold, document.createTextNode(" used"));

  const countdownVal = document.createElement("div");
  countdownVal.className = "session-countdown";
  countdownVal.id = "countdown-value";
  countdownVal.textContent = "--:--";

  const countdownLabel = document.createElement("div");
  countdownLabel.className = "session-countdown-label";
  countdownLabel.textContent = "until reset";

  details.append(pctLine, countdownVal, countdownLabel);
  wrap.append(ringContainer, details);
  el.appendChild(wrap);

  // Start live countdown
  startCountdown(resetMin, ({ label }) => {
    const cdEl = document.getElementById("countdown-value");
    if (cdEl) cdEl.textContent = label;
  });
}
```

- [ ] **Step 3: Wire session card into main.js**

```js
// src/main.js
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { renderHeader } from "./components/header.js";
import { renderSessionCard } from "./components/session-card.js";

let data = {};

listen("widget-data", (event) => {
  try {
    data = JSON.parse(event.payload);
    render(data);
  } catch (e) { console.error(e); }
});

getCurrentWindow().onFocusChanged(({ payload: focused }) => {
  if (!focused) getCurrentWindow().hide();
});

function render(d) {
  renderHeader(document.getElementById("header"), d);
  renderSessionCard(document.getElementById("session-card"), d);
}
```

- [ ] **Step 4: Verify ring + countdown render**

Run: `cargo tauri dev`
Expected: Session card shows circular SVG ring with correct percentage, color threshold (green <70, amber <90, red >=90). Countdown ticks every second in `Xh XXm XXs` format. Ring animates smoothly on data change.

- [ ] **Step 5: Commit session card**

```bash
cd /home/ti/claude-usage-widget
git add tauri-app/
git commit -m "feat(tauri): session card with SVG progress ring and live countdown"
```

---

## Task 8: Weekly Limits + Service Health + Dumbness Cards

**Files:**
- Create: `tauri-app/src/components/weekly-card.js`
- Create: `tauri-app/src/components/health-card.js`
- Create: `tauri-app/src/components/dumbness-card.js`
- Modify: `tauri-app/src/main.js`

- [ ] **Step 1: Write weekly-card.js**

```js
// src/components/weekly-card.js
import { colorForPercent } from "../lib/theme.js";

export function renderWeeklyCard(el, data) {
  const rl = data.rateLimits ?? {};
  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Weekly Limits";
  el.appendChild(title);

  appendWeeklyRow(el, "All models", rl.weeklyAll?.percentUsed ?? 0, rl.weeklyAll?.resetsLabel);
  appendWeeklyRow(el, "Sonnet", rl.weeklySonnet?.percentUsed ?? 0, rl.weeklySonnet?.resetsLabel);
}

function appendWeeklyRow(parent, label, pct, resetLabel) {
  const color = colorForPercent(pct);

  const row = document.createElement("div");
  row.className = "weekly-row";
  const nameSpan = document.createElement("span");
  nameSpan.className = "weekly-label";
  nameSpan.textContent = label;
  const pctSpan = document.createElement("span");
  pctSpan.className = "weekly-pct";
  pctSpan.style.color = color;
  pctSpan.textContent = Math.round(pct) + "%";
  row.append(nameSpan, pctSpan);
  parent.appendChild(row);

  const track = document.createElement("div");
  track.className = "bar-track";
  const fill = document.createElement("div");
  fill.className = "bar-fill";
  fill.style.width = Math.min(100, pct) + "%";
  fill.style.background = color;
  track.appendChild(fill);
  parent.appendChild(track);

  if (resetLabel) {
    const reset = document.createElement("div");
    reset.className = "weekly-reset";
    reset.textContent = "Resets " + resetLabel;
    parent.appendChild(reset);
  }
}
```

- [ ] **Step 2: Write health-card.js**

```js
// src/components/health-card.js

export function renderHealthCard(el, data) {
  const status = data.serviceStatus ?? {};
  const components = status.components ?? [];
  const incidents = status.active_incidents ?? [];

  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Service Health";
  el.appendChild(title);

  const desc = document.createElement("div");
  desc.style.cssText = "font-size:0.88em;margin-bottom:8px;";
  desc.style.color = status.indicator === "none" ? "var(--green)" : "var(--amber)";
  desc.textContent = status.description ?? "Unknown";
  el.appendChild(desc);

  const grid = document.createElement("div");
  grid.className = "health-grid";
  for (const c of components) {
    const item = document.createElement("div");
    item.className = "health-item";
    const dot = document.createElement("span");
    dot.className = "status-dot " + c.status.replace(/ /g, "_");
    const name = document.createTextNode(c.name);
    item.append(dot, name);
    grid.appendChild(item);
  }
  el.appendChild(grid);

  for (const inc of incidents) {
    const box = document.createElement("div");
    box.className = "mt-4";
    box.style.cssText = "font-size:0.82em;padding:8px;background:rgba(239,68,68,0.1);border-radius:6px;";
    const incName = document.createElement("div");
    incName.className = "fw-bold";
    incName.style.color = "var(--red)";
    incName.textContent = inc.name;
    box.appendChild(incName);
    if (inc.latest_update) {
      const incUpdate = document.createElement("div");
      incUpdate.className = "text-muted mt-4";
      incUpdate.textContent = inc.latest_update;
      box.appendChild(incUpdate);
    }
    el.appendChild(box);
  }
}
```

- [ ] **Step 3: Write dumbness-card.js**

```js
// src/components/dumbness-card.js
import { dumbLevelColor } from "../lib/theme.js";

export function renderDumbnessCard(el, data) {
  const d = data.dumbness ?? {};
  const score = d.score ?? 0;
  const level = d.level ?? "genius";
  const reasons = d.reasons ?? [];
  const color = dumbLevelColor(level);

  const labels = {
    genius: "Genius", smart: "Smart", slow: "Degraded",
    dumb: "Dumb", braindead: "Braindead",
  };

  el.replaceChildren();

  const title = document.createElement("div");
  title.className = "card-title";
  title.textContent = "Intelligence Score";
  el.appendChild(title);

  const header = document.createElement("div");
  header.className = "dumb-header";

  const scoreWrap = document.createElement("div");
  const scoreSpan = document.createElement("span");
  scoreSpan.className = "dumb-score";
  scoreSpan.style.color = color;
  scoreSpan.textContent = String(score);
  const maxSpan = document.createElement("span");
  maxSpan.className = "text-dim";
  maxSpan.textContent = "/100";
  scoreWrap.append(scoreSpan, maxSpan);

  const levelSpan = document.createElement("div");
  levelSpan.className = "dumb-level";
  levelSpan.style.color = color;
  levelSpan.textContent = labels[level] ?? level;

  header.append(scoreWrap, levelSpan);
  el.appendChild(header);

  const reasonsDiv = document.createElement("div");
  reasonsDiv.className = "dumb-reasons";
  reasonsDiv.textContent = reasons.length > 0 ? reasons.join(" \u00B7 ") : "No issues detected";
  el.appendChild(reasonsDiv);
}
```

- [ ] **Step 4: Update main.js with all cards**

```js
// src/main.js
import { listen } from "@tauri-apps/api/event";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { renderHeader } from "./components/header.js";
import { renderSessionCard } from "./components/session-card.js";
import { renderWeeklyCard } from "./components/weekly-card.js";
import { renderHealthCard } from "./components/health-card.js";
import { renderDumbnessCard } from "./components/dumbness-card.js";

let data = {};

listen("widget-data", (event) => {
  try {
    data = JSON.parse(event.payload);
    render(data);
  } catch (e) {
    console.error("Failed to parse widget data:", e);
  }
});

getCurrentWindow().onFocusChanged(({ payload: focused }) => {
  if (!focused) getCurrentWindow().hide();
});

function render(d) {
  renderHeader(document.getElementById("header"), d);
  renderSessionCard(document.getElementById("session-card"), d);
  renderWeeklyCard(document.getElementById("weekly-card"), d);
  renderHealthCard(document.getElementById("health-card"), d);
  renderDumbnessCard(document.getElementById("dumbness-card"), d);
}
```

- [ ] **Step 5: Verify all cards render correctly**

Run: `cargo tauri dev`
Expected: Popup shows 4 cards stacked vertically: session (with ring + countdown), weekly limits (with progress bars), service health (with colored dots grid), dumbness (with score + level + reasons). All data matches `widget-data.json`. Scrollable if content overflows.

- [ ] **Step 6: Commit all cards**

```bash
cd /home/ti/claude-usage-widget
git add tauri-app/
git commit -m "feat(tauri): weekly limits, service health, and dumbness score cards"
```

---

## Task 9: Global Shortcut (Linux Workaround)

**Files:**
- Modify: `tauri-app/src-tauri/src/lib.rs`

- [ ] **Step 1: Add global shortcut registration to lib.rs**

Add this function after `start_file_watcher`:

```rust
fn register_global_shortcut(app: &tauri::AppHandle) {
    use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut};

    // Super+Shift+C to toggle the popup
    let shortcut: Shortcut = "Super+Shift+KeyC".parse().expect("invalid shortcut");

    let app_clone = app.clone();
    app.global_shortcut().on_shortcut(shortcut, move |_app, _shortcut, _event| {
        if let Some(window) = app_clone.get_webview_window("popup") {
            if window.is_visible().unwrap_or(false) {
                let _ = window.hide();
            } else {
                // Center on screen (no tray position available on Linux)
                let _ = window.center();
                let _ = window.show();
                let _ = window.set_focus();
            }
        }
    }).expect("failed to register global shortcut");
}
```

Update the `setup` closure in the `run()` function:

```rust
.setup(|app| {
    tray::create_tray(app.handle())?;
    start_file_watcher(app.handle().clone());
    register_global_shortcut(app.handle());
    Ok(())
})
```

- [ ] **Step 2: Verify shortcut works**

Run: `cargo tauri dev`
Expected: Press `Super+Shift+C`: popup appears centered on screen. Press again: hides. This works even on GNOME where tray click events are not emitted.

- [ ] **Step 3: Commit global shortcut**

```bash
cd /home/ti/claude-usage-widget
git add tauri-app/
git commit -m "feat(tauri): global shortcut Super+Shift+C to toggle popup (Linux workaround)"
```

---

## Task 10: End-to-End Smoke Test

**Files:** None (verification only)

- [ ] **Step 1: Run the full app**

```bash
cd /home/ti/claude-usage-widget/tauri-app && cargo tauri dev
```

- [ ] **Step 2: Verify checklist**

| Test | Expected |
|------|----------|
| Tray icon visible | Claude logo in system tray |
| Left-click tray (KDE) | Popup appears near tray icon |
| Click outside popup | Popup hides |
| `Super+Shift+C` | Popup toggles (centered) |
| Session ring | Correct %, correct color (green/amber/red) |
| Countdown | Ticks every second, format `Xh XXm XXs` |
| Mascot | Correct sprite for dumbness level, animated frames |
| Weekly card | All-models and Sonnet % with progress bars |
| Health card | Grid of component dots, all green when operational |
| Dumbness card | Score, level, reasons (or "No issues") |
| Data refresh | Manually run `~/.local/bin/claude-usage-collector.py` then popup updates |
| Dark/light theme | Switch system theme then popup follows |
| Scroll | If content overflows, smooth scroll works |

- [ ] **Step 3: Final commit**

```bash
cd /home/ti/claude-usage-widget
git add tauri-app/
git commit -m "feat(tauri): core MVP — tray app with session, weekly, health, dumbness cards"
```

---

## Next Plans (not covered here)

**Plan 2: Complete UI**
- Credits card (balance, auto-reload, extra usage)
- Performance metrics card (burn rate, error rate, latency, avg response)
- Model distribution bar (horizontal stacked)
- 7-day activity chart (CSS bar chart)
- Peak hours chart (24-column)
- Quick actions (open claude.ai, open status page, copy stats)
- Footer (version, streak counter)

**Plan 3: Collector Hardening**
- Multi-OS Firefox cookie paths (snap, flatpak, Windows)
- Chrome cookie extraction (DPAPI on Windows, libsecret on Linux)
- Cross-platform notification dispatch
- Windows Task Scheduler setup

**Plan 4: Packaging + CI**
- GitHub Actions matrix (Linux AppImage + .deb, Windows NSIS, macOS .dmg)
- Auto-updater via tauri-plugin-updater
- Auto-start via tauri-plugin-autostart
