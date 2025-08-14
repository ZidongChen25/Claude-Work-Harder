@echo off
REM Windows batch script to run Claude scheduler
REM Equivalent of run_daemon.sh for Windows

REM Set PATH to include common Python locations
set PATH=%PATH%;C:\Python312;C:\Python311;C:\Python310;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310;C:\Program Files\Python312;C:\Program Files\Python311;C:\Program Files\Python310

REM Change to the directory where this script is located
cd /d "%~dp0"

REM Run the Python scheduler
python claude_scheduler.py