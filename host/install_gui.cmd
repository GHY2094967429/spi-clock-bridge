@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements-gui-lock.txt
if errorlevel 1 goto failed
start "" ".venv\Scripts\pythonw.exe" "clock_bridge_gui.py"
exit /b
:failed
echo 安装失败。请确认已安装 Python 3.10 或以上，并可连接 Python 包下载站。
pause
exit /b 1
