#Requires -Version 5.1
<#
.SYNOPSIS
  Install YouTube Music -> Discord status updater (hidden background app).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -ClientId 1536877982222913626 -Build -StartNow

  Auto-starts with Discord after reboot by default (logon watchdog). Use -NoAutoStart to skip.
#>
param(
  [string]$ClientId = "",
  [switch]$Build,
  [switch]$StartWithWindows, # kept for compat; auto-start is now default
  [switch]$NoAutoStart,
  [switch]$StartNow
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ytm-discord-status"
$DataDir = Join-Path $env:LOCALAPPDATA "ytm-discord-status"
$StartMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\YouTube Music Discord Status"
$Startup = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
$TaskName = "ytm-discord-status-watchdog"
$EnableAutoStart = -not $NoAutoStart

function Write-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }

function Register-DiscordWatchdog {
  param([string]$WatchScript)

  Write-Step "Registering Discord watchdog (starts updater when Discord is open)..."

  $wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
  $vbs = Join-Path $InstallDir "run_watchdog_hidden.vbs"
  $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"

  # Remove any previous registration (Startup lnk + task).
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
  $legacyStartup = Join-Path $Startup "YouTube Music Discord Status.lnk"
  Remove-Item -LiteralPath $legacyStartup -Force -ErrorAction SilentlyContinue

  if (Test-Path -LiteralPath $vbs) {
    $action = New-ScheduledTaskAction -Execute $wscript -Argument "//B `"$vbs`"" -WorkingDirectory $InstallDir
  } else {
    $arg = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$WatchScript`""
    $action = New-ScheduledTaskAction -Execute $psExe -Argument $arg -WorkingDirectory $InstallDir
  }
  $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
  # Give the desktop a moment; Discord often starts a few seconds after logon.
  $trigger.Delay = "PT20S"
  $settingsArgs = @{
    AllowStartIfOnBatteries = $true
    DontStopIfGoingOnBatteries = $true
    StartWhenAvailable = $true
    RestartCount = 3
    RestartInterval = (New-TimeSpan -Minutes 1)
    ExecutionTimeLimit = [TimeSpan]::Zero
  }
  # -Hidden is supported on modern Windows; ignore if the parameter is missing.
  try {
    $settings = New-ScheduledTaskSettingsSet @settingsArgs -Hidden
  } catch {
    $settings = New-ScheduledTaskSettingsSet @settingsArgs
  }
  $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

  Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Starts ytm-discord whenever Discord desktop is running (survives reboot)." `
    -Force | Out-Null

  # Kick the watchdog now so we don't wait for the next logon (no console flash).
  . (Join-Path $InstallDir "start_hidden.ps1")
  Start-HiddenPowerShellFile -ScriptPath $WatchScript -WorkingDirectory $InstallDir
}

Write-Step "Install directory: $InstallDir"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
New-Item -ItemType Directory -Force -Path $StartMenu | Out-Null

# Stop any running copies before replacing the exe (including Discord watchdog).
Get-Process ytm-discord -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -like '*watch_discord.ps1*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Get-CimInstance Win32_Process -Filter "Name='wscript.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -like '*run_watchdog_hidden.vbs*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 800

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
Copy-Item -Force (Join-Path $Root "scripts\start.ps1") (Join-Path $InstallDir "start.ps1")
Copy-Item -Force (Join-Path $Root "scripts\start_hidden.ps1") (Join-Path $InstallDir "start_hidden.ps1")
Copy-Item -Force (Join-Path $Root "scripts\watch_discord.ps1") (Join-Path $InstallDir "watch_discord.ps1")
Copy-Item -Force (Join-Path $Root "scripts\run_watchdog_hidden.vbs") (Join-Path $InstallDir "run_watchdog_hidden.vbs")

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
# Keep privacy defaults intact on upgrades (don't wipe user values if already set).
if (-not ($cfg.PSObject.Properties.Name -contains "allow_browsers")) {
  $cfg | Add-Member -NotePropertyName allow_browsers -NotePropertyValue $true
}
if (-not ($cfg.PSObject.Properties.Name -contains "browser_require_catalog_match")) {
  $cfg | Add-Member -NotePropertyName browser_require_catalog_match -NotePropertyValue $true
}
# Soft-upgrade: append newly shipped music apps missing from older explicit whitelists.
$upgradeIds = @("jellyfin")
if ($cfg.PSObject.Properties.Name -contains "whitelist" -and $cfg.whitelist) {
  $list = @($cfg.whitelist | ForEach-Object { [string]$_ })
  foreach ($id in $upgradeIds) {
    if ($list -notcontains $id) { $list += $id }
  }
  $cfg.whitelist = $list
}
($cfg | ConvertTo-Json -Depth 6) + "`n" | Set-Content -Path $configPath -Encoding UTF8

# Start Menu: start.ps1 clears pause flag, launches updater + Discord watchdog.
$WshShell = New-Object -ComObject WScript.Shell
$shortcutPath = Join-Path $StartMenu "YouTube Music Discord Status.lnk"
$sc = $WshShell.CreateShortcut($shortcutPath)
$sc.TargetPath = "powershell.exe"
$sc.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$InstallDir\start.ps1`""
$sc.WorkingDirectory = $InstallDir
$sc.WindowStyle = 7
$sc.Description = "Start music -> Discord presence updater (and Discord watchdog)"
$sc.Save()

$stopShortcut = Join-Path $StartMenu "Stop YouTube Music Discord Status.lnk"
$scStop = $WshShell.CreateShortcut($stopShortcut)
$scStop.TargetPath = "powershell.exe"
$scStop.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$InstallDir\stop.ps1`""
$scStop.WorkingDirectory = $InstallDir
$scStop.WindowStyle = 7
$scStop.Description = "Stop the hidden updater"
$scStop.Save()

$watchScript = Join-Path $InstallDir "watch_discord.ps1"
if ($EnableAutoStart -or $StartWithWindows) {
  Register-DiscordWatchdog -WatchScript $watchScript
} else {
  Write-Step "Skipping auto-start (-NoAutoStart)"
  Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
}

$uninstall = Join-Path $InstallDir "uninstall.ps1"
@"
`$ErrorActionPreference = 'SilentlyContinue'
Get-Process ytm-discord -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
  Where-Object { `$_.CommandLine -and `$_.CommandLine -like '*watch_discord.ps1*' } |
  ForEach-Object { Stop-Process -Id `$_.ProcessId -Force -ErrorAction SilentlyContinue }
Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false -ErrorAction SilentlyContinue
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
if ($EnableAutoStart -or $StartWithWindows) {
  Write-Host "  Auto:   Starts with Discord after login (task: $TaskName)" -ForegroundColor Cyan
}
Write-Host ""
Write-Host "Album art uses Deezer/iTunes CDNs (Discord cannot proxy catbox reliably)." -ForegroundColor Yellow
Write-Host "Browser/Jellyfin tracks need a Deezer/iTunes catalog match (movies/TV ignored)." -ForegroundColor Yellow
Write-Host "No Discord restart needed - just open your profile card after a track change."
Write-Host ""

if ($StartNow) {
  Write-Step "Starting hidden updater..."
  Remove-Item -LiteralPath (Join-Path $DataDir "watchdog.paused") -Force -ErrorAction SilentlyContinue
  . (Join-Path $InstallDir "start_hidden.ps1")
  $exePath = Join-Path $InstallDir "ytm-discord.exe"
  Start-HiddenExe -FilePath $exePath -WorkingDirectory $InstallDir
}
