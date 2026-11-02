$ErrorActionPreference = 'Stop'
$hostRoot = $PSScriptRoot
$guiPython = Join-Path $hostRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $guiPython)) {
    throw 'First create host/.venv and install requirements-gui.txt.'
}
& $guiPython -m pip install 'pyinstaller>=6,<7'
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installation failed.' }
Push-Location -LiteralPath $hostRoot
try {
    & $guiPython -m PyInstaller --noconfirm --clean --windowed --onedir --distpath dist_ui --name ClockBridgeStudio --hidden-import serial.tools.list_ports_windows clock_bridge_gui.py
    if ($LASTEXITCODE -ne 0) { throw 'GUI build failed.' }
    $guiOutput = Join-Path $hostRoot 'dist_ui\ClockBridgeStudio'
    Copy-Item -LiteralPath (Join-Path $hostRoot 'readme_gui.md') -Destination (Join-Path $guiOutput 'readme_gui.md')
    Copy-Item -LiteralPath (Join-Path $hostRoot 'examples') -Destination (Join-Path $guiOutput 'examples') -Recurse -Force
    Copy-Item -LiteralPath (Join-Path $hostRoot 'third_party_notices.txt') -Destination $guiOutput
    & $guiPython (Join-Path $hostRoot 'collect_runtime_licenses.py') (Join-Path $guiOutput 'licenses')
    if ($LASTEXITCODE -ne 0) { throw 'License collection failed.' }
    Write-Output "GUI ready: $guiOutput\ClockBridgeStudio.exe"
} finally {
    Pop-Location
}
