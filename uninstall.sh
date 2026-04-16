#!/bin/bash
set -euo pipefail

echo "Removing Claude Usage Monitor..."

# Stop and remove systemd timer
systemctl --user disable --now claude-usage-collector.timer 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/claude-usage-collector.service"
rm -f "$HOME/.config/systemd/user/claude-usage-collector.timer"
systemctl --user daemon-reload 2>/dev/null || true

# Remove plasmoid
rm -rf "$HOME/.local/share/plasma/plasmoids/org.kde.plasma.claudeusage"

# Remove binaries
rm -f "$HOME/.local/bin/claude-usage-collector.py"
rm -f "$HOME/.local/bin/claude-usage-tray"

# Remove autostart
rm -f "$HOME/.config/autostart/claude-usage-tray.desktop"

# Remove data
rm -f "$HOME/.claude/widget-data.json"
rm -f "$HOME/.claude/widget-config.json"
rm -f "$HOME/.claude/widget-status-prev.json"

echo "Done. Remove the widget from your panel manually if still visible."
