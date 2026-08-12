#Requires -Version 5.1
<#
.SYNOPSIS
  Keep ytm-discord running whenever Discord desktop is open.

  Registered at logon by install.ps1. Starts the updater when Discord appears
  and leaves it alone while Discord stays up (updater reconnects itself).
#>
$ErrorActionPreference = "SilentlyContinue"

$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\ytm-discord-status"
$ExePath = Join-Path $InstallDir "ytm-discord.exe"
$LogDir = Join-Path $env:LOCALAPPDATA "ytm-discord-status"
$LogPath = Join-Path $LogDir "watchdog.log"

function Write-WatchLog([string]$msg) {
  try {
    if (-not (Test-Path $LogDir)) {
      New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
    }
    $line = "{0:HH:mm:ss} {1}" -f (Get-Date), $msg
    Add-Content -Path $LogPath -Value $line -Encoding UTF8 -ErrorAction SilentlyContinue
  } catch {}
}

function Test-DiscordRunning {
  $names = @("Discord", "DiscordCanary", "DiscordPTB", "DiscordDevelopment")
  foreach ($n in $names) {
    if (Get-Process -Name $n -ErrorAction SilentlyContinue) {
      return $true
    }
  }
  return $false
}

function Test-UpdaterRunning {
  return [bool](Get-Process -Name "ytm-discord" -ErrorAction SilentlyContinue)
}

function Start-Updater {
  if (-not (Test-Path $ExePath)) {
    Write-WatchLog "Updater exe missing: $ExePath"
    return
  }
  if (Test-UpdaterRunning) {
    return
  }
  Write-WatchLog "Discord is up - starting ytm-discord"
  Start-Process -FilePath $ExePath -WorkingDirectory $InstallDir -WindowStyle Hidden
}

$pauseFlag = Join-Path $LogDir "watchdog.paused"
if (Test-Path $pauseFlag) {
  # Cleared at logon by the scheduled task starting a fresh session, or by Start Now.
  Remove-Item -LiteralPath $pauseFlag -Force -ErrorAction SilentlyContinue
  Write-WatchLog "Cleared pause flag from previous Stop"
}

Write-WatchLog "Watchdog started (poll Discord every 15s)"

while ($true) {
  try {
    if (Test-Path $pauseFlag) {
      Start-Sleep -Seconds 15
      continue
    }
    if (Test-DiscordRunning) {
      Start-Updater
    }
  } catch {
    Write-WatchLog ("Watch loop error: " + $_.Exception.Message)
  }
  Start-Sleep -Seconds 15
}
