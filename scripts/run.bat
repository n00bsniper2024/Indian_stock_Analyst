@echo off
REM Start the dashboard on http://localhost:8501
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
if "%1"=="--demo" set ISA_DEMO=1
streamlit run app.py
