# ═══════════════════════════════════════════════════
# Claude Usage Monitor - Windows Uninstaller
# ═══════════════════════════════════════════════════

$ErrorActionPreference = "SilentlyContinue"
$BinDir = "$env:LOCALAPPDATA\ClaudeUsageMonitor"
$ClaudeDir = "$env:USERPROFILE\.claude"

Write-Host ""
Write-Host "=======================================" -ForegroundColor White
Write-Host "  Claude Usage Monitor - Uninstaller   " -ForegroundColor White
Write-Host "=======================================" -ForegroundColor White
Write-Host ""

# ── Kill running tray app ──
$proc = Get-Process -Name "claude-usage-tray" -ErrorAction SilentlyContinue
if ($proc) {
    $proc | Stop-Process -Force
    Write-Host "  + Stopped running tray app" -ForegroundColor Green
}

# ── Remove scheduled task ──
$task = Get-ScheduledTask -TaskName "ClaudeUsageCollector" -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName "ClaudeUsageCollector" -Confirm:$false
    Write-Host "  + Removed scheduled task" -ForegroundColor Green
}

# ── Remove startup shortcut ──
$shortcut = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Claude Usage Monitor.lnk"
if (Test-Path $shortcut) {
    Remove-Item $shortcut -Force
    Write-Host "  + Removed startup shortcut" -ForegroundColor Green
}

# ── Remove binaries (collector + tray app) ──
if (Test-Path $BinDir) {
    Remove-Item $BinDir -Recurse -Force
    Write-Host "  + Removed $BinDir" -ForegroundColor Green
}

# ── Remove data files ──
$dataFiles = @("widget-data.json", "widget-config.json", "widget-status-prev.json", "widget-stats-cache.json")
$removed = 0
foreach ($f in $dataFiles) {
    $p = "$ClaudeDir\$f"
    if (Test-Path $p) {
        Remove-Item $p -Force
        $removed++
    }
}
if ($removed -gt 0) {
    Write-Host "  + Removed $removed data files from $ClaudeDir" -ForegroundColor Green
}

# ── Remove temp cookie files ──
$tempFiles = @(
    "$env:TEMP\claude_chrome_cookies.sqlite",
    "$env:TEMP\claude_chrome_cookies.sqlite-wal",
    "$env:TEMP\claude_chrome_cookies.sqlite-shm",
    "$env:TEMP\claude_chrome_cookies.sqlite-journal",
    "$env:TEMP\claude_cookies.sqlite"
)
foreach ($f in $tempFiles) {
    if (Test-Path $f) { Remove-Item $f -Force }
}

Write-Host ""
Write-Host "  Uninstall complete." -ForegroundColor Green
Write-Host ""
Read-Host "Press Enter to close"
