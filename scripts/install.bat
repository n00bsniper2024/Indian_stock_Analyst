@echo off
REM One-time setup on Windows. Double-click or run from the repo folder.
cd /d "%~dp0.."
python -m venv .venv || (echo Install Python 3.10+ from https://www.python.org/downloads/ and tick "Add to PATH" && pause && exit /b 1)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Installed. Put your API key in .env (optional), then run scripts\run.bat
pause
