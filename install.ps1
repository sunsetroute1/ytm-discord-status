#Requires -Version 5.1
<#
.SYNOPSIS
  Install YouTube Music -> Discord status updater (hidden background app).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -ClientId 1536877982222913626 -StartWithWindows -StartNow
#>
param(
  [string]$ClientId = "",
  [switch]$Build,
  [switch]$StartWithWindows,
  [switch]$StartNow
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ytm-discord-status"
$DataDir = Join-Path $env:LOCALAPPDATA "ytm-discord-status"
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\YouTube Music Discord Status"
$Startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

Write-Step "Install directory: $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null

# Stop any running copies before replacing the exe.
Get-Process ytm-discord -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 400

$exeSource = Join-Path $Root "dist\ytm-discord.exe"
if ($Build -or -not (Test-Path $exeSource)) {
  Write-Step "Building standalone hidden exe (first time can take a few minutes)..."
  if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    python -m venv "$Root\.venv"
    & "$Root\.venv\Scripts\python.exe" -m pip install -U pip
  }
  & "$Root\.venv\Scripts\python.exe" -m pip install -e . pyinstaller | Out-Null
  & "$Root\.venv\Scripts\python.exe" "$Root\scripts\build_exe.py"
  if (-not (Test-Path $exeSource)) { throw "Build failed: $exeSource not found" }
}

Write-Step "Copying files..."
Copy-Item -Force $exeSource (Join-Path $InstallDir "ytm-discord.exe")
Copy-Item -Force (Join-Path $Root "config.example.json") (Join-Path $InstallDir "config.example.json")
Copy-Item -Force (Join-Path $Root "docs\INSTALL.md") (Join-Path $InstallDir "INSTALL.md")
Copy-Item -Force (Join-Path $Root "scripts\stop.ps1") (Join-Path $InstallDir "stop.ps1")

$configPath = Join-Path $DataDir "config.json"
if (-not (Test-Path $configPath)) {
  Write-Step "Creating config at $configPath"
  Copy-Item (Join-Path $InstallDir "config.example.json") $configPath
}

if (-not $ClientId) {
  $existing = Get-Content $configPath -Raw | ConvertFrom-Json
  if ($existing.client_id -and $existing.client_id -ne "YOUR_DISCORD_APP_CLIENT_ID") {
    $ClientId = [string]$existing.client_id
  }
}

if (-not $ClientId) {
  Write-Host ""
  Write-Host "Create a Discord app named 'YouTube Music' here:" -ForegroundColor Yellow
  Write-Host "  https://discord.com/developers/applications"
  Write-Host "Copy the Application ID, then paste it below."
  $ClientId = Read-Host "Discord Application ID"
}

if (-not ($ClientId -match '^\d+$')) {
  throw "Client ID must be numeric (Discord Application ID)."
}

$cfg = Get-Content $configPath -Raw | ConvertFrom-Json
$cfg.client_id = $ClientId
if (-not ($cfg.PSObject.Properties.Name -contains "show_artwork")) {
  $cfg | Add-Member -NotePropertyName show_artwork -NotePropertyValue $true
}
($cfg | ConvertTo-Json -Depth 6) + "`n" | Set-Content -Path $configPath -Encoding UTF8

# Direct shortcut to windowless exe (config is auto-discovered in %LOCALAPPDATA%\ytm-discord-status).
$WshShell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $StartMenu "YouTube Music Discord Status.lnk"
$sc = $WshShell.CreateShortcut($shortcutPath)
$sc.TargetPath = Join-Path $InstallDir "ytm-discord.exe"
$sc.WorkingDirectory = $InstallDir
$sc.WindowStyle = 7  # Minimized; exe is built with --noconsole so no window appears
$sc.Description = "Hidden YouTube Music -> Discord presence updater"
$sc.Save()

$stopShortcut = Join-Path $StartMenu "Stop YouTube Music Discord Status.lnk"
$scStop = $WshShell.CreateShortcut($stopShortcut)
$scStop.TargetPath = "powershell.exe"
$scStop.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\stop.ps1`""
$scStop.WorkingDirectory = $InstallDir
$scStop.WindowStyle = 7
$scStop.Description = "Stop the hidden updater"
$scStop.Save()

if ($StartWithWindows) {
  Write-Step "Adding Startup entry..."
  $startupLnk = Join-Path $Startup "YouTube Music Discord Status.lnk"
  Copy-Item -Force $shortcutPath $startupLnk
}

$uninstall = Join-Path $InstallDir "uninstall.ps1"
@"
`$ErrorActionPreference = 'Stop'
Get-Process ytm-discord -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath '$shortcutPath' -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath '$stopShortcut' -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path `$env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\YouTube Music Discord Status.lnk') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath '$InstallDir' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'Removed app files. Config/logs left at $DataDir (delete manually if desired).'
"@ | Set-Content -Path $uninstall -Encoding UTF8

Write-Host ""
Write-Host "Installed (runs hidden - no console window)." -ForegroundColor Green
Write-Host "  App:    $InstallDir"
Write-Host "  Config: $configPath"
Write-Host "  Logs:   $(Join-Path $DataDir 'ytm-discord.log')"
Write-Host "  Start:  Start Menu -> YouTube Music Discord Status"
Write-Host "  Stop:   Start Menu -> Stop YouTube Music Discord Status"
Write-Host ""
Write-Host "Album art uses Deezer/iTunes CDNs (Discord cannot proxy catbox reliably)." -ForegroundColor Yellow
Write-Host "No Discord restart needed - just open your profile card after a track change."
Write-Host ""

if ($StartNow) {
  Write-Step "Starting hidden updater..."
  $exePath = Join-Path $InstallDir "ytm-discord.exe"
  Start-Process -FilePath $exePath -WorkingDirectory $InstallDir -WindowStyle Hidden
}
