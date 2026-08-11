#Requires -Version 5.1
Get-Process ytm-discord -ErrorAction SilentlyContinue | Stop-Process -Force
Write-Host "Stopped ytm-discord."
