@echo off
REM One-time setup: installs Python packages, runs the screener once,
REM and schedules it for 4:30 PM every weekday.
cd /d "%~dp0"
where python >nul 2>nul || (echo Python not found. Install it from python.org and tick "Add python.exe to PATH". & pause & exit /b 1)
echo Installing packages...
python -m pip install --upgrade yfinance pandas numpy lxml requests
echo.
echo Running the screener once (takes a few minutes)...
python screener.py
echo.
echo Scheduling nightly run at 4:30 PM, Mon-Fri...
schtasks /Create /SC WEEKLY /D MON,TUE,WED,THU,FRI /ST 16:30 /TN "Swing Screener" /TR "\"%~dp0run_screener.bat\"" /F
echo.
echo Done. Results: %~dp0output\latest.html
start "" "%~dp0output\latest.html"
pause
