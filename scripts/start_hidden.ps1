#Requires -Version 5.1
<#
.SYNOPSIS
  Shared helpers to start processes with no visible window.
#>

function Start-HiddenExe {
  param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string]$WorkingDirectory = "",
    [string]$Arguments = ""
  )
  if (-not (Test-Path -LiteralPath $FilePath)) {
    throw "Missing executable: $FilePath"
  }
  $work = if ($WorkingDirectory) { $WorkingDirectory } else { Split-Path -Parent $FilePath }
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FilePath
  $psi.WorkingDirectory = $work
  $psi.Arguments = $Arguments
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
  [void][System.Diagnostics.Process]::Start($psi)
}

function Start-HiddenPowerShellFile {
  param(
    [Parameter(Mandatory = $true)][string]$ScriptPath,
    [string]$WorkingDirectory = ""
  )
  if (-not (Test-Path -LiteralPath $ScriptPath)) {
    throw "Missing script: $ScriptPath"
  }
  $psExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
  $work = if ($WorkingDirectory) { $WorkingDirectory } else { Split-Path -Parent $ScriptPath }
  # Prefer wscript so even the PowerShell host never flashes a console.
  $vbs = Join-Path $work "run_watchdog_hidden.vbs"
  if (Test-Path -LiteralPath $vbs) {
    $wscript = Join-Path $env:SystemRoot "System32\wscript.exe"
    Start-HiddenExe -FilePath $wscript -WorkingDirectory $work -Arguments "//B `"$vbs`""
    return
  }
  Start-HiddenExe -FilePath $psExe -WorkingDirectory $work -Arguments (
    "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`""
  )
}
