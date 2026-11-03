@echo off
REM Start the dashboard (same as the Desktop shortcut). Add --demo for offline demo data.
if "%1"=="--demo" set ISA_DEMO=1
call "%~dp0start-windows.bat"
