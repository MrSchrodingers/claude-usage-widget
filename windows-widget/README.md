# Windows AppBar Widget

Pure-Python Windows implementation of the Claude Usage Monitor UI, using the
Win32 **AppBar** API (`SHAppBarMessage`) to dock a compact strip at the top of
the screen. Clicking the strip opens the full popup with all 13 sections,
visually matching `screenshots/widget.gif`.

Built as an alternative to the `tauri-app/` build path, which requires the
Rust + Node.js + MSVC + WebView2 toolchain and did not produce a working
Windows build at the time of writing.

## How it compares

| | Tauri app | This widget |
|---|---|---|
| Compile toolchain | Rust + Node + MSVC + WebView2 | Python only |
| Always-visible strip | ❌ (tray icon only) | ✅ (AppBar, reserves screen space) |
| Popup with 13 sections | ✅ | ✅ |
| Size on disk | ~50 MB | ~8 KB code + ~120 MB PySide6 |
| Installer | `install.ps1` → `cargo tauri build` | `install-windows.ps1` (no admin) |

The data source is identical: both read from `~/.claude/widget-data.json`
written by `scripts/claude-usage-collector.py`.

## Install

```powershell
.\install-windows.ps1
```

What the installer does (none of which needs admin):

1. Finds Python 3.10+ on PATH
2. `pip install` PySide6, pywin32, cryptography
3. Copies `scripts/claude-usage-collector.py` → `%LOCALAPPDATA%\ClaudeUsageMonitor\`
4. Copies `windows-widget/` → `%LOCALAPPDATA%\ClaudeUsageMonitor\widget\`
5. Registers Scheduled Task `ClaudeUsageCollector` running every 60s
6. Seeds `~/.claude/widget-data.json`
7. Creates a Startup shortcut to `pythonw.exe main.py`
8. Launches the widget

## Uninstall

```powershell
.\uninstall-windows.ps1
```

Removes only artifacts this installer created. Does not touch other files in
`~/.claude/`.

## Architecture

```
┌─ claude-usage-collector.py (every 60s, Scheduled Task)
│     reads browser cookies, calls claude.ai API,
│     writes ~/.claude/widget-data.json
│
└─ main.py (startup, always running)
      │
      ├─ DataReader       → QFileSystemWatcher + polling on widget-data.json
      ├─ CompactBar       → QWidget docked via SHAppBarMessage on TOP edge
      ├─ PopupWindow      → frameless 400×900 window with 13 sections
      └─ QSystemTrayIcon  → secondary access point + Quit menu
```

## Requirements

- **Windows 10 22H2 / Windows 11**
- **Python 3.10+** with `pythonw.exe` (from python.org or Microsoft Store)

## Troubleshooting

**The strip does not appear**
Check if `main.py` is running: `Get-Process pythonw`. Run it manually:
`pythonw "%LOCALAPPDATA%\ClaudeUsageMonitor\widget\main.py"`.

**The widget shows `--%` and `Offline`**
The collector could not authenticate. Make sure you're logged into
https://claude.ai in Firefox, Chrome, Chromium, or Brave. Then run:
`python "%LOCALAPPDATA%\ClaudeUsageMonitor\claude-usage-collector.py" --verbose`

**The strip hides part of a maximized window**
This is the correct AppBar behavior — the shell reserves the area so other
windows don't overlap it. Resize via `thickness=` in `main.py` if needed.

**Only one copy runs**
Enforced by a named mutex (`ClaudeUsageWidget_SingleInstance`). Existing
instance wins; second launch exits silently.
