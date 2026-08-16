#Requires -Version 5.1
$ErrorActionPreference = "SilentlyContinue"

$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ytm-discord-status"
$DataDir = Join-Path $env:LOCALAPPDATA "ytm-discord-status"
$ExePath = Join-Path $InstallDir "ytm-discord.exe"
$WatchScript = Join-Path $InstallDir "watch_discord.ps1"
$Helper = Join-Path $InstallDir "start_hidden.ps1"

Remove-Item -LiteralPath (Join-Path $DataDir "watchdog.paused") -Force -ErrorAction SilentlyContinue

. $Helper

if (-not (Get-Process -Name "ytm-discord" -ErrorAction SilentlyContinue)) {
  Start-HiddenExe -FilePath $ExePath -WorkingDirectory $InstallDir
}

$watchRunning = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -like "*watch_discord.ps1*" }
$wscriptRunning = Get-CimInstance Win32_Process -Filter "Name='wscript.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -like "*run_watchdog_hidden.vbs*" }
if (-not $watchRunning -and -not $wscriptRunning -and (Test-Path $WatchScript)) {
  Start-HiddenPowerShellFile -ScriptPath $WatchScript -WorkingDirectory $InstallDir
}
