@echo off
echo Launching Vehicle Report App...
REM Activate virtual environment if needed
REM call venv\Scripts\activate.bat

REM Start the Flask app
start "" py app.py

REM Optional: Open browser automatically
timeout /t 2 >nul
start http://localhost:5000
