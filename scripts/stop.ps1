#Requires -Version 5.1
$ErrorActionPreference = "SilentlyContinue"

# Pause auto-restart until the next Windows logon (watchdog task starts fresh then).
$DataDir = Join-Path $env:LOCALAPPDATA "ytm-discord-status"
New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
Set-Content -Path (Join-Path $DataDir "watchdog.paused") -Value (Get-Date).ToString("o") -Encoding UTF8

Get-Process ytm-discord -ErrorAction SilentlyContinue | Stop-Process -Force

Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -and $_.CommandLine -like "*watch_discord.ps1*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "Stopped ytm-discord (auto-start paused until next login)."
