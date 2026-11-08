"""Run the PyQt editor, preferring this checkout's prepared environment if needed."""
import importlib.util
from pathlib import Path
import subprocess
import sys


def main():
    if importlib.util.find_spec("PyQt6") is None:
        root = Path(__file__).resolve().parent
        executable = root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        if executable.is_file() and executable.resolve() != Path(sys.executable).resolve():
            return subprocess.call([str(executable), str(Path(__file__).resolve()), *sys.argv[1:]])
    from tkinterplus.launcher import main as run
    return run()

if __name__ == "__main__":
    raise SystemExit(main())
