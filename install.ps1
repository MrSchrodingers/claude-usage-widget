# ═══════════════════════════════════════════════════
# Claude Usage Monitor - Windows Installer
# ═══════════════════════════════════════════════════

$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeDir = "$env:USERPROFILE\.claude"
$BinDir = "$env:LOCALAPPDATA\ClaudeUsageMonitor"
$CollectorSrc = "$RepoDir\scripts\claude-usage-collector.py"
$CollectorDst = "$BinDir\claude-usage-collector.py"

function Write-Step($num, $msg) { Write-Host "`n[$num/5] $msg" -ForegroundColor Yellow }
function Write-OK($msg) { Write-Host "  + $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  ! $msg" -ForegroundColor DarkYellow }
function Write-Err($msg) { Write-Host "  X $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "=======================================" -ForegroundColor White
Write-Host "  Claude Usage Monitor - Windows Setup " -ForegroundColor White
Write-Host "=======================================" -ForegroundColor White

# ── 1. Check Python ──
Write-Step 1 "Checking Python..."
$python = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3") {
            $python = $cmd
            break
        }
    } catch {}
}
if (-not $python) {
    Write-Err "Python 3 not found."
    Write-Host "  Download from https://www.python.org/downloads/" -ForegroundColor Gray
    Write-Host "  IMPORTANT: Check 'Add Python to PATH' during install." -ForegroundColor Gray
    Write-Host ""
    Write-Host "  After installing Python, re-run this script." -ForegroundColor Gray
    Read-Host "Press Enter to exit"
    exit 1
}
Write-OK "Found $( & $python --version 2>&1)"

# Install cryptography
Write-Host "  Installing cryptography..." -ForegroundColor Gray
& $python -m pip install --quiet cryptography 2>$null

# ── 2. Install collector ──
Write-Step 2 "Installing data collector..."
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
New-Item -ItemType Directory -Force -Path $ClaudeDir | Out-Null
Copy-Item $CollectorSrc $CollectorDst -Force
Write-OK "Collector: $CollectorDst"

# ── 3. Schedule Task ──
Write-Step 3 "Setting up scheduled task (runs every 60s)..."
$taskName = "ClaudeUsageCollector"
$action = New-ScheduledTaskAction -Execute $python -Argument "`"$CollectorDst`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration ([TimeSpan]::MaxValue)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "Claude Usage Monitor - data collector" | Out-Null
Write-OK "Scheduled task '$taskName' created"

# ── 4. Build tray app ──
Write-Step 4 "Building tray app..."
$hasCargo = $false
$hasNode = $false
try { cargo --version 2>$null | Out-Null; $hasCargo = $true } catch {}
try { node --version 2>$null | Out-Null; $hasNode = $true } catch {}

$tauriExe = $null
if ($hasCargo -and $hasNode) {
    Write-Host "  Compiling... (this takes 3-8 minutes)" -ForegroundColor Gray
    Push-Location "$RepoDir\tauri-app"
    $buildLog = "$RepoDir\tauri-build.log"
    & npm install --silent *>&1 | Out-File $buildLog
    Write-Host "  Compiling... (3-8 minutes)" -ForegroundColor Gray
    & npx tauri build *>&1 | Out-File $buildLog -Append
    $builtExe = "src-tauri\target\release\claude-usage-tray.exe"
    if (Test-Path $builtExe) {
        Copy-Item $builtExe "$BinDir\claude-usage-tray.exe" -Force
        $tauriExe = "$BinDir\claude-usage-tray.exe"
        Write-OK "Tray app: $tauriExe"
    } else {
        Write-Warn "Build failed. See: $buildLog"
    }
    Pop-Location
} else {
    Write-Warn "Rust + Node.js required to build from source."
    Write-Host "  Rust:    https://rustup.rs" -ForegroundColor Gray
    Write-Host "  Node.js: https://nodejs.org" -ForegroundColor Gray
}

# Check for pre-built binary in releases
if (-not $tauriExe) {
    $prebuilt = "$RepoDir\releases\claude-usage-tray.exe"
    if (Test-Path $prebuilt) {
        Copy-Item $prebuilt "$BinDir\claude-usage-tray.exe" -Force
        $tauriExe = "$BinDir\claude-usage-tray.exe"
        Write-OK "Using pre-built binary: $tauriExe"
    }
}

# ── 5. First run + autostart ──
Write-Step 5 "Testing data collection..."

# Structured health check — exposes silent decrypt failures and gives actionable advice
& $python $CollectorDst --health-check
$hcExit = $LASTEXITCODE
if ($hcExit -ne 0) {
    Write-Host ""
    Write-Warn "Widget will run in Offline mode (local estimates only)."
    Write-Host "  Follow the advice above, then run:" -ForegroundColor Gray
    Write-Host "    python $CollectorDst --health-check" -ForegroundColor Gray
    Write-Host "  to re-check without reinstalling." -ForegroundColor Gray
}

# Generate initial data regardless — offline mode still gives useful info
& $python $CollectorDst 2>$null
Write-OK "Initial data generated at $ClaudeDir\widget-data.json"

# Add to startup
if ($tauriExe) {
    $startupDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
    $shortcutPath = "$startupDir\Claude Usage Monitor.lnk"
    $WScriptShell = New-Object -ComObject WScript.Shell
    $shortcut = $WScriptShell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $tauriExe
    $shortcut.Description = "Claude Usage Monitor"
    $shortcut.Save()
    Write-OK "Added to Windows startup"
}

# ── Done ──
Write-Host ""
Write-Host "=======================================" -ForegroundColor White
Write-Host "  Installation Complete!               " -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor White
Write-Host ""
if ($tauriExe) {
    Write-Host "  Tray app: $tauriExe" -ForegroundColor White
    Write-Host "  Click the tray icon to open, or press Super+Shift+C" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Starting tray app..." -ForegroundColor Gray
    Start-Process $tauriExe
} else {
    Write-Host "  Collector installed. Data updates every 60 seconds." -ForegroundColor White
    Write-Host "  To get the tray app, install Rust + Node.js and re-run." -ForegroundColor Gray
}
Write-Host ""
Write-Host "  Data refreshes every 60s from claude.ai." -ForegroundColor Gray
Write-Host "  Reads browser cookies automatically - no API keys needed." -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to close"
