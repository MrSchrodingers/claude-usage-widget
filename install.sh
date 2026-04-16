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
BUILD_LOG="$REPO_DIR/tauri-build.log"

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
    HAS_SYSTEMD=false
    DISTRO="unknown"

    command -v python3 &>/dev/null && HAS_PYTHON=true
    command -v plasmashell &>/dev/null && HAS_KDE=true
    command -v cargo &>/dev/null && command -v rustc &>/dev/null && HAS_RUST=true
    command -v node &>/dev/null && command -v npm &>/dev/null && HAS_NODE=true
    systemctl --user status &>/dev/null 2>&1 && HAS_SYSTEMD=true

    if [ -f /etc/os-release ]; then
        . /etc/os-release
        if [[ "$ID" == "fedora" ]] || [[ "${ID_LIKE:-}" == *"fedora"* ]]; then
            DISTRO="fedora"
        elif [[ "$ID" == "ubuntu" ]] || [[ "$ID" == "debian" ]] || [[ "${ID_LIKE:-}" == *"ubuntu"* ]] || [[ "${ID_LIKE:-}" == *"debian"* ]]; then
            DISTRO="debian"
        elif [[ "$ID" == "arch" ]] || [[ "${ID_LIKE:-}" == *"arch"* ]]; then
            DISTRO="arch"
        elif [[ "$ID" == *"opensuse"* ]] || [[ "${ID_LIKE:-}" == *"suse"* ]]; then
            DISTRO="opensuse"
        fi
    fi
}

install_deps() {
    echo -e "${AMBER}[1/6]${NC} Checking dependencies..."

    if ! $HAS_PYTHON; then
        echo -e "  ${RED}!${NC} Python 3 not found. Installing..."
        case $DISTRO in
            fedora)   sudo dnf install -y python3 ;;
            debian)   sudo apt-get install -y python3 ;;
            arch)     sudo pacman -S --noconfirm python ;;
            opensuse) sudo zypper install -y python3 ;;
            *)        echo -e "  ${RED}ERROR:${NC} Unknown distro ($DISTRO). Install Python 3 manually."; exit 1 ;;
        esac
        HAS_PYTHON=true
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
                fedora)   sudo dnf install -y kwalletmanager 2>/dev/null || true ;;
                debian)   sudo apt-get install -y kwalletmanager 2>/dev/null || true ;;
                opensuse) sudo zypper install -y kwalletmanager 2>/dev/null || true ;;
                arch)     sudo pacman -S --noconfirm kwallet 2>/dev/null || true ;;
            esac
        fi
    else
        if ! command -v secret-tool &>/dev/null; then
            echo -e "  ${DIM}  Installing secret-tool for Chrome cookies...${NC}"
            case $DISTRO in
                fedora)   sudo dnf install -y libsecret 2>/dev/null || true ;;
                debian)   sudo apt-get install -y libsecret-tools 2>/dev/null || true ;;
                opensuse) sudo zypper install -y libsecret-tools 2>/dev/null || true ;;
                arch)     sudo pacman -S --noconfirm libsecret 2>/dev/null || true ;;
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
    echo -e "${AMBER}[3/6]${NC} Setting up auto-refresh..."

    if ! $HAS_SYSTEMD; then
        echo -e "  ${AMBER}!${NC} systemd user session not available (WSL/container?)."
        echo -e "  ${DIM}  Add to crontab manually: * * * * * python3 $COLLECTOR${NC}"
        return
    fi

    mkdir -p "$SYSTEMD_DIR"
    cp "$REPO_DIR/scripts/claude-usage-collector.service" "$SYSTEMD_DIR/"
    cp "$REPO_DIR/scripts/claude-usage-collector.timer" "$SYSTEMD_DIR/"

    # Patch python path in service file to match this system
    local PYTHON_BIN
    PYTHON_BIN=$(command -v python3 || command -v python || echo "/usr/bin/python3")
    sed -i "s|/usr/bin/python3|$PYTHON_BIN|g" "$SYSTEMD_DIR/claude-usage-collector.service"

    systemctl --user daemon-reload
    systemctl --user enable --now claude-usage-collector.timer
    echo -e "  ${GREEN}✓${NC} Timer enabled (refreshes every 30s)"
}

install_plasmoid() {
    local PLASMOID_DIR="$HOME/.local/share/plasma/plasmoids/org.kde.plasma.claudeusage"

    echo ""
    echo -e "${AMBER}[4/6]${NC} Installing KDE Plasmoid..."

    local PLASMA_VER
    PLASMA_VER=$(plasmashell --version 2>/dev/null | grep -oP '\d+' | head -1 || true)
    PLASMA_VER=${PLASMA_VER:-0}
    if [ "$PLASMA_VER" -lt 6 ] 2>/dev/null; then
        echo -e "  ${AMBER}!${NC} Plasma 6+ required (found Plasma $PLASMA_VER). Skipping plasmoid."
        return
    fi

    rm -rf "$PLASMOID_DIR"
    mkdir -p "$PLASMOID_DIR/contents/"{ui,icons,config}
    cp "$REPO_DIR/plasmoid/metadata.json" "$PLASMOID_DIR/"
    cp "$REPO_DIR/plasmoid/contents/ui/main.qml" "$PLASMOID_DIR/contents/ui/"
    if compgen -G "$REPO_DIR/plasmoid/contents/icons/*" > /dev/null 2>&1; then
        cp "$REPO_DIR/plasmoid/contents/icons/"* "$PLASMOID_DIR/contents/icons/"
    fi
    mkdir -p "$HOME/.local/share/icons/hicolor/48x48/apps/"
    if [ -f "$REPO_DIR/plasmoid/contents/icons/claude-logo.png" ]; then
        cp "$REPO_DIR/plasmoid/contents/icons/claude-logo.png" "$HOME/.local/share/icons/hicolor/48x48/apps/claude-logo.png"
    fi

    echo -e "  ${GREEN}✓${NC} Plasmoid installed"
    echo -e "  ${DIM}  Right-click panel → Add Widgets → 'Claude Usage Monitor'${NC}"
}

install_tauri() {
    echo ""
    echo -e "${AMBER}[5/6]${NC} Building tray app..."

    if [ ! -d "$TAURI_DIR" ]; then
        echo -e "  ${AMBER}!${NC} tauri-app directory not found. Skipping."
        return
    fi

    if ! $HAS_RUST; then
        echo -e "  ${DIM}  Rust not found. Installing via rustup...${NC}"
        echo -e "  ${DIM}  (download from https://rustup.rs)${NC}"
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --quiet 2>/dev/null || true
        # shellcheck disable=SC1091
        source "$HOME/.cargo/env" 2>/dev/null || true
        if ! command -v cargo &>/dev/null; then
            echo -e "  ${RED}!${NC} Rust install failed. Skipping tray app."
            echo -e "  ${DIM}  Install Rust manually: https://rustup.rs${NC}"
            return
        fi
        HAS_RUST=true
    fi

    if ! $HAS_NODE; then
        echo -e "  ${RED}!${NC} Node.js + npm required for tray app."
        case $DISTRO in
            fedora)   echo -e "  ${DIM}  sudo dnf install nodejs npm${NC}" ;;
            debian)   echo -e "  ${DIM}  sudo apt install nodejs npm${NC}" ;;
            arch)     echo -e "  ${DIM}  sudo pacman -S nodejs npm${NC}" ;;
            opensuse) echo -e "  ${DIM}  sudo zypper install nodejs npm${NC}" ;;
            *)        echo -e "  ${DIM}  Install Node.js from https://nodejs.org${NC}" ;;
        esac
        return
    fi

    # Install Tauri build deps
    echo -e "  ${DIM}  Installing system dependencies...${NC}"
    case $DISTRO in
        fedora)
            sudo dnf install -y webkit2gtk4.1-devel gtk3-devel libappindicator-gtk3-devel \
                librsvg2-devel pango-devel 2>/dev/null || true ;;
        debian)
            sudo apt-get install -y libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev \
                librsvg2-dev libpango1.0-dev 2>/dev/null || true ;;
        opensuse)
            sudo zypper install -y webkit2gtk3-soup2-devel gtk3-devel libappindicator3-devel \
                librsvg-devel pango-devel 2>/dev/null || true ;;
        arch)
            sudo pacman -S --noconfirm webkit2gtk-4.1 gtk3 libappindicator-gtk3 \
                librsvg pango 2>/dev/null || true ;;
    esac

    cd "$TAURI_DIR"
    echo -e "  ${DIM}  Installing npm dependencies...${NC}"
    npm install --silent 2>&1 | tee -a "$BUILD_LOG" > /dev/null || true
    echo -e "  ${DIM}  Compiling Tauri app... (2-5 minutes)${NC}"
    npx tauri build 2>&1 | tee -a "$BUILD_LOG" > /dev/null || true

    # Copy binary to ~/.local/bin
    local BIN="$TAURI_DIR/src-tauri/target/release/claude-usage-tray"
    if [ -f "$BIN" ]; then
        cp "$BIN" "$HOME/.local/bin/claude-usage-tray"
        chmod +x "$HOME/.local/bin/claude-usage-tray"
        echo -e "  ${GREEN}✓${NC} Tray app: ~/.local/bin/claude-usage-tray"
    else
        echo -e "  ${RED}!${NC} Build failed. See: $BUILD_LOG"
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
    python3 "$COLLECTOR" 2>/dev/null || true
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

echo -e "  ${BLUE}Detected:${NC} $DISTRO | KDE=$HAS_KDE | Rust=$HAS_RUST | Node=$HAS_NODE | systemd=$HAS_SYSTEMD"
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
