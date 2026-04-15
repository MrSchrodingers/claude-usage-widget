#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════
# Claude Usage Widget - Installer for KDE Plasma 6
# ═══════════════════════════════════════════════════

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PLASMOID_DIR="$HOME/.local/share/plasma/plasmoids/org.kde.plasma.claudeusage"
COLLECTOR="$HOME/.local/bin/claude-usage-collector.py"
SYSTEMD_DIR="$HOME/.config/systemd/user"

RED='\033[0;31m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${BOLD}═══════════════════════════════════════${NC}"
echo -e "${BOLD}  Claude Usage Monitor - KDE Plasma 6  ${NC}"
echo -e "${BOLD}═══════════════════════════════════════${NC}"
echo ""

# ── Pre-flight checks ──
echo -e "${AMBER}[1/6]${NC} Checking requirements..."

if ! command -v plasmashell &>/dev/null; then
    echo -e "${RED}ERROR:${NC} KDE Plasma not found. This widget requires Plasma 6."
    exit 1
fi

PLASMA_VER=$(plasmashell --version 2>/dev/null | grep -oP '\d+' | head -1)
if [ "$PLASMA_VER" -lt 6 ] 2>/dev/null; then
    echo -e "${RED}ERROR:${NC} Plasma 6+ required (found Plasma $PLASMA_VER)"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}ERROR:${NC} Python 3 is required."
    exit 1
fi

echo -e "  ${GREEN}✓${NC} Plasma $(plasmashell --version 2>/dev/null | grep -oP '[\d.]+')"
echo -e "  ${GREEN}✓${NC} Python $(python3 --version 2>/dev/null | grep -oP '[\d.]+')"

# ── Install collector ──
echo ""
echo -e "${AMBER}[2/6]${NC} Installing data collector..."
mkdir -p "$HOME/.local/bin"
cp "$REPO_DIR/scripts/claude-usage-collector.py" "$COLLECTOR"
chmod +x "$COLLECTOR"
echo -e "  ${GREEN}✓${NC} $COLLECTOR"

# ── Install plasmoid ──
echo ""
echo -e "${AMBER}[3/6]${NC} Installing plasmoid..."
rm -rf "$PLASMOID_DIR"
mkdir -p "$PLASMOID_DIR/contents/"{ui,icons,config}
cp "$REPO_DIR/plasmoid/metadata.json" "$PLASMOID_DIR/"
cp "$REPO_DIR/plasmoid/contents/ui/main.qml" "$PLASMOID_DIR/contents/ui/"
cp "$REPO_DIR/plasmoid/contents/icons/"* "$PLASMOID_DIR/contents/icons/"

# Install icon for About dialog
mkdir -p "$HOME/.local/share/icons/hicolor/48x48/apps/"
cp "$REPO_DIR/plasmoid/contents/icons/claude-logo.png" "$HOME/.local/share/icons/hicolor/48x48/apps/claude-logo.png"
echo -e "  ${GREEN}✓${NC} Plasmoid installed to $PLASMOID_DIR"

# ── Install systemd timer ──
echo ""
echo -e "${AMBER}[4/6]${NC} Setting up auto-refresh (systemd timer)..."
mkdir -p "$SYSTEMD_DIR"
cp "$REPO_DIR/scripts/claude-usage-collector.service" "$SYSTEMD_DIR/"
cp "$REPO_DIR/scripts/claude-usage-collector.timer" "$SYSTEMD_DIR/"
systemctl --user daemon-reload
systemctl --user enable --now claude-usage-collector.timer
echo -e "  ${GREEN}✓${NC} Timer enabled (refreshes every 30s)"

# ── Setup / Auth ──
echo ""
echo -e "${AMBER}[5/6]${NC} Configuring authentication..."
python3 "$COLLECTOR" --setup

# ── First run ──
echo ""
echo -e "${AMBER}[6/6]${NC} Generating initial data..."
python3 "$COLLECTOR"

echo ""
echo -e "${BOLD}═══════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation Complete!${NC}"
echo -e "${BOLD}═══════════════════════════════════════${NC}"
echo ""
echo "  To add the widget to your panel:"
echo "    1. Right-click your KDE panel"
echo "    2. Click 'Add Widgets...'"
echo "    3. Search for 'Claude Usage Monitor'"
echo "    4. Drag it to your panel"
echo ""
echo "  The widget updates every 30 seconds with live data from claude.ai."
echo "  It reads your browser session cookies automatically — no API keys needed."
echo ""
