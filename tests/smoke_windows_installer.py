"""Install, upgrade, run and uninstall in .qa, preserving a user's project."""
import ctypes
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import winreg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tkinterplus import __version__

QA = ROOT / ".qa"
TARGET = (QA / f"installed-{__version__}").resolve()
TARGET.relative_to(QA.resolve())
EXE = TARGET / "TkinterPlusPlus.exe"
SETUP = ROOT / "dist" / f"TkinterPlusPlus-{__version__}-setup-windows-x64.exe"
REGISTRY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\{9273D4AC-62C8-47A6-A37F-5352BD06F83E}_is1"
ACCESS = winreg.KEY_READ | winreg.KEY_WOW64_64KEY

# Never replace a real installation while running the packaging check.
try:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY, 0, ACCESS) as key:
        existing = Path(winreg.QueryValueEx(key, "InstallLocation")[0]).resolve()
        existing.relative_to(QA.resolve())
except FileNotFoundError:
    pass

environment = dict(os.environ)
environment["TEMP"] = environment["TMP"] = str(QA / "temp")
environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
for key in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "TCL_LIBRARY", "TK_LIBRARY"):
    environment.pop(key, None)

def install(label):
    subprocess.run([str(SETUP), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/SP-", "/NORESTART", "/LANG=russian",
                    "/NOICONS", "/TASKS=", f"/DIR={TARGET}", f"/LOG={QA / (label+'.log')}"],
                   check=True, timeout=60, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
    assert EXE.is_file() and (TARGET / "LICENSE").is_file()
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY, 0, ACCESS) as key:
        assert winreg.QueryValueEx(key, "DisplayVersion")[0] == __version__
        assert Path(winreg.QueryValueEx(key, "InstallLocation")[0]).resolve() == TARGET
    print(label, "OK", flush=True)

install("installer-first-install")
project = TARGET / "my-project.tpp"
project.write_text('USER PROJECT: preserve on upgrade and uninstall', encoding="utf-8")
install("installer-upgrade")
assert project.read_text(encoding="utf-8") == 'USER PROJECT: preserve on upgrade and uninstall'

user = ctypes.WinDLL("user32")
kernel = ctypes.WinDLL("kernel32")
CALLBACK = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
user.EnumWindows.argtypes = [CALLBACK, w.LPARAM]
user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
user.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user.IsWindowVisible.argtypes = [w.HWND]
user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
kernel.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
kernel.OpenProcess.restype = w.HANDLE
kernel.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
kernel.CloseHandle.argtypes = [w.HANDLE]

process = subprocess.Popen([str(EXE)], cwd=TARGET, env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
owned = []
@CALLBACK
def inspect(hwnd, _):
    if not user.IsWindowVisible(hwnd):
        return True
    window_class = ctypes.create_unicode_buffer(256)
    user.GetClassNameW(hwnd, window_class, len(window_class))
    if not window_class.value.startswith("Qt"):
        return True
    pid = w.DWORD()
    user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = kernel.OpenProcess(0x1000, False, pid.value)
    if handle:
        name, length = ctypes.create_unicode_buffer(32768), w.DWORD(32768)
        if kernel.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(length)) and Path(name.value) == EXE:
            owned.append(hwnd)
        kernel.CloseHandle(handle)
    return True

try:
    deadline = time.monotonic()+30
    while not owned and time.monotonic() < deadline:
        user.EnumWindows(inspect, 0)
        if process.poll() is not None:
            raise RuntimeError("Installed editor exited before opening a window")
        time.sleep(.1)
    assert owned, "Installed editor did not open a window"
    for hwnd in owned:
        user.PostMessageW(hwnd, 0x0010, 0, 0)
    assert process.wait(timeout=20) == 0
    print("installed editor without Python on PATH: OK", flush=True)
finally:
    if process.poll() is None:
        process.kill()

subprocess.run([str(TARGET / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                f"/LOG={QA / 'installer-uninstall.log'}"], check=True, timeout=60,
               env=environment, creationflags=subprocess.CREATE_NO_WINDOW)
assert not EXE.exists()
assert project.read_text(encoding="utf-8") == 'USER PROJECT: preserve on upgrade and uninstall'
try:
    winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY, 0, ACCESS).Close()
except FileNotFoundError:
    pass
else:
    raise AssertionError("Uninstaller left its registry entry behind")
(QA / "installer-report.json").write_text(json.dumps({
    "version": __version__, "install": True, "upgrade": True, "standalone_launch": True,
    "uninstall": True, "user_project_preserved": True,
}, indent=2), encoding="utf-8")
print("uninstall and user project preservation: OK", flush=True)
