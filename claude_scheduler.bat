@echo off
REM Windows batch script to run Claude scheduler
REM Equivalent of run_daemon.sh for Windows

REM Set PATH to include common Python and npm locations
set PATH=%PATH%;C:\Python312;C:\Python311;C:\Python310;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python312;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python311;C:\Users\%USERNAME%\AppData\Local\Programs\Python\Python310;C:\Program Files\Python312;C:\Program Files\Python311;C:\Program Files\Python310

REM Add npm global paths for Claude CLI and claude-monitor
set PATH=%PATH%;%APPDATA%\npm;C:\Users\%USERNAME%\AppData\Roaming\npm;%APPDATA%\npm\node_modules\.bin

REM Also add local bin paths for Python packages (claude-monitor)
set PATH=%PATH%;%USERPROFILE%\.local\bin;%USERPROFILE%\AppData\Local\bin

REM Change to the directory where this script is located
cd /d "%~dp0"

REM Run the Python scheduler
python claude_scheduler.py