# Claude Usage Monitor - Windows Uninstaller

$BinDir = "$env:LOCALAPPDATA\ClaudeUsageMonitor"
$ClaudeDir = "$env:USERPROFILE\.claude"

Write-Host "Removing Claude Usage Monitor..." -ForegroundColor Yellow

# Remove scheduled task
$task = Get-ScheduledTask -TaskName "ClaudeUsageCollector" -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName "ClaudeUsageCollector" -Confirm:$false
    Write-Host "  Removed scheduled task" -ForegroundColor Green
}

# Remove startup shortcut
$shortcut = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Claude Usage Monitor.lnk"
if (Test-Path $shortcut) {
    Remove-Item $shortcut -Force
    Write-Host "  Removed startup shortcut" -ForegroundColor Green
}

# Kill running instance
Get-Process -Name "claude-usage-tray" -ErrorAction SilentlyContinue | Stop-Process -Force

# Remove files
if (Test-Path $BinDir) {
    Remove-Item $BinDir -Recurse -Force
    Write-Host "  Removed $BinDir" -ForegroundColor Green
}

# Remove data files
foreach ($f in @("widget-data.json", "widget-config.json", "widget-status-prev.json")) {
    $p = "$ClaudeDir\$f"
    if (Test-Path $p) { Remove-Item $p -Force }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Read-Host "Press Enter to close"
