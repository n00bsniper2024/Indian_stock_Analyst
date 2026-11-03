@echo off
REM Windows installer for a downloaded copy (GitHub: Code -> Download ZIP -> extract -> double-click this file).
REM No Python needed: it installs "uv", which brings its own Python 3.12, into your user folder.
REM The app is installed right here, in the folder you extracted. Then use the Desktop / Start menu shortcut.
cd /d "%~dp0.."
set "ISA_SOURCE_DIR=%CD%"
set "ISA_HOME=%CD%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0get.ps1"
if errorlevel 1 (
  echo.
  echo Installation failed - see the message above.
)
pause
