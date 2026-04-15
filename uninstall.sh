#!/bin/bash
set -euo pipefail

echo "Removing Claude Usage Widget..."

systemctl --user disable --now claude-usage-collector.timer 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/claude-usage-collector.service"
rm -f "$HOME/.config/systemd/user/claude-usage-collector.timer"
systemctl --user daemon-reload 2>/dev/null || true

rm -rf "$HOME/.local/share/plasma/plasmoids/org.kde.plasma.claudeusage"
rm -f "$HOME/.local/bin/claude-usage-collector.py"
rm -f "$HOME/.claude/widget-data.json"
rm -f "$HOME/.claude/widget-config.json"

echo "Done. Remove the widget from your panel manually if still visible."
