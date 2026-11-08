"""Console entry point with a clear message for a missing editor dependency."""
import importlib.util
import sys


def main():
    if importlib.util.find_spec("PyQt6") is None:
        print('Для редактора нужен PyQt6. Установите: python -m pip install "PyQt6>=6.7,<7"', file=sys.stderr)
        return 1
    from .builder import main as run
    return run()
