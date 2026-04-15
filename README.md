# Claude Usage Monitor - KDE Plasma Widget

A KDE Plasma 6 widget that shows your **Claude AI usage limits** in real-time, directly in your panel.

![Claude Usage Widget](screenshots/widget.png)

## Features

- **Live usage limits** from claude.ai API (session, weekly, Sonnet-only)
- **Session countdown** — shows when your 5-hour window resets
- **Weekly breakdown** — all models + Sonnet-only with reset dates
- **Prepaid balance** — shows your current credits
- **7-day activity chart** — local token usage trend from Claude Code
- **Auto-refresh** every 30 seconds via systemd timer
- **Official Claude logos** — Clawd mascot + Claude logo
- **Zero API keys needed** — authenticates via your browser session

## Requirements

- **KDE Plasma 6** (Fedora 40+, Kubuntu 24.04+, Arch, etc.)
- **Python 3.8+**
- **Firefox or Chromium** — logged in to [claude.ai](https://claude.ai)
- **Claude Code** installed (for local activity data)

## Installation

```bash
git clone https://github.com/MrSchrodingers/claude-usage-widget.git
cd claude-usage-widget
chmod +x install.sh
./install.sh
```

The installer will:
1. Install the data collector to `~/.local/bin/`
2. Install the Plasma widget
3. Set up a systemd timer for auto-refresh
4. Auto-detect your claude.ai organization from browser cookies
5. Verify API connectivity

### Add to Panel

1. Right-click your KDE panel
2. Click **"Add Widgets..."**
3. Search for **"Claude Usage Monitor"**
4. Drag it to your panel

## How It Works

```
Browser cookies (Firefox/Chrome)
        │
        ▼
claude-usage-collector.py ──▶ claude.ai/api/organizations/{org}/usage
        │                              │
        │                              ▼
        │                     { five_hour: { utilization: 13 },
        │                       seven_day: { utilization: 54 },
        │                       seven_day_sonnet: { utilization: 2 } }
        │
        ├──▶ ~/.claude/projects/**/*.jsonl  (local token data)
        │
        ▼
~/.claude/widget-data.json ──▶ Plasma Widget (QML)
```

### Authentication

The widget reads session cookies from your browser automatically. No API keys or passwords are stored.

- **Firefox**: reads from `~/.mozilla/firefox/*/cookies.sqlite`
- **Chromium/Chrome**: reads from `~/.config/google-chrome/Default/Cookies` (unencrypted values only)

You must be logged in to [claude.ai](https://claude.ai) in your browser. The session refreshes automatically as long as you use Claude in your browser periodically.

### Data Sources

| Data | Source | Scope |
|------|--------|-------|
| Usage limits (%) | claude.ai API | Your entire account (all devices) |
| Reset timers | claude.ai API | Your entire account |
| Balance | claude.ai API | Your organization |
| 7-day activity | Local JSONL files | This machine only |
| Lifetime stats | Local stats-cache | This machine only |

## Uninstall

```bash
cd claude-usage-widget
chmod +x uninstall.sh
./uninstall.sh
```

Then remove the widget from your panel manually.

## Configuration

Config is stored at `~/.claude/widget-config.json`:

```json
{
  "org_id": "auto-detected-uuid",
  "setup_done": true
}
```

To re-run setup:
```bash
~/.local/bin/claude-usage-collector.py --setup
```

## Troubleshooting

### Widget shows "--" or no data
- Make sure you're logged in to [claude.ai](https://claude.ai) in Firefox/Chrome
- Run `~/.local/bin/claude-usage-collector.py --verbose` to check
- Run `~/.local/bin/claude-usage-collector.py --setup` to re-configure

### Widget shows "Local" instead of "Live"
- Your browser session may have expired — log in to claude.ai again
- Cloudflare may be blocking requests — visit claude.ai to refresh the `cf_clearance` cookie

### Timer not running
```bash
systemctl --user status claude-usage-collector.timer
systemctl --user enable --now claude-usage-collector.timer
```

### Widget not appearing in "Add Widgets"
```bash
kpackagetool6 --type Plasma/Applet --list | grep claude
```

## Supported Plans

The widget auto-detects your plan from Claude Code credentials:

| Plan | Features shown |
|------|---------------|
| Max (20x) | Session %, Weekly all %, Weekly Sonnet %, Balance |
| Max (5x) | Session %, Weekly all %, Weekly Sonnet %, Balance |
| Pro | Session %, Weekly all % |
| Free | Session % |

## License

MIT
