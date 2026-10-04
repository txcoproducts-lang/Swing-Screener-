@echo off
REM Runs the screener and opens the results. Used by the nightly scheduled task.
cd /d "%~dp0"
python screener.py > output_log.txt 2>&1
start "" "%~dp0output\latest.html"
