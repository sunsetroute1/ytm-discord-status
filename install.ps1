#Requires -Version 5.1
<#
.SYNOPSIS
  Install YouTube Music -> Discord status updater for the current user.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -ClientId 1536877982222913626

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -Build
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

$exeSource = Join-Path $Root "dist\ytm-discord.exe"
if ($Build -or -not (Test-Path $exeSource)) {
  Write-Step "Building standalone exe (first time can take a few minutes)..."
  & "$Root\.venv\Scripts\python.exe" -m pip install -e . pyinstaller | Out-Null
  if (-not $?) {
    python -m venv "$Root\.venv"
    & "$Root\.venv\Scripts\python.exe" -m pip install -U pip
    & "$Root\.venv\Scripts\python.exe" -m pip install -e . pyinstaller
  }
  & "$Root\.venv\Scripts\python.exe" "$Root\scripts\build_exe.py"
  if (-not (Test-Path $exeSource)) { throw "Build failed: $exeSource not found" }
}

Write-Step "Copying files..."
Copy-Item -Force $exeSource (Join-Path $InstallDir "ytm-discord.exe")
Copy-Item -Force (Join-Path $Root "config.example.json") (Join-Path $InstallDir "config.example.json")
Copy-Item -Force (Join-Path $Root "docs\INSTALL.md") (Join-Path $InstallDir "INSTALL.md")

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
($cfg | ConvertTo-Json -Depth 5) + "`n" | Set-Content -Path $configPath -Encoding UTF8

# Launcher sets config env so the exe always finds AppData config.
$launcher = Join-Path $InstallDir "Start YTM Discord Status.cmd"
@"
@echo off
set "YTM_DISCORD_CONFIG=$configPath"
start "" "$InstallDir\ytm-discord.exe"
"@ | Set-Content -Path $launcher -Encoding ASCII

$WshShell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $StartMenu "YouTube Music Discord Status.lnk"
$sc = $WshShell.CreateShortcut($shortcutPath)
$sc.TargetPath = "$InstallDir\ytm-discord.exe"
$sc.WorkingDirectory = $InstallDir
$sc.WindowStyle = 1
$sc.Description = "Push YouTube Music now-playing into Discord"
$sc.Arguments = ""
# Env var for shortcut: use the cmd launcher instead
$sc.TargetPath = $launcher
$sc.Save()

# Better: shortcut directly to exe with a tiny wrapper env via cmd /c
$sc2 = $WshShell.CreateShortcut($shortcutPath)
$sc2.TargetPath = "cmd.exe"
$sc2.Arguments = "/c `"set YTM_DISCORD_CONFIG=$configPath&& `"$InstallDir\ytm-discord.exe`"`""
$sc2.WorkingDirectory = $InstallDir
$sc2.WindowStyle = 1
$sc2.Description = "Push YouTube Music now-playing into Discord"
$sc2.Save()

if ($StartWithWindows) {
  Write-Step "Adding Startup entry..."
  $startupLnk = Join-Path $Startup "YouTube Music Discord Status.lnk"
  Copy-Item -Force $shortcutPath $startupLnk
}

$uninstall = Join-Path $InstallDir "uninstall.ps1"
@"
`$ErrorActionPreference = 'Stop'
Remove-Item -LiteralPath '$shortcutPath' -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath (Join-Path `$env:APPDATA 'Microsoft\Windows\Start Menu\Programs\Startup\YouTube Music Discord Status.lnk') -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath '$InstallDir' -Recurse -Force -ErrorAction SilentlyContinue
Write-Host 'Removed app files. Config left at $DataDir (delete manually if desired).'
"@ | Set-Content -Path $uninstall -Encoding UTF8

Write-Host ""
Write-Host "Installed." -ForegroundColor Green
Write-Host "  App:    $InstallDir"
Write-Host "  Config: $configPath"
Write-Host "  Start:  Start Menu -> YouTube Music Discord Status"
Write-Host ""
Write-Host "Where your status appears in Discord:" -ForegroundColor Yellow
Write-Host "  1) User Settings -> Activity Privacy -> turn ON 'Display current activity as a status'"
Write-Host "  2) Click your avatar (bottom-left) - the profile card shows Listening to YouTube Music"
Write-Host "  3) Or check yourself in a server member list"
Write-Host "  Note: this is NOT the Spotify green panel - that UI is Spotify-only."
Write-Host ""

if ($StartNow) {
  Write-Step "Starting..."
  Start-Process cmd.exe -ArgumentList "/c `"set YTM_DISCORD_CONFIG=$configPath&& `"$InstallDir\ytm-discord.exe`"`""
}
