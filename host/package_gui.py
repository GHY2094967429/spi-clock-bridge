"""Package the portable Windows runtime and standalone GUI sources."""
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import zipfile


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(__file__).resolve().parent
    runtime = root / "dist_ui/ClockBridgeStudio"
    executable = runtime / "ClockBridgeStudio.exe"
    if not executable.is_file():
        raise SystemExit("Run build_gui.ps1 first")
    source_files = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in
                          (".py", ".txt", ".md", ".ps1", ".cmd"))
    manifest = {
        "application": "Clock Bridge Studio",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "PySide6-Essentials": metadata.version("PySide6-Essentials"),
        "pyserial": metadata.version("pyserial"),
        "PyInstaller": metadata.version("pyinstaller"),
        "hardware_tested": False,
        "executable_sha256": sha256(executable),
        "source_sha256": {p.name: sha256(p) for p in source_files},
    }
    (runtime / "build_info.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    output = root / "dist_ui/ClockBridgeStudio_Windows_x64.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(runtime.rglob("*")):
            if path.is_file():
                archive.write(path, "ClockBridgeStudio/" + path.relative_to(runtime).as_posix())
    with zipfile.ZipFile(root / "dist_ui/ClockBridgeStudio_Qt_Source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        examples = sorted(p for p in (root / "examples").iterdir() if p.suffix in (".csv", ".py"))
        for path in source_files + examples:
            archive.write(path, "ClockBridgeStudio_Qt_Source/" + path.relative_to(root).as_posix())
    print(f"Portable ZIP: {output.name}, {output.stat().st_size} bytes")
    print("Standalone source ZIP: ClockBridgeStudio_Qt_Source.zip")


if __name__ == "__main__":
    main()
