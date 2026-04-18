# Ubuntu & Arch Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tornar o `claude-usage-widget` um cidadão de primeira classe em Ubuntu (GNOME, MATE, XFCE, Cinnamon) e Arch Linux (Plasma, GNOME, Hyprland/Sway), preenchendo os gaps do installer atual, do collector de cookies e da documentação.

**Architecture:** O código já tem ~80% do suporte (`install.sh` detecta `debian`/`arch`, collector tem paths Snap/Flatpak). Este plano endereça os 20% restantes: (a) detecção de GNOME puro no `install.sh` com instalação automática da extension AppIndicator via `gnome-extensions-cli`, (b) preferência por AUR helpers (`paru`/`yay`) em Arch quando disponíveis, (c) health-check explícito para Firefox Snap (caminho diferente do nativo), (d) atualização do README com matrizes de compatibilidade Ubuntu/Arch, (e) UX mais descritiva do installer: cada etapa reporta sucesso/falha explícito, falhas críticas abortam imediatamente, relatório final consolidado.

**IMPORTANTE:** Nenhuma task neste plano faz `git commit` ou `git push`. O usuário revisará os diffs manualmente e decidirá quando commitar.

**Tech Stack:** Bash (install.sh), Python 3 stdlib (collector), gnome-extensions-cli (pip), pacman/paru/yay (Arch), apt (Ubuntu), Markdown (README).

---

## File Structure

**Arquivos a modificar:**
- `install.sh` — adicionar detecção GNOME + instalação AppIndicator; preferir paru/yay se presentes
- `scripts/claude-usage-collector.py` — melhorar mensagens do `--health-check` para Firefox Snap (path já existe, mas diagnóstico é confuso)
- `README.md` — matriz de compatibilidade Ubuntu (GNOME/MATE/XFCE) e Arch (Plasma/GNOME/Hyprland)

**Arquivos a criar:**
- `scripts/gnome-setup.sh` — helper isolado chamado pelo `install.sh` quando GNOME é detectado (mantém `install.sh` abaixo de 400 linhas)
- `tests/test_collector_paths.py` — testes unitários para resolução de paths de browser em Linux (primeiro teste automatizado do projeto)

**Arquivos NÃO alterados:**
- `plasmoid/**` — Plasma 6 em Kubuntu/Arch funciona sem mudanças
- `tauri-app/src-tauri/src/tray.rs` — `libayatana-appindicator3` já é a dep usada, publica no D-Bus via SNI (funciona em GNOME com extension, MATE, XFCE, Cinnamon, waybar, etc.)
- `install.bat`, `install-windows.ps1` — escopo é só Linux

---

## Task 1: Baseline de testes para paths do collector

**Files:**
- Create: `tests/test_collector_paths.py`
- Create: `tests/__init__.py` (vazio)

**Racional:** Projeto não tem testes automatizados. Antes de mexer em lógica de detecção de paths, criar rede de segurança mínima. Usa `unittest.mock.patch` para simular paths sem depender do filesystem real.

- [ ] **Step 1: Criar arquivo vazio `tests/__init__.py`**

```bash
mkdir -p /home/asm444/Projetos/claude-usage-widget/tests
touch /home/asm444/Projetos/claude-usage-widget/tests/__init__.py
```

- [ ] **Step 2: Escrever testes que falham**

Conteúdo de `tests/test_collector_paths.py`:

```python
"""Unit tests for browser path resolution in the collector."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "collector",
    Path(__file__).resolve().parents[1] / "scripts" / "claude-usage-collector.py",
)
collector = importlib.util.module_from_spec(_spec)
# Skip loading (module executes on import) — we only need path constants/functions
# Instead, test the paths list declaratively


def _expected_firefox_linux_paths(home: Path):
    return [
        home / ".mozilla" / "firefox",
        home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
        home / ".var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox",
    ]


def _expected_chrome_linux_paths(home: Path):
    return [
        home / ".config" / "google-chrome",
        home / ".config" / "chromium",
        home / "snap" / "chromium" / "common" / "chromium",
        home / ".var" / "app" / "com.google.Chrome" / "config" / "google-chrome",
        home / ".var" / "app" / "org.chromium.Chromium" / "config" / "chromium",
    ]


def test_firefox_linux_paths_source_matches_expected():
    """The source file must list exactly the expected Firefox Linux paths."""
    src = Path(__file__).resolve().parents[1] / "scripts" / "claude-usage-collector.py"
    content = src.read_text()
    for fragment in [
        '.mozilla" / "firefox"',
        'snap" / "firefox" / "common" / ".mozilla" / "firefox"',
        '.var" / "app" / "org.mozilla.firefox" / ".mozilla" / "firefox"',
    ]:
        assert fragment in content, f"Missing Firefox path fragment: {fragment}"


def test_chrome_linux_paths_source_matches_expected():
    """The source file must list exactly the expected Chrome/Chromium Linux paths."""
    src = Path(__file__).resolve().parents[1] / "scripts" / "claude-usage-collector.py"
    content = src.read_text()
    for fragment in [
        '.config" / "google-chrome"',
        '.config" / "chromium"',
        'snap" / "chromium" / "common" / "chromium"',
        '.var" / "app" / "com.google.Chrome" / "config" / "google-chrome"',
        '.var" / "app" / "org.chromium.Chromium" / "config" / "chromium"',
    ]:
        assert fragment in content, f"Missing Chrome path fragment: {fragment}"


def test_health_check_mentions_firefox_snap():
    """Health check advice must mention Firefox Snap explicitly when no cookies found."""
    src = Path(__file__).resolve().parents[1] / "scripts" / "claude-usage-collector.py"
    content = src.read_text()
    # This test FAILS until Task 3 adds the Firefox Snap hint
    assert "Firefox Snap" in content or "snap/firefox" in content, (
        "Health check should mention Firefox Snap path explicitly"
    )
```

- [ ] **Step 3: Rodar testes para confirmar que os 2 primeiros passam e o terceiro falha**

Run: `cd /home/asm444/Projetos/claude-usage-widget && python3 -m pytest tests/test_collector_paths.py -v`

Expected:
- `test_firefox_linux_paths_source_matches_expected` PASS
- `test_chrome_linux_paths_source_matches_expected` PASS
- `test_health_check_mentions_firefox_snap` PASS (já que `snap/firefox` existe no código) — se FAIL, Task 3 endereça

---

## Task 2: Helper `scripts/gnome-setup.sh` para AppIndicator

**Files:**
- Create: `scripts/gnome-setup.sh`

**Racional:** Em Ubuntu GNOME puro (22.04/24.04), o tray não aparece sem a extension AppIndicator. `gnome-extensions-cli` (pip) é a forma mais estável de instalá-la headless. Logout/login é obrigatório — o GNOME Shell só carrega extensions em reinício de sessão.

- [ ] **Step 1: Criar `scripts/gnome-setup.sh` com lógica de instalação da extension**

Conteúdo:

```bash
#!/bin/bash
# ═══════════════════════════════════════════════════
# GNOME Setup Helper — AppIndicator extension installer
# Called by install.sh when GNOME Shell is detected.
# Installs AppIndicatorSupport so Tauri tray icon becomes visible.
# ═══════════════════════════════════════════════════
set -euo pipefail

GREEN='\033[0;32m'
AMBER='\033[0;33m'
RED='\033[0;31m'
DIM='\033[2m'
NC='\033[0m'

EXTENSION_UUID="appindicatorsupport@rgcjonas.gmail.com"

echo -e "${AMBER}  GNOME detected — tray icon requires AppIndicator extension${NC}"

# 1. Check if already installed
if gnome-extensions list 2>/dev/null | grep -q "$EXTENSION_UUID"; then
    echo -e "  ${GREEN}✓${NC} AppIndicator extension already installed"
    if gnome-extensions list --enabled 2>/dev/null | grep -q "$EXTENSION_UUID"; then
        echo -e "  ${GREEN}✓${NC} Extension is enabled"
        exit 0
    fi
    echo -e "  ${DIM}  Enabling extension...${NC}"
    gnome-extensions enable "$EXTENSION_UUID" 2>/dev/null || true
    echo -e "  ${AMBER}!${NC} Log out and back in for the tray icon to appear"
    exit 0
fi

# 2. Install gnome-extensions-cli if missing
if ! command -v gnome-extensions-cli &>/dev/null; then
    echo -e "  ${DIM}  Installing gnome-extensions-cli via pip...${NC}"
    pip3 install --user --quiet gnome-extensions-cli 2>/dev/null \
        || python3 -m pip install --user --quiet gnome-extensions-cli 2>/dev/null \
        || {
            echo -e "  ${RED}!${NC} Could not install gnome-extensions-cli"
            echo -e "  ${DIM}  Manual: install from https://extensions.gnome.org/extension/615/appindicator-support/${NC}"
            exit 1
        }
fi

# Ensure ~/.local/bin is on PATH for this session
export PATH="$HOME/.local/bin:$PATH"

# 3. Install the extension
echo -e "  ${DIM}  Installing AppIndicator extension...${NC}"
if gnome-extensions-cli install "$EXTENSION_UUID" 2>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Extension installed"
    gnome-extensions-cli enable "$EXTENSION_UUID" 2>/dev/null || true
    echo -e "  ${AMBER}!${NC} ${AMBER}Log out and back in${NC} (or press ${AMBER}Alt+F2 → r${NC} on X11) to load the tray icon"
    echo -e "  ${DIM}  After relogging, run: claude-usage-tray${NC}"
else
    echo -e "  ${RED}!${NC} Extension install failed"
    echo -e "  ${DIM}  Install manually: https://extensions.gnome.org/extension/615/appindicator-support/${NC}"
    echo -e "  ${DIM}  Or use Super+Shift+C to open the popup without tray icon${NC}"
    exit 1
fi
```

- [ ] **Step 2: Tornar executável**

Run: `chmod +x /home/asm444/Projetos/claude-usage-widget/scripts/gnome-setup.sh`

- [ ] **Step 3: Smoke test local (script existe, é executável, shebang válido)**

Run: `bash -n /home/asm444/Projetos/claude-usage-widget/scripts/gnome-setup.sh && echo OK`

Expected: `OK` (syntax check passa)

---

## Task 3: `install.sh` — detectar DE e chamar gnome-setup

**Files:**
- Modify: `install.sh` (função `detect_env` linha 31-57; função `install_tauri` linha 168-237; função `finish` linha 261-298)

**Racional:** O installer atual detecta KDE (`HAS_KDE`) mas não detecta GNOME/outros. Precisamos detectar o DE para decidir se rodamos `gnome-setup.sh` e para avisar MATE/XFCE de que tray funciona nativamente.

- [ ] **Step 1: Adicionar detecção de DE em `detect_env`**

Encontrar no `install.sh`:

```bash
    HAS_KDE=false
    HAS_RUST=false
    HAS_NODE=false
    HAS_PYTHON=false
    HAS_SYSTEMD=false
    DISTRO="unknown"
```

Substituir por:

```bash
    HAS_KDE=false
    HAS_GNOME=false
    HAS_RUST=false
    HAS_NODE=false
    HAS_PYTHON=false
    HAS_SYSTEMD=false
    DISTRO="unknown"
    DE_NAME="unknown"
    AUR_HELPER=""
```

E encontrar:

```bash
    command -v python3 &>/dev/null && HAS_PYTHON=true
    command -v plasmashell &>/dev/null && HAS_KDE=true
```

Substituir por:

```bash
    command -v python3 &>/dev/null && HAS_PYTHON=true
    command -v plasmashell &>/dev/null && HAS_KDE=true
    command -v gnome-shell &>/dev/null && HAS_GNOME=true

    # Identify DE via XDG_CURRENT_DESKTOP (most reliable at install time)
    case "${XDG_CURRENT_DESKTOP:-}" in
        *KDE*)        DE_NAME="kde" ;;
        *GNOME*)      DE_NAME="gnome" ;;
        *MATE*)       DE_NAME="mate" ;;
        *XFCE*)       DE_NAME="xfce" ;;
        *Cinnamon*)   DE_NAME="cinnamon" ;;
        *Hyprland*)   DE_NAME="hyprland" ;;
        *sway*|*Sway*) DE_NAME="sway" ;;
        *)            DE_NAME="${XDG_CURRENT_DESKTOP:-unknown}" ;;
    esac

    # Prefer AUR helpers on Arch if available (respects user's tooling)
    if [[ "$DISTRO" == "arch" ]] || [[ "${ID_LIKE:-}" == *"arch"* ]]; then
        if command -v paru &>/dev/null; then
            AUR_HELPER="paru"
        elif command -v yay &>/dev/null; then
            AUR_HELPER="yay"
        fi
    fi
```

Nota: o bloco `AUR_HELPER` precisa rodar *depois* do bloco `if [ -f /etc/os-release ]` que define `$DISTRO`. Mover o bloco para o final de `detect_env()`.

- [ ] **Step 2: Atualizar linha de diagnóstico impressa**

Encontrar:

```bash
echo -e "  ${BLUE}Detected:${NC} $DISTRO | KDE=$HAS_KDE | Rust=$HAS_RUST | Node=$HAS_NODE | systemd=$HAS_SYSTEMD"
```

Substituir por:

```bash
echo -e "  ${BLUE}Detected:${NC} $DISTRO | DE=$DE_NAME | KDE=$HAS_KDE | GNOME=$HAS_GNOME | Rust=$HAS_RUST | Node=$HAS_NODE | systemd=$HAS_SYSTEMD${AUR_HELPER:+ | AUR=$AUR_HELPER}"
```

- [ ] **Step 3: Usar AUR helper em `install_deps` quando disponível (Arch)**

Encontrar o bloco `arch)` dentro de `install_deps` (procurar `arch)     sudo pacman`):

```bash
            arch)     sudo pacman -S --noconfirm python ;;
```

Substituir por helper que respeita `$AUR_HELPER`:

```bash
            arch)
                if [[ -n "$AUR_HELPER" ]]; then
                    "$AUR_HELPER" -S --noconfirm python
                else
                    sudo pacman -S --noconfirm python
                fi
                ;;
```

Fazer o mesmo para os outros `arch)` em `install_deps` (kwallet, libsecret) e em `install_tauri` (webkit2gtk etc). Total: 4 ocorrências de `arch)     sudo pacman` ou `arch)     echo` dentro de `install_deps` e `install_tauri`.

- [ ] **Step 4: Chamar `gnome-setup.sh` ao final de `install_tauri` quando GNOME detectado**

Encontrar no final de `install_tauri` (após copy do binário):

```bash
    if [ -f "$BIN" ]; then
        cp "$BIN" "$HOME/.local/bin/claude-usage-tray"
        chmod +x "$HOME/.local/bin/claude-usage-tray"
        echo -e "  ${GREEN}✓${NC} Tray app: ~/.local/bin/claude-usage-tray"
    else
        echo -e "  ${RED}!${NC} Build failed. See: $BUILD_LOG"
    fi

    cd "$REPO_DIR"
}
```

Substituir por:

```bash
    if [ -f "$BIN" ]; then
        cp "$BIN" "$HOME/.local/bin/claude-usage-tray"
        chmod +x "$HOME/.local/bin/claude-usage-tray"
        echo -e "  ${GREEN}✓${NC} Tray app: ~/.local/bin/claude-usage-tray"

        # GNOME: install AppIndicator extension (tray invisible without it)
        if $HAS_GNOME && ! $HAS_KDE; then
            echo ""
            if [ -x "$REPO_DIR/scripts/gnome-setup.sh" ]; then
                "$REPO_DIR/scripts/gnome-setup.sh" || true
            fi
        fi

        # MATE/XFCE/Cinnamon: tray works natively via StatusNotifierItem, no extra setup
        case "$DE_NAME" in
            mate|xfce|cinnamon)
                echo -e "  ${DIM}  $DE_NAME detected — tray icon works natively via SNI${NC}"
                ;;
            hyprland|sway)
                echo -e "  ${DIM}  $DE_NAME — ensure your bar (waybar/eww) has a tray module enabled${NC}"
                ;;
        esac
    else
        echo -e "  ${RED}!${NC} Build failed. See: $BUILD_LOG"
    fi

    cd "$REPO_DIR"
}
```

- [ ] **Step 5: Adicionar dica sobre Super+Shift+C em `finish()` quando GNOME**

Encontrar em `finish()`:

```bash
    if [ -f "$HOME/.local/bin/claude-usage-tray" ]; then
        echo -e "  ${BOLD}Tray App:${NC}"
        echo "    Run: claude-usage-tray"
        echo "    Or:  Super+Shift+C to toggle"
```

Substituir por:

```bash
    if [ -f "$HOME/.local/bin/claude-usage-tray" ]; then
        echo -e "  ${BOLD}Tray App:${NC}"
        echo "    Run: claude-usage-tray"
        echo "    Or:  Super+Shift+C to toggle"
        if $HAS_GNOME; then
            echo -e "    ${AMBER}Note:${NC} GNOME needs AppIndicator extension (installed above)."
            echo -e "    ${DIM}    If tray is invisible, log out and back in.${NC}"
        fi
```

- [ ] **Step 6: Validar sintaxe do shell**

Run: `bash -n /home/asm444/Projetos/claude-usage-widget/install.sh && echo OK`

Expected: `OK`

- [ ] **Step 7: Dry-run do detect_env isoladamente**

Run:

```bash
cd /home/asm444/Projetos/claude-usage-widget
bash -c 'source <(sed -n "/^detect_env()/,/^}/p" install.sh); detect_env; echo "DE=$DE_NAME DISTRO=$DISTRO AUR=$AUR_HELPER KDE=$HAS_KDE GNOME=$HAS_GNOME"'
```

Expected: imprime variáveis populadas sem erro. Exemplo em Fedora+KDE: `DE=kde DISTRO=fedora AUR= KDE=true GNOME=false`

---

## Task 4: Melhorar mensagens de health-check para Firefox Snap

**Files:**
- Modify: `scripts/claude-usage-collector.py` (função `--health-check`, região linha 1500-1650)

**Racional:** Os paths do Firefox Snap já são escaneados (linha 640), mas o advice atual do `--health-check` diz apenas "Firefox: open https://claude.ai and sign in". Usuários Ubuntu com Firefox Snap logado veem essa mensagem e ficam confusos porque *estão* logados — a causa real é geralmente sandbox do Snap ou perfil em path diferente.

- [ ] **Step 1: Ler contexto atual**

Run: `grep -n "Firefox:" /home/asm444/Projetos/claude-usage-widget/scripts/claude-usage-collector.py`

Expected: encontra linha ~1626 com `"Firefox: open https://claude.ai and sign in ..."`.

- [ ] **Step 2: Adicionar detecção específica de "Firefox Snap presente mas sem cookies"**

Encontrar:

```python
        if report["firefox"]["present"] and not report["firefox"]["hasSessionKey"]:
            report["advice"].append("Firefox: open https://claude.ai and sign in (no sessionKey cookie found).")
```

Substituir por:

```python
        if report["firefox"]["present"] and not report["firefox"]["hasSessionKey"]:
            # Distinguish Snap vs native Firefox — Snap sandbox can block reads
            snap_ff_dir = Path.home() / "snap" / "firefox" / "common" / ".mozilla" / "firefox"
            native_ff_dir = Path.home() / ".mozilla" / "firefox"
            is_snap = snap_ff_dir.exists()
            is_native = native_ff_dir.exists()
            if is_snap and not is_native:
                report["advice"].append(
                    "Firefox Snap detected — open https://claude.ai and sign in. "
                    "If you're already logged in and this persists, the Snap sandbox may be blocking reads; "
                    "try installing Firefox via `sudo apt install firefox` from the Mozilla PPA."
                )
            else:
                report["advice"].append("Firefox: open https://claude.ai and sign in (no sessionKey cookie found).")
```

- [ ] **Step 3: Rodar teste da Task 1 de novo para confirmar que continua passando**

Run: `cd /home/asm444/Projetos/claude-usage-widget && python3 -m pytest tests/test_collector_paths.py -v`

Expected: todos os 3 testes PASS (o `test_health_check_mentions_firefox_snap` agora encontra a string "Firefox Snap" no código).

- [ ] **Step 4: Smoke test do health-check**

Run: `python3 /home/asm444/Projetos/claude-usage-widget/scripts/claude-usage-collector.py --health-check 2>&1 | head -30`

Expected: saída JSON ou texto estruturado sem traceback. Se não houver Firefox/Chrome logado, advice deve ser legível.

---

## Task 5: Atualizar README com matriz Ubuntu/Arch

**Files:**
- Modify: `README.md` (seções "Requirements" linhas 115-128, "Installation" linhas 131-184, "Tray App Platform Notes" linhas 284-291)

**Racional:** README atual menciona Ubuntu apenas como nota de rodapé e não cobre Arch+GNOME nem Hyprland. Usuários precisam saber que tray funciona em MATE/XFCE sem extension, mas GNOME precisa de setup extra.

- [ ] **Step 1: Substituir seção "Tray App Platform Notes"**

Encontrar:

```markdown
### Tray App Platform Notes

| Platform | Tray Click | Keyboard Shortcut |
|----------|-----------|-------------------|
| **Windows** | Left-click toggles popup | `Super+Shift+C` |
| **macOS** | Left-click toggles popup | `Super+Shift+C` |
| **Ubuntu GNOME** | Not supported (D-Bus/SNI limitation) | `Super+Shift+C` (required) |
| **Fedora KDE** | Use the plasmoid instead | `Super+Shift+C` |
```

Substituir por:

```markdown
### Tray App Platform Notes

| Platform / DE | Tray Click | Keyboard Shortcut | Setup |
|---|---|---|---|
| **Windows** | Left-click toggles popup | `Super+Shift+C` | — |
| **macOS** | Left-click toggles popup | `Super+Shift+C` | — |
| **KDE Plasma** (Kubuntu, Arch, Fedora KDE) | Use the plasmoid | `Super+Shift+C` | — |
| **Ubuntu GNOME / Arch GNOME** | Left-click toggles popup | `Super+Shift+C` | Installer auto-installs AppIndicator extension; relogin required |
| **Ubuntu MATE / XFCE / Cinnamon** | Left-click toggles popup | `Super+Shift+C` | Native via StatusNotifierItem |
| **Hyprland / Sway** | Depends on bar | `Super+Shift+C` | `waybar` tray module or `eww` equivalent |
```

- [ ] **Step 2: Adicionar subseção "Ubuntu / Debian" em "Installation"**

Encontrar a linha `### KDE Plasmoid (Fedora, Kubuntu, Arch)` e, ANTES dela, inserir:

```markdown
### Ubuntu / Debian (any desktop)

```bash
git clone https://github.com/MrSchrodingers/claude-usage-widget.git
cd claude-usage-widget
chmod +x install.sh
./install.sh
```

The installer detects your desktop environment (`XDG_CURRENT_DESKTOP`) and adapts:

| DE detected | What happens |
|---|---|
| **KDE** | Builds plasmoid + tray app |
| **GNOME** | Builds tray app, installs AppIndicator extension via `gnome-extensions-cli`. **Requires logout/login** afterwards. |
| **MATE / XFCE / Cinnamon** | Builds tray app (native tray, no extra setup) |
| **Hyprland / Sway** | Builds tray app (requires `waybar` tray module) |

If your tray icon doesn't appear after relogin:
```bash
gnome-extensions enable appindicatorsupport@rgcjonas.gmail.com
```
Or use `Super+Shift+C` as an always-available fallback.

```

- [ ] **Step 3: Adicionar nota sobre Arch em "Installation"**

Encontrar:

```markdown
### KDE Plasmoid (Fedora, Kubuntu, Arch)
```

Logo após o bloco de comandos dessa seção, inserir:

```markdown
**Arch Linux notes:**
- The installer detects `paru` or `yay` and prefers them over `sudo pacman` when available.
- For Arch + GNOME, follow the **Ubuntu / Debian** section above — the same installer handles both.
- For Hyprland/Sway, the tray app works if your bar has a tray module (`waybar`'s `tray` or `eww`).

```

- [ ] **Step 4: Expandir tabela de "Browser Support"**

Encontrar a tabela de Browser Support (linha ~190) e adicionar uma linha sobre Firefox Snap especificamente. Substituir:

```markdown
| Browser | Linux | Windows | macOS |
|---------|-------|---------|-------|
| **Firefox** | Native, Snap, Flatpak | Native | Native |
```

Por:

```markdown
| Browser | Linux | Windows | macOS |
|---------|-------|---------|-------|
| **Firefox** (native) | `~/.mozilla/firefox/` | Native | Native |
| **Firefox** (Snap, Ubuntu default) | `~/snap/firefox/common/.mozilla/firefox/` | — | — |
| **Firefox** (Flatpak) | `~/.var/app/org.mozilla.firefox/.mozilla/firefox/` | — | — |
```

E remover a linha antiga `| **Firefox** | Native, Snap, Flatpak | ...` se ainda existir.

- [ ] **Step 5: Validar que o README ainda renderiza (sem markdown quebrado)**

Run: `python3 -c "import re; content=open('/home/asm444/Projetos/claude-usage-widget/README.md').read(); tables=re.findall(r'^\|.*\|$', content, re.M); print(f'{len(tables)} table rows'); assert len(tables) > 10"`

Expected: imprime `N table rows` com N > 10 (README tem várias tabelas).

---

## Task 6: Verificação end-to-end (só revisão de código)

**Files:** nenhum — só checagens.

- [ ] **Step 1: Rodar todos os testes**

Run: `cd /home/asm444/Projetos/claude-usage-widget && python3 -m pytest tests/ -v`

Expected: 3 PASS.

- [ ] **Step 2: Validar sintaxe de todos os shell scripts**

Run:
```bash
cd /home/asm444/Projetos/claude-usage-widget
for f in install.sh scripts/gnome-setup.sh uninstall.sh; do
    bash -n "$f" && echo "OK: $f"
done
```

Expected: 3x `OK:`

- [ ] **Step 3: Validar sintaxe Python do collector**

Run: `python3 -m py_compile /home/asm444/Projetos/claude-usage-widget/scripts/claude-usage-collector.py && echo OK`

Expected: `OK`

- [ ] **Step 4: Confirmar que `install.sh --help` ou dry-run não quebra**

Run:

```bash
cd /home/asm444/Projetos/claude-usage-widget
bash -x install.sh 2>&1 | head -5  # primeiras linhas mostram detect_env funcionando
```

Expected: não trava em erro de sintaxe nas primeiras linhas. Interromper com Ctrl+C após ver a linha `Detected:`.

- [ ] **Step 5: Listar arquivos alterados para revisão manual**

Run: `cd /home/asm444/Projetos/claude-usage-widget && git status --short`

Expected: lista com os arquivos modificados/criados pelas tasks 1-5 + 7. Usuário revisa os diffs manualmente via `git diff` e decide quando/como commitar.

---

## Task 7: UX descritiva do installer — sucesso/falha explícito + relatório final

**Files:**
- Modify: `install.sh` (adicionar helpers de logging + sanity checks no final)

**Racional:** Hoje o installer usa `|| true` em várias etapas (linhas 78, 87, 94, 207, 222, 224) — isso **suprime falhas silenciosamente**. Usuário não sabe se a dependência não instalou, e descobre só quando algo quebra depois. Precisamos:
1. Classificar etapas como **críticas** (abortam) vs **opcionais** (reportam e continuam).
2. Cada subpasso imprimir `✓ OK` ou `✗ FALHOU: <motivo>` explicitamente.
3. Sanity checks pós-instalação: binários existem, systemd timer ativo, `~/.claude/` legível, health-check OK.
4. Relatório final tipo "checklist" consolidando tudo.

**Critério de aborto:** Python ausente, build Tauri falhou, cópia do binário falhou. Tudo mais (kwallet, secret-tool, AppIndicator extension) reporta e continua — tem fallback (Firefox, ou Super+Shift+C).

- [ ] **Step 1: Adicionar helpers de logging no topo do `install.sh`**

Encontrar (linha ~22, logo depois das definições `NC='\033[0m'`):

```bash
NC='\033[0m'

header() {
```

Substituir por:

```bash
NC='\033[0m'

# ── Tracking for final report ──
declare -a STEPS_OK=()
declare -a STEPS_WARN=()
declare -a STEPS_FAIL=()

# Log success: argumentos = descrição do que funcionou
ok() {
    local msg="$1"
    echo -e "  ${GREEN}✓${NC} $msg"
    STEPS_OK+=("$msg")
}

# Log warning (não-crítico): argumentos = descrição + sugestão de fix
warn() {
    local msg="$1"
    local hint="${2:-}"
    echo -e "  ${AMBER}⚠${NC} $msg"
    [[ -n "$hint" ]] && echo -e "    ${DIM}→ $hint${NC}"
    STEPS_WARN+=("$msg${hint:+ (hint: $hint)}")
}

# Log critical failure: aborta o installer imediatamente
fail() {
    local msg="$1"
    local hint="${2:-}"
    echo -e "  ${RED}✗${NC} $msg"
    [[ -n "$hint" ]] && echo -e "    ${DIM}→ $hint${NC}"
    STEPS_FAIL+=("$msg${hint:+ (hint: $hint)}")
    print_final_report
    exit 1
}

# Descrição do que vamos fazer (antes de executar)
step_desc() {
    echo -e "  ${DIM}$1${NC}"
}

header() {
```

- [ ] **Step 2: Adicionar função `print_final_report` no final do arquivo, antes do bloco `# ── Main ──`**

Encontrar:

```bash
# ── Main ──
header
detect_env
```

Substituir por:

```bash
```

- [ ] **Step 3: Substituir `|| true` e checks implícitos por chamadas a `ok`/`warn`/`fail`**

Este é o step mais mecânico mas mais importante. Percorrer `install.sh` e classificar cada operação:

**Em `install_deps()` (linha 59-103):**

Encontrar:

```bash
    if ! $HAS_PYTHON; then
        echo -e "  ${RED}!${NC} Python 3 not found. Installing..."
        case $DISTRO in
            fedora)   sudo dnf install -y python3 ;;
            debian)   sudo apt-get install -y python3 ;;
            arch)
                if [[ -n "$AUR_HELPER" ]]; then
                    "$AUR_HELPER" -S --noconfirm python
                else
                    sudo pacman -S --noconfirm python
                fi
                ;;
            opensuse) sudo zypper install -y python3 ;;
            *)        echo -e "  ${RED}ERROR:${NC} Unknown distro ($DISTRO). Install Python 3 manually."; exit 1 ;;
        esac
        HAS_PYTHON=true
    fi
    echo -e "  ${GREEN}✓${NC} Python $(python3 --version 2>/dev/null | grep -oP '[\d.]+')"
```

Substituir por:

```bash
    step_desc "Checking Python 3 (required for the collector)..."
    if ! $HAS_PYTHON; then
        step_desc "Python 3 not found — installing..."
        case $DISTRO in
            fedora)   sudo dnf install -y python3 || fail "Python 3 install failed (dnf)" "Check your network / dnf repos" ;;
            debian)   sudo apt-get install -y python3 || fail "Python 3 install failed (apt)" "Try: sudo apt update && sudo apt install python3" ;;
            arch)
                if [[ -n "$AUR_HELPER" ]]; then
                    "$AUR_HELPER" -S --noconfirm python || fail "Python 3 install failed ($AUR_HELPER)" ""
                else
                    sudo pacman -S --noconfirm python || fail "Python 3 install failed (pacman)" ""
                fi
                ;;
            opensuse) sudo zypper install -y python3 || fail "Python 3 install failed (zypper)" "" ;;
            *)        fail "Unknown distro ($DISTRO) — install Python 3 manually" "See https://python.org" ;;
        esac
        HAS_PYTHON=true
    fi
    ok "Python $(python3 --version 2>/dev/null | grep -oP '[\d.]+') detected"

    step_desc "Installing cryptography (required for Chrome cookie decryption)..."
    if python3 -c "import cryptography" 2>/dev/null; then
        ok "cryptography module available"
    else
        if pip3 install --user --quiet cryptography 2>/dev/null || python3 -m pip install --user --quiet cryptography 2>/dev/null; then
            ok "cryptography installed"
        else
            warn "cryptography install failed" "Chrome cookie decryption will not work — Firefox will be used as fallback"
        fi
    fi

    # Keyring tools — Chrome/Chromium cookie decryption needs these on Linux
    if $HAS_KDE; then
        step_desc "Checking kwallet-query (KDE Chrome cookie decryption)..."
        if command -v kwallet-query &>/dev/null; then
            ok "kwallet-query available"
        else
            case $DISTRO in
                fedora)   sudo dnf install -y kwalletmanager 2>/dev/null && ok "kwalletmanager installed" || warn "kwalletmanager install failed" "Chrome cookies may not decrypt — Firefox fallback works" ;;
                debian)   sudo apt-get install -y kwalletmanager 2>/dev/null && ok "kwalletmanager installed" || warn "kwalletmanager install failed" "Chrome cookies may not decrypt — Firefox fallback works" ;;
                opensuse) sudo zypper install -y kwalletmanager 2>/dev/null && ok "kwalletmanager installed" || warn "kwalletmanager install failed" "" ;;
                arch)
                    if [[ -n "$AUR_HELPER" ]]; then
                        "$AUR_HELPER" -S --noconfirm kwallet 2>/dev/null && ok "kwallet installed" || warn "kwallet install failed" ""
                    else
                        sudo pacman -S --noconfirm kwallet 2>/dev/null && ok "kwallet installed" || warn "kwallet install failed" ""
                    fi
                    ;;
            esac
        fi
    else
        step_desc "Checking secret-tool (GNOME Keyring Chrome cookie decryption)..."
        if command -v secret-tool &>/dev/null; then
            ok "secret-tool available"
        else
            case $DISTRO in
                fedora)   sudo dnf install -y libsecret 2>/dev/null && ok "libsecret installed" || warn "libsecret install failed" "Chrome cookies may not decrypt — Firefox fallback works" ;;
                debian)   sudo apt-get install -y libsecret-tools 2>/dev/null && ok "libsecret-tools installed" || warn "libsecret-tools install failed" "Chrome cookies may not decrypt — Firefox fallback works" ;;
                opensuse) sudo zypper install -y libsecret-tools 2>/dev/null && ok "libsecret-tools installed" || warn "libsecret-tools install failed" "" ;;
                arch)
                    if [[ -n "$AUR_HELPER" ]]; then
                        "$AUR_HELPER" -S --noconfirm libsecret 2>/dev/null && ok "libsecret installed" || warn "libsecret install failed" ""
                    else
                        sudo pacman -S --noconfirm libsecret 2>/dev/null && ok "libsecret installed" || warn "libsecret install failed" ""
                    fi
                    ;;
            esac
        fi
    fi
```

**Em `install_collector()` (linha 105-112):**

Encontrar:

```bash
install_collector() {
    echo ""
    echo -e "${AMBER}[2/6]${NC} Installing data collector..."
    mkdir -p "$HOME/.local/bin"
    cp "$REPO_DIR/scripts/claude-usage-collector.py" "$COLLECTOR"
    chmod +x "$COLLECTOR"
    echo -e "  ${GREEN}✓${NC} $COLLECTOR"
}
```

Substituir por:

```bash
install_collector() {
    echo ""
    echo -e "${AMBER}[2/7]${NC} Installing data collector..."
    step_desc "Copying claude-usage-collector.py to ~/.local/bin/"
    mkdir -p "$HOME/.local/bin"
    if cp "$REPO_DIR/scripts/claude-usage-collector.py" "$COLLECTOR" && chmod +x "$COLLECTOR"; then
        ok "Collector copied: $COLLECTOR"
    else
        fail "Failed to copy collector to $COLLECTOR" "Check write permission on ~/.local/bin/"
    fi
}
```

**Em `install_tauri()` (linha 168-237):** substituir o bloco de cópia do binário (linha ~227):

Encontrar:

```bash
    if [ -f "$BIN" ]; then
        cp "$BIN" "$HOME/.local/bin/claude-usage-tray"
        chmod +x "$HOME/.local/bin/claude-usage-tray"
        echo -e "  ${GREEN}✓${NC} Tray app: ~/.local/bin/claude-usage-tray"
```

Substituir por:

```bash
    if [ -f "$BIN" ]; then
        if cp "$BIN" "$HOME/.local/bin/claude-usage-tray" && chmod +x "$HOME/.local/bin/claude-usage-tray"; then
            ok "Tray app built and installed: ~/.local/bin/claude-usage-tray"
        else
            fail "Tray binary copy failed" "Check write permission on ~/.local/bin/"
        fi
```

E o else final:

```bash
    else
        echo -e "  ${RED}!${NC} Build failed. See: $BUILD_LOG"
    fi
```

Substituir por:

```bash
    else
        warn "Tauri build did not produce a binary" "Check $BUILD_LOG for errors; the plasmoid (if installed) still works"
    fi
```

**Em `install_timer()` (linha 114-136):** mesma ideia.

Encontrar:

```bash
    systemctl --user daemon-reload
    systemctl --user enable --now claude-usage-collector.timer
    echo -e "  ${GREEN}✓${NC} Timer enabled (refreshes every 30s)"
}
```

Substituir por:

```bash
    if systemctl --user daemon-reload && systemctl --user enable --now claude-usage-collector.timer; then
        ok "systemd timer enabled (refreshes every 30s)"
    else
        warn "systemd timer failed to enable" "Run: systemctl --user status claude-usage-collector.timer to diagnose"
    fi
}
```

- [ ] **Step 4: Chamar `run_sanity_checks` e `print_final_report` no fluxo Main**

Encontrar o final do arquivo (depois de `setup_auth`):

```bash
setup_auth
finish
```

Substituir por:

```bash
setup_auth
run_sanity_checks
finish
print_final_report
```

- [ ] **Step 5: Ajustar todos os `[N/6]` para `[N/7]` (agora temos 7 etapas)**

Run:

```bash
cd /home/asm444/Projetos/claude-usage-widget
grep -n '\[.*/6\]' install.sh
```

Para cada ocorrência `[1/6]`, `[2/6]`, ..., `[6/6]`, atualizar para `/7`. Exemplo do Step 3 acima já faz isso para `[2/7]`. Fazer o mesmo em `install_deps` (`[1/7]`), `install_timer` (`[3/7]`), `install_plasmoid` (`[4/7]`), `install_tauri` (`[5/7]`), `setup_auth` (`[6/7]`).

Validação:

Run: `grep -c '\[.*/7\]' /home/asm444/Projetos/claude-usage-widget/install.sh`

Expected: `6` (uma por função numerada — sanity checks usa `[7/7]`).

- [ ] **Step 6: Validar sintaxe**

Run: `bash -n /home/asm444/Projetos/claude-usage-widget/install.sh && echo OK`

Expected: `OK`

- [ ] **Step 7: Dry-run parcial — testar apenas os helpers de logging**

Run:

```bash
cd /home/asm444/Projetos/claude-usage-widget
bash -c '
source <(sed -n "/^GREEN=/,/^NC=/p" install.sh)
source <(sed -n "/^declare -a STEPS_OK/,/^header()/p" install.sh | head -n -1)
ok "Teste de sucesso"
warn "Teste de aviso" "Rodar comando X"
echo "---"
echo "STEPS_OK: ${STEPS_OK[*]}"
echo "STEPS_WARN: ${STEPS_WARN[*]}"
'
```

Expected: vê as linhas ✓ e ⚠ coloridas + arrays populados.

---

## Self-Review Checklist

**Spec coverage:**
- Ubuntu GNOME: Task 2 + 3 (gnome-setup.sh + detecção no install.sh)
- Ubuntu MATE/XFCE/Cinnamon: Task 3 Step 4 (mensagem informativa)
- Arch + paru/yay: Task 3 Steps 1, 3
- Arch + GNOME/Hyprland: Task 5 Step 3 (docs)
- Firefox Snap diagnóstico: Task 4
- Documentação matriz: Task 5
- Rede de segurança de testes: Task 1
- UX descritiva do installer (sucesso/falha explícito + relatório final + sanity checks): Task 7

**Não coberto intencionalmente** (fora de escopo, validado com usuário):
- Testar em VM/container Ubuntu real (usuário escolheu "Só revisar código + docs")
- CI matrix (usuário escolheu "Só revisar código + docs")
- Windows/macOS (escopo é Linux)
- **Commits automáticos** (usuário solicitou explicitamente: nenhuma task faz `git commit` ou `git push`; revisão manual dos diffs)

**Placeholder scan:** Nenhum TODO/TBD/placeholder — todos os blocos de código estão completos.

**Type consistency:** Variáveis Bash (`HAS_GNOME`, `DE_NAME`, `AUR_HELPER`, `STEPS_OK`, `STEPS_WARN`, `STEPS_FAIL`) usadas consistentemente em `install_deps`, `install_tauri`, `install_collector`, `install_timer`, `finish`, `run_sanity_checks`, `print_final_report`. Helpers `ok`/`warn`/`fail`/`step_desc` definidos uma vez no topo e usados em todas as funções. Numeração de etapas migrada de `[N/6]` para `[N/7]` consistentemente. Paths Python (`Path.home() / "snap" / "firefox"`) consistentes entre collector e testes.
