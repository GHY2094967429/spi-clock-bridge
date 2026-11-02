@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "dist_ui\ClockBridgeStudio\ClockBridgeStudio.exe" (
    start "" "dist_ui\ClockBridgeStudio\ClockBridgeStudio.exe"
    exit /b
)
if exist "dist\ClockBridgeStudio\ClockBridgeStudio.exe" (
    start "" "dist\ClockBridgeStudio\ClockBridgeStudio.exe"
    exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "clock_bridge_gui.py"
    exit /b
)
echo 首次使用请运行本目录的“install_gui.cmd”。
pause
