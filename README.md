<div align="center">

# Claude Usage Monitor

### KDE Plasma 6 Widget

**Real-time Claude AI usage limits, service health, intelligence score, and spending tracker directly in your taskbar.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![KDE Plasma 6](https://img.shields.io/badge/KDE_Plasma-6.0+-blue.svg)](https://kde.org/plasma-desktop/)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-green.svg)](https://python.org)
[![Claude API](https://img.shields.io/badge/Claude-API-D97757.svg)](https://claude.ai)

<br>

<img src="screenshots/widget.gif" alt="Claude Usage Widget" width="427"/>

<br>

<img src="screenshots/panel.png" alt="Panel compact view"/>

</div>

---

## Highlights

<table>
<tr>
<td width="50%">

### Usage Monitoring
- Circular progress ring with live countdown (seconds)
- Session, weekly all-models, and weekly Sonnet limits
- Prepaid credits balance with auto-reload status
- Extra Usage: enabled/disabled, monthly limit, used/remaining

</td>
<td width="50%">

### Intelligence Score
- Composite 0-100 "Dumbness Score" detects degradation
- 5 animated pixel art mascot states
- Factors: service health, rate limits, API errors, config
- Predictive alert: "limit in ~Xh at current rate"

</td>
</tr>
<tr>
<td>

### Service Health
- Real-time from status.claude.com (Statuspage API)
- Component status: claude.ai, Platform, API, Claude Code
- Active incident details with latest update text
- KDE desktop notifications on status changes

</td>
<td>

### Performance Metrics
- Token burn rate (output tokens/hour)
- API error tracking (429/529/overloaded in 2h window)
- Average response quality (tokens per response)
- Average latency (user-to-assistant response time)
- Model distribution bar (Opus/Sonnet/Haiku split)

</td>
</tr>
</table>

---

## Mascot States

The Clawd mascot changes based on Claude's performance score:

| Score | Level | Mascot | Trigger |
|:-----:|:-----:|:------:|:--------|
| 0-9 | **Genius** | Crown + sparkles | Everything perfect |
| 10-24 | **Smart** | Coffee cup + steam | Minor config issues |
| 25-49 | **Slow** | Rain cloud + drops | Service degraded |
| 50-74 | **Dumb** | Fire flames | Major issues + rate limit pressure |
| 75-100 | **Braindead** | Tombstone + ghost Clawd | Critical outage |

### Dumbness Score Factors

| Factor | Points | Source |
|--------|:------:|--------|
| Service health | 0-40 | status.claude.com |
| Session utilization | 0-25 | claude.ai API |
| API errors (2h window) | 0-20 | Local JSONL files |
| Adaptive Thinking ON | 8 | ~/.claude/settings.json |
| 1M Context OFF | 3 | ~/.claude/settings.json |

> **Why is Adaptive Thinking ON a penalty?** With Adaptive Thinking enabled, Claude sometimes allocates zero reasoning tokens on complex tasks, causing lazy/shallow responses. [Learn more](https://dev.to/shuicici/claude-codes-feb-mar-2026-updates-quietly-broke-complex-engineering-heres-the-technical-5b4h)

---

## Requirements

- **KDE Plasma 6** (Fedora 40+, Kubuntu 24.04+, Arch, etc.)
- **Python 3.8+** with Pillow (`pip install pillow`)
- **Firefox or Chromium** logged in to [claude.ai](https://claude.ai)
- **Claude Code** installed (for local activity data)

---

## Installation

```bash
git clone https://github.com/MrSchrodingers/claude-usage-widget.git
cd claude-usage-widget
chmod +x install.sh
./install.sh
```

The installer will:
1. Check Plasma 6 and Python 3
2. Install the data collector to `~/.local/bin/`
3. Install the Plasma widget to `~/.local/share/plasma/plasmoids/`
4. Set up a systemd timer (refreshes every 30s)
5. Auto-detect your claude.ai organization from browser cookies
6. Generate initial data

### Add to Panel

1. Right-click your KDE panel
2. Click **"Add Widgets..."**
3. Search for **"Claude Usage Monitor"**
4. Drag it to your panel

---

## How It Works

```
Browser cookies (Firefox/Chromium)
        |
        v
claude-usage-collector.py (every 30s)
        |
        |--- claude.ai/api/.../usage
        |       Session %, weekly limits, reset timers
        |
        |--- claude.ai/api/.../prepaid/credits
        |       Balance, currency, auto-reload
        |
        |--- claude.ai/api/.../overage_spend_limit
        |       Extra usage: enabled, limit, used
        |
        |--- claude.ai/api/.../overage_credit_grant
        |       Credit grant status
        |
        |--- status.claude.com/api/v2/summary.json
        |       Service health, components, incidents
        |
        |--- ~/.claude/settings.json
        |       Adaptive thinking, effort level
        |
        |--- ~/.claude/projects/**/*.jsonl
        |       Errors, tokens, latency, sessions
        |
        v
~/.claude/widget-data.json ---> Plasma Widget (QML)
```

### Authentication

The widget reads session cookies from your browser. No API keys or passwords stored.

- **Firefox**: `~/.mozilla/firefox/*/cookies.sqlite`
- **Chromium**: `~/.config/google-chrome/Default/Cookies`

### Data Sources

| Data | Source | Scope |
|------|--------|-------|
| Session/weekly usage | claude.ai API | All devices |
| Reset timers | claude.ai API | All devices |
| Prepaid credits | claude.ai API | Organization |
| Extra usage limits | claude.ai API | Organization |
| Service health | status.claude.com | Anthropic infra |
| Error rate | Local JSONL | This machine |
| Burn rate | Local JSONL | This machine |
| Avg response/latency | Local JSONL | This machine |
| Adaptive Thinking | Local settings | This machine |
| Dumbness score | Composite | Combined |
| 7-day chart | Local JSONL | This machine |
| Peak hours | Local stats-cache | This machine |

---

## Features

### Live Countdown
The session reset timer counts down in real-time (seconds), not just every 30s refresh.

### Circular Progress Ring
Replaces the traditional progress bar with an animated circular ring for the session limit.

### Model Distribution
Horizontal stacked bar showing Opus/Sonnet/Haiku usage split with color legend.

### Peak Hours Chart
24-column mini bar chart showing your usage patterns by hour. Work hours in amber, night hours in blue.

### Quick Actions
- **claude.ai** - Open Claude in browser
- **Status** - Open status.claude.com
- **Copy Stats** - Copy formatted stats to clipboard

### Streak Counter
Shows consecutive days of Claude usage in the footer.

### Easter Egg
Click the Clawd mascot 5 times rapidly to cycle through all mascot states. Returns to live data after 30s.

---

## Adaptive Thinking Workaround

If Claude feels "lazy" or gives shallow answers:

```json
// ~/.claude/settings.json
{
  "effortLevel": "high",
  "env": {
    "CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING": "1"
  }
}
```

This forces full reasoning on every turn. Trade-off: consumes rate limit faster, but significantly better output quality.

---

## Testing States

The collector supports a `--test-state` flag for previewing mascot states:

```bash
~/.local/bin/claude-usage-collector.py --test-state=genius
~/.local/bin/claude-usage-collector.py --test-state=smart
~/.local/bin/claude-usage-collector.py --test-state=slow
~/.local/bin/claude-usage-collector.py --test-state=dumb
~/.local/bin/claude-usage-collector.py --test-state=braindead
```

---

## Uninstall

```bash
cd claude-usage-widget
chmod +x uninstall.sh
./uninstall.sh
```

---

## Troubleshooting

### Widget shows `--` or no data
- Make sure you're logged in to [claude.ai](https://claude.ai) in Firefox/Chrome
- Run `~/.local/bin/claude-usage-collector.py --verbose` to inspect output
- Run `~/.local/bin/claude-usage-collector.py --setup` to re-configure

### Widget shows `Offline` instead of `Live`
- Your browser session may have expired - log in to claude.ai again
- Visit claude.ai to refresh the `cf_clearance` cookie

### Claude feels "dumb" or lazy
1. Check the Dumbness Score in the widget
2. Disable Adaptive Thinking (see workaround above)
3. Check status.claude.com for incidents
4. If session > 80%, wait for the 5h window to reset

### Timer not running
```bash
systemctl --user status claude-usage-collector.timer
systemctl --user enable --now claude-usage-collector.timer
```

---

## Supported Plans

| Plan | Features |
|------|----------|
| Max (20x) | All features, full limits tracking |
| Max (5x) | All features, full limits tracking |
| Pro | Session %, weekly %, dumbness score |
| Free | Session %, dumbness score |

---

## Tech Stack

- **Widget**: QML (Qt 6) + Kirigami + PlasmaComponents3
- **Data collector**: Python 3 (stdlib only, no pip dependencies)
- **Sprite generator**: Python 3 + Pillow
- **Timer**: systemd user timer (30s interval)
- **APIs**: claude.ai (authenticated), status.claude.com (public)

---

<div align="center">

**MIT License** | Made by [MrSchrodingers](https://github.com/MrSchrodingers)

</div>
