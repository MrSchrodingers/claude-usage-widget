#!/bin/bash
set -euo pipefail

# ═══════════════════════════════════════════════════
# Claude Usage Monitor - Universal Linux Installer
# Supports: KDE Plasma 6 (plasmoid) + any DE (tray app)
# ═══════════════════════════════════════════════════

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
COLLECTOR="$HOME/.local/bin/claude-usage-collector.py"
SYSTEMD_DIR="$HOME/.config/systemd/user"
TAURI_DIR="$REPO_DIR/tauri-app"

RED='\033[0;31m'
GREEN='\033[0;32m'
AMBER='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

header() {
    echo ""
    echo -e "${BOLD}═══════════════════════════════════════════${NC}"
    echo -e "${BOLD}  Claude Usage Monitor - Linux Installer   ${NC}"
    echo -e "${BOLD}═══════════════════════════════════════════${NC}"
    echo ""
}

detect_env() {
    HAS_KDE=false
    HAS_RUST=false
    HAS_NODE=false
    HAS_PYTHON=false
    DISTRO="unknown"

    command -v python3 &>/dev/null && HAS_PYTHON=true
    command -v plasmashell &>/dev/null && HAS_KDE=true
    command -v cargo &>/dev/null && command -v rustc &>/dev/null && HAS_RUST=true
    command -v node &>/dev/null && command -v npm &>/dev/null && HAS_NODE=true

    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [[ "$ID" == "fedora" ]] || [[ "${ID_LIKE:-}" == *"fedora"* ]]; then
            DISTRO="fedora"
        elif [[ "$ID" == "ubuntu" ]] || [[ "$ID" == "debian" ]] || [[ "${ID_LIKE:-}" == *"ubuntu"* ]] || [[ "${ID_LIKE:-}" == *"debian"* ]]; then
            DISTRO="debian"
        elif [[ "$ID" == "arch" ]] || [[ "${ID_LIKE:-}" == *"arch"* ]]; then
            DISTRO="arch"
        fi
    fi
}

install_deps() {
    echo -e "${AMBER}[1/6]${NC} Checking dependencies..."

    if ! $HAS_PYTHON; then
        echo -e "  ${RED}!${NC} Python 3 not found. Installing..."
        case $DISTRO in
            fedora)  sudo dnf install -y python3 ;;
            debian)  sudo apt-get install -y python3 ;;
            arch)    sudo pacman -S --noconfirm python ;;
            *)       echo -e "  ${RED}ERROR:${NC} Install Python 3 manually."; exit 1 ;;
        esac
    fi
    echo -e "  ${GREEN}✓${NC} Python $(python3 --version 2>/dev/null | grep -oP '[\d.]+')"

    # cryptography for Chrome cookie decryption
    if ! python3 -c "import cryptography" 2>/dev/null; then
        echo -e "  ${DIM}  Installing cryptography for Chrome cookies...${NC}"
        pip3 install --user --quiet cryptography 2>/dev/null || python3 -m pip install --user --quiet cryptography 2>/dev/null || true
    fi

    # Chrome keyring tools
    if $HAS_KDE; then
        if ! command -v kwallet-query &>/dev/null; then
            echo -e "  ${DIM}  Installing kwallet tools for Chrome cookies...${NC}"
            case $DISTRO in
                fedora) sudo dnf install -y kwalletmanager 2>/dev/null || true ;;
                debian) sudo apt-get install -y kwalletmanager 2>/dev/null || true ;;
            esac
        fi
    else
        if ! command -v secret-tool &>/dev/null; then
            echo -e "  ${DIM}  Installing secret-tool for Chrome cookies...${NC}"
            case $DISTRO in
                fedora) sudo dnf install -y libsecret 2>/dev/null || true ;;
                debian) sudo apt-get install -y libsecret-tools 2>/dev/null || true ;;
            esac
        fi
    fi
}

install_collector() {
    echo ""
    echo -e "${AMBER}[2/6]${NC} Installing data collector..."
    mkdir -p "$HOME/.local/bin"
    cp "$REPO_DIR/scripts/claude-usage-collector.py" "$COLLECTOR"
    chmod +x "$COLLECTOR"
    echo -e "  ${GREEN}✓${NC} $COLLECTOR"
}

install_timer() {
    echo ""
    echo -e "${AMBER}[3/6]${NC} Setting up auto-refresh (systemd timer)..."
    mkdir -p "$SYSTEMD_DIR"
    cp "$REPO_DIR/scripts/claude-usage-collector.service" "$SYSTEMD_DIR/"
    cp "$REPO_DIR/scripts/claude-usage-collector.timer" "$SYSTEMD_DIR/"
    systemctl --user daemon-reload
    systemctl --user enable --now claude-usage-collector.timer
    echo -e "  ${GREEN}✓${NC} Timer enabled (refreshes every 30s)"
}

install_plasmoid() {
    local PLASMOID_DIR="$HOME/.local/share/plasma/plasmoids/org.kde.plasma.claudeusage"

    echo ""
    echo -e "${AMBER}[4/6]${NC} Installing KDE Plasmoid..."

    PLASMA_VER=$(plasmashell --version 2>/dev/null | grep -oP '\d+' | head -1 || echo "0")
    if [ "$PLASMA_VER" -lt 6 ] 2>/dev/null; then
        echo -e "  ${RED}!${NC} Plasma 6+ required (found Plasma $PLASMA_VER). Skipping plasmoid."
        return
    fi

    rm -rf "$PLASMOID_DIR"
    mkdir -p "$PLASMOID_DIR/contents/"{ui,icons,config}
    cp "$REPO_DIR/plasmoid/metadata.json" "$PLASMOID_DIR/"
    cp "$REPO_DIR/plasmoid/contents/ui/main.qml" "$PLASMOID_DIR/contents/ui/"
    cp "$REPO_DIR/plasmoid/contents/icons/"* "$PLASMOID_DIR/contents/icons/"
    mkdir -p "$HOME/.local/share/icons/hicolor/48x48/apps/"
    cp "$REPO_DIR/plasmoid/contents/icons/claude-logo.png" "$HOME/.local/share/icons/hicolor/48x48/apps/claude-logo.png"

    echo -e "  ${GREEN}✓${NC} Plasmoid installed"
    echo -e "  ${DIM}  Right-click panel → Add Widgets → 'Claude Usage Monitor'${NC}"
}

install_tauri() {
    echo ""
    echo -e "${AMBER}[5/6]${NC} Building tray app..."

    if ! $HAS_RUST; then
        echo -e "  ${DIM}  Installing Rust toolchain...${NC}"
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --quiet 2>/dev/null
        source "$HOME/.cargo/env" 2>/dev/null || true
        if ! command -v cargo &>/dev/null; then
            echo -e "  ${RED}!${NC} Rust install failed. Skipping tray app."
            return
        fi
    fi

    if ! $HAS_NODE; then
        echo -e "  ${RED}!${NC} Node.js + npm required for tray app. Install and re-run."
        echo -e "  ${DIM}  Fedora: sudo dnf install nodejs npm${NC}"
        echo -e "  ${DIM}  Ubuntu: sudo apt install nodejs npm${NC}"
        return
    fi

    # Install Tauri build deps
    case $DISTRO in
        fedora)
            sudo dnf install -y webkit2gtk4.1-devel gtk3-devel libappindicator-gtk3-devel \
                librsvg2-devel pango-devel 2>/dev/null || true ;;
        debian)
            sudo apt-get install -y libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev \
                librsvg2-dev libpango1.0-dev 2>/dev/null || true ;;
    esac

    cd "$TAURI_DIR"
    npm install --silent 2>/dev/null
    echo -e "  ${DIM}  Compiling... (this takes 2-5 minutes)${NC}"
    npx tauri build 2>/dev/null

    # Copy binary to ~/.local/bin
    local BIN="$TAURI_DIR/src-tauri/target/release/claude-usage-tray"
    if [ -f "$BIN" ]; then
        cp "$BIN" "$HOME/.local/bin/claude-usage-tray"
        chmod +x "$HOME/.local/bin/claude-usage-tray"
        echo -e "  ${GREEN}✓${NC} Tray app installed to ~/.local/bin/claude-usage-tray"
    else
        echo -e "  ${RED}!${NC} Build failed. Check build logs."
    fi

    cd "$REPO_DIR"
}

setup_auth() {
    echo ""
    echo -e "${AMBER}[6/6]${NC} Testing data collection..."

    if python3 "$COLLECTOR" --verbose 2>&1 | grep -q '"source": "api"'; then
        echo -e "  ${GREEN}✓${NC} Connected to claude.ai (Live)"
    else
        echo -e "  ${AMBER}!${NC} Could not connect to claude.ai (Offline mode)"
        echo -e "  ${DIM}  Make sure you're logged in to claude.ai in Firefox or Chrome${NC}"
    fi

    # Generate initial data
    python3 "$COLLECTOR" 2>/dev/null
    echo -e "  ${GREEN}✓${NC} Initial data generated"
}

finish() {
    echo ""
    echo -e "${BOLD}═══════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Installation Complete!${NC}"
    echo -e "${BOLD}═══════════════════════════════════════════${NC}"
    echo ""

    if $HAS_KDE; then
        echo -e "  ${BOLD}KDE Plasmoid:${NC}"
        echo "    Right-click panel → Add Widgets → 'Claude Usage Monitor'"
        echo ""
    fi

    if [ -f "$HOME/.local/bin/claude-usage-tray" ]; then
        echo -e "  ${BOLD}Tray App:${NC}"
        echo "    Run: claude-usage-tray"
        echo "    Or:  Super+Shift+C to toggle"
        echo ""

        # Create desktop entry for autostart
        mkdir -p "$HOME/.config/autostart"
        cat > "$HOME/.config/autostart/claude-usage-tray.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=Claude Usage Monitor
Exec=$HOME/.local/bin/claude-usage-tray
Icon=claude-logo
StartupNotify=false
Terminal=false
X-GNOME-Autostart-enabled=true
DESKTOP
        echo -e "  ${GREEN}✓${NC} Added to autostart"
    fi

    echo "  Data refreshes every 30 seconds from claude.ai."
    echo "  Reads browser cookies automatically — no API keys needed."
    echo ""
}

# ── Main ──
header
detect_env

echo -e "  ${BLUE}Detected:${NC} $DISTRO | KDE=$HAS_KDE | Rust=$HAS_RUST | Node=$HAS_NODE"
echo ""

install_deps
install_collector
install_timer

if $HAS_KDE; then
    install_plasmoid
fi

# Build tray app if not KDE, or if user has Rust+Node
if ! $HAS_KDE || ($HAS_RUST && $HAS_NODE); then
    install_tauri
else
    echo ""
    echo -e "${AMBER}[5/6]${NC} Skipping tray app (KDE detected, use plasmoid instead)"
    echo -e "  ${DIM}  To also build the tray app: install Rust + Node.js and re-run${NC}"
fi

setup_auth
finish
