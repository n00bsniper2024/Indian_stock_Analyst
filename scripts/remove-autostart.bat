@echo off
REM Stop starting the dashboard at login, and stop the running copy.
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\IndianStockAnalyst.vbs" 2>nul
taskkill /f /im streamlit.exe >/dev/null 2>&1
echo Autostart removed.
pause
