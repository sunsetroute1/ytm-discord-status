@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Create the venv first: python -m venv .venv ^& .venv\Scripts\pip install -e .
  exit /b 1
)
".venv\Scripts\python.exe" -m ytm_discord %*
