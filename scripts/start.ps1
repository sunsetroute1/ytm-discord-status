#Requires -Version 5.1
$ErrorActionPreference = "SilentlyContinue"

$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ytm-discord-status"
$DataDir = Join-Path $env:LOCALAPPDATA "ytm-discord-status"
$ExePath = Join-Path $InstallDir "ytm-discord.exe"
$WatchScript = Join-Path $InstallDir "watch_discord.ps1"

Remove-Item -LiteralPath (Join-Path $DataDir "watchdog.paused") -Force -ErrorAction SilentlyContinue

if (-not (Get-Process -Name "ytm-discord" -ErrorAction SilentlyContinue)) {
  Start-Process -FilePath $ExePath -WorkingDirectory $InstallDir -WindowStyle Hidden
}

$watchRunning = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -like "*watch_discord.ps1*" }
if (-not $watchRunning -and (Test-Path $WatchScript)) {
  $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
  Start-Process -FilePath $psExe -ArgumentList "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$WatchScript`"" -WorkingDirectory $InstallDir -WindowStyle Hidden
}
