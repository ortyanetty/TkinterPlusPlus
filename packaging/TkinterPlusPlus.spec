# Build with: .venv/Scripts/python -m PyInstaller packaging/TkinterPlusPlus.spec
from pathlib import Path

root = Path(SPECPATH).parent
a = Analysis(
    [str(root / 'run_builder.py')],
    pathex=[str(root)],
    binaries=[],
    datas=[(str(root / 'LICENSE'), '.'),
           (str(root / 'THIRD_PARTY_NOTICES.md'), '.'),
           (str(root / 'licenses'), 'licenses')],
    hiddenimports=['tkinterplus.preview'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False, optimize=0,
)
# The editor renders with Qt's raster engine; it does not use the optional Mesa
# software OpenGL renderer distributed with Qt.
a.binaries = [entry for entry in a.binaries if Path(entry[0]).name.lower() != 'opengl32sw.dll']
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name='TkinterPlusPlus-0.2.0-windows-x64',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    version=str(root / 'packaging' / 'windows-version.txt'),
)
