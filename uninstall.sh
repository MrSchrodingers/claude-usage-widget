#!/bin/bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}═══════════════════════════════════════════${NC}"
echo -e "${BOLD}  Claude Usage Monitor - Uninstaller       ${NC}"
echo -e "${BOLD}═══════════════════════════════════════════${NC}"
echo ""

# ── Kill running tray app ──
if pgrep -f "claude-usage-tray" &>/dev/null; then
    pkill -f "claude-usage-tray" 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Stopped running tray app"
fi

# ── Remove systemd timer ──
if systemctl --user is-active claude-usage-collector.timer &>/dev/null; then
    systemctl --user disable --now claude-usage-collector.timer 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} Disabled systemd timer"
fi
rm -f "$HOME/.config/systemd/user/claude-usage-collector.service"
rm -f "$HOME/.config/systemd/user/claude-usage-collector.timer"
systemctl --user daemon-reload 2>/dev/null || true

# ── Remove plasmoid ──
if [ -d "$HOME/.local/share/plasma/plasmoids/org.kde.plasma.claudeusage" ]; then
    rm -rf "$HOME/.local/share/plasma/plasmoids/org.kde.plasma.claudeusage"
    echo -e "  ${GREEN}✓${NC} Removed KDE Plasmoid"
fi

# ── Remove icon ──
rm -f "$HOME/.local/share/icons/hicolor/48x48/apps/claude-logo.png"

# ── Remove binaries ──
for f in claude-usage-collector.py claude-usage-tray; do
    if [ -f "$HOME/.local/bin/$f" ]; then
        rm -f "$HOME/.local/bin/$f"
        echo -e "  ${GREEN}✓${NC} Removed ~/.local/bin/$f"
    fi
done

# ── Remove autostart ──
if [ -f "$HOME/.config/autostart/claude-usage-tray.desktop" ]; then
    rm -f "$HOME/.config/autostart/claude-usage-tray.desktop"
    echo -e "  ${GREEN}✓${NC} Removed autostart entry"
fi

# ── Remove data files ──
for f in widget-data.json widget-config.json widget-status-prev.json widget-stats-cache.json; do
    rm -f "$HOME/.claude/$f"
done
echo -e "  ${GREEN}✓${NC} Removed data files from ~/.claude/"

# ── Remove temp files ──
rm -f /tmp/claude_chrome_cookies.sqlite*
rm -f /tmp/claude_cookies.sqlite*

echo ""
echo -e "${GREEN}  Uninstall complete.${NC}"
echo ""
echo "  If the plasmoid is still visible, right-click it → Remove."
echo ""
