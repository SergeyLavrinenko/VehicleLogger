@echo off
chcp 65001 >nul
title device-sim
cd /d "%~dp0"
where node >nul 2>&1
if errorlevel 1 (
  echo Node.js not found in PATH. Install Node 18+ and try again.
  pause
  exit /b 1
)
node sim.js %*
echo.
echo --- exited ---
pause
