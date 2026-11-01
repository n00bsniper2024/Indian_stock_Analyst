@echo off
REM Start the dashboard automatically (hidden) every time you log in to Windows.
REM Adds a small launcher to your Startup folder - no admin rights needed.
cd /d "%~dp0.."
if not exist ".venv\Scripts\streamlit.exe" (echo Run scripts\install.bat first. & pause & exit /b 1)
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "LAUNCHER=%STARTUP%\IndianStockAnalyst.vbs"
> "%LAUNCHER%" echo Set sh = CreateObject("WScript.Shell")
>> "%LAUNCHER%" echo sh.CurrentDirectory = "%CD%"
>> "%LAUNCHER%" echo sh.Run """%CD%\.venv\Scripts\streamlit.exe"" run app.py --server.headless=true", 0, False
start "" wscript.exe "%LAUNCHER%"
echo.
echo Done. The dashboard now starts in the background at every login.
echo Open http://localhost:8501   (first start can take ~20 seconds)
echo To undo: scripts\remove-autostart.bat
pause
