"""Copy installed distribution notices into the portable runtime directory."""
from importlib import metadata
from pathlib import Path
import shutil
import sys


def collect(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("PySide6-Essentials", "shiboken6", "pyserial", "pyinstaller"):
        distribution = metadata.distribution(name)
        folder = destination / name
        folder.mkdir(exist_ok=True)
        for item in distribution.files or []:
            if (any(token in str(item).lower() for token in ("license", "copying", "notice"))
                    or str(item).endswith(".dist-info/METADATA")):
                source = Path(distribution.locate_file(item))
                if source.is_file():
                    target = folder / str(item).replace("..", "_")
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.exists():
        shutil.copy2(python_license, destination / "Python-LICENSE.txt")


if __name__ == "__main__":
    collect(sys.argv[1])
