# =====================================================
# Claude Usage Monitor - Windows AppBar installer
# Replaces the Tauri build path with a pure-Python
# AppBar widget docked to the top of the screen.
#
# Requirements: Python 3.10+, no admin rights needed.
# =====================================================

$ErrorActionPreference = "Stop"
$RepoDir       = Split-Path -Parent $MyInvocation.MyCommand.Path
$ClaudeDir     = "$env:USERPROFILE\.claude"
$BinDir        = "$env:LOCALAPPDATA\ClaudeUsageMonitor"
$WidgetDir     = "$BinDir\widget"
$CollectorSrc  = "$RepoDir\scripts\claude-usage-collector.py"
$CollectorDst  = "$BinDir\claude-usage-collector.py"
$WidgetSrc     = "$RepoDir\windows-widget"

function Write-Step($num, $total, $msg) { Write-Host "`n[$num/$total] $msg" -ForegroundColor Yellow }
function Write-OK($msg)   { Write-Host "  + $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "  ! $msg" -ForegroundColor DarkYellow }
function Write-Err($msg)  { Write-Host "  X $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "=========================================" -ForegroundColor White
Write-Host "  Claude Usage Monitor - Windows AppBar " -ForegroundColor White
Write-Host "=========================================" -ForegroundColor White

# --- 1. Check Python 3.10+ ---
Write-Step 1 6 "Locating Python 3.10+..."
$python = $null
$pythonw = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -eq 3 -and $minor -ge 10) {
                $python = $cmd
                break
            }
        }
    } catch {}
}
if (-not $python) {
    Write-Err "Python 3.10+ not found."
    Write-Host "  Install from https://www.python.org/downloads/ (check 'Add to PATH')." -ForegroundColor Gray
    Read-Host "Press Enter to exit"; exit 1
}
Write-OK ("Found: " + ( & $python --version 2>&1))

# Locate pythonw.exe (GUI launcher, no console window)
$pyPath = (& $python -c "import sys; print(sys.executable)").Trim()
$pyDir  = Split-Path $pyPath -Parent
$pythonw = Join-Path $pyDir "pythonw.exe"
if (-not (Test-Path $pythonw)) {
    Write-Warn "pythonw.exe not found next to python.exe - widget will run with a console window."
    $pythonw = $pyPath
}

# --- 2. Create dirs ---
Write-Step 2 6 "Preparing install dirs..."
New-Item -ItemType Directory -Force -Path $BinDir    | Out-Null
New-Item -ItemType Directory -Force -Path $WidgetDir | Out-Null
New-Item -ItemType Directory -Force -Path $ClaudeDir | Out-Null
Write-OK "Base:   $BinDir"
Write-OK "Widget: $WidgetDir"

# --- 3. Copy files ---
Write-Step 3 6 "Copying collector + widget files..."
Copy-Item $CollectorSrc $CollectorDst -Force
Write-OK "Collector copied"

Copy-Item "$WidgetSrc\*.py"    $WidgetDir -Force
Copy-Item "$WidgetSrc\requirements.txt" $WidgetDir -Force
$assetsSrc = "$WidgetSrc\assets"
$assetsDst = "$WidgetDir\assets"
if (Test-Path $assetsDst) { Remove-Item $assetsDst -Recurse -Force }
Copy-Item $assetsSrc $assetsDst -Recurse -Force
Write-OK "Widget files copied"

# --- 4. Install Python deps ---
Write-Step 4 6 "Installing Python dependencies..."
& $python -m pip install --quiet --upgrade pip 2>$null
& $python -m pip install --quiet -r "$WidgetDir\requirements.txt"
if ($LASTEXITCODE -ne 0) {
    Write-Warn "pip install had warnings. Trying with --user..."
    & $python -m pip install --user -r "$WidgetDir\requirements.txt"
}
Write-OK "PySide6 + pywin32 + cryptography installed"

# --- 5. Scheduled Task for collector (user scope, no admin) ---
Write-Step 5 6 "Creating scheduled task for collector (every 60s)..."
$taskName = "ClaudeUsageCollector"
$action   = New-ScheduledTaskAction -Execute $pythonw -Argument "-X utf8 `"$CollectorDst`""
$trigger  = New-ScheduledTaskTrigger -Once -At (Get-Date) `
             -RepetitionInterval (New-TimeSpan -Minutes 1) `
             -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet `
             -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
             -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Claude Usage Monitor - data collector" | Out-Null
Write-OK "Scheduled task '$taskName' registered"

# Run collector once to seed data
Write-Host "  Running collector once..." -ForegroundColor Gray
$env:PYTHONIOENCODING = "utf-8"
& $python -X utf8 $CollectorDst 2>$null | Out-Null
if (Test-Path "$ClaudeDir\widget-data.json") {
    Write-OK "Initial widget-data.json generated"
} else {
    Write-Warn "widget-data.json not generated - make sure you are logged into claude.ai"
}

# --- 6. Startup shortcut ---
Write-Step 6 6 "Adding widget to Windows startup..."
$startupDir  = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$shortcutPath = "$startupDir\Claude Usage Widget.lnk"
$mainPy       = Join-Path $WidgetDir "main.py"
$WScriptShell = New-Object -ComObject WScript.Shell
$shortcut     = $WScriptShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath       = $pythonw
$shortcut.Arguments        = "`"$mainPy`""
$shortcut.WorkingDirectory = $WidgetDir
$shortcut.Description      = "Claude Usage Monitor (AppBar widget)"
$shortcut.IconLocation     = "$WidgetDir\assets\sprites\claude-logo.png,0"
$shortcut.Save()
Write-OK "Shortcut created at Startup folder"

# --- Launch now ---
Write-Host ""
Write-Host "=========================================" -ForegroundColor White
Write-Host "  Installation complete!                 " -ForegroundColor Green
Write-Host "=========================================" -ForegroundColor White
Write-Host ""
Write-Host "  Starting the widget..." -ForegroundColor Gray
Start-Process -FilePath $pythonw -ArgumentList "`"$mainPy`"" -WorkingDirectory $WidgetDir
Write-Host ""
Write-Host "  The top strip should appear after a second." -ForegroundColor Gray
Write-Host "  Click it to open the full popup." -ForegroundColor Gray
Write-Host "  Collector refreshes every 60s." -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to close"
