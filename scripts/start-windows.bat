@echo off
REM Starts the dashboard and opens it in your browser. Keep this window open while you use it; close it to stop.
title Indian Stock Analyst - keep this window open while you use the dashboard
cd /d "%~dp0.."
set PORT=8501
REM Already running? Just open the browser.
powershell -NoProfile -Command "try { (New-Object Net.Sockets.TcpClient('127.0.0.1', %PORT%)).Close(); exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  start "" http://localhost:%PORT%
  exit /b 0
)
if not exist ".venv\Scripts\python.exe" (
  echo The app is not installed yet. Run the installer line from the README first.
  pause
  exit /b 1
)
REM open the browser as soon as the server answers
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "for ($i=0; $i -lt 120; $i++) { try { (New-Object Net.Sockets.TcpClient('127.0.0.1', %PORT%)).Close(); Start-Process 'http://localhost:%PORT%'; break } catch { Start-Sleep -Milliseconds 700 } }"
echo Starting Indian Stock Analyst on http://localhost:%PORT% ...
".venv\Scripts\python.exe" -m streamlit run app.py --server.port %PORT%
echo.
echo The dashboard stopped. If you saw an error above, run the installer line again to repair it.
pause
