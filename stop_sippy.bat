@echo off
if not exist "%~dp0sippy.pid" (
  echo Sippy is not running.
  exit /b
)
set /p PID=<"%~dp0sippy.pid"
taskkill /PID %PID% /F >nul 2>&1
del "%~dp0sippy.pid" >nul 2>&1
echo Sippy stopped. Bye bye!
