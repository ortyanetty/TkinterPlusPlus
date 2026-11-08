"""Black-box smoke checks of the actual bundled executable, with no Python on PATH."""
from pathlib import Path
import ctypes
from ctypes import wintypes as w
import os
import subprocess
import time
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tkinterplus.project import Project, SPECS
EXE = ROOT / "dist" / "TkinterPlusPlus-0.4.0-windows-x64.exe"
RUN = ROOT / ".qa" / "standalone-run"
RUN.mkdir(exist_ok=True, parents=True)
(ROOT / ".qa" / "temp").mkdir(exist_ok=True)
custom = Project(title="HEX / RGB widgets", width=1000, height=800,
                 colors={"accent": (124, 92, 224), "background": "#16181d"})
for index, kind in enumerate(SPECS):
    custom.add(kind, 32, 24+index*48).props["colors"] = {"border": "#64748b", "thumb": (220, 230, 240)}
custom_path = RUN / "custom-colors.json"
custom.save(custom_path)
kernel = ctypes.WinDLL("kernel32", use_last_error=True)
user = ctypes.WinDLL("user32", use_last_error=True)
class PE(ctypes.Structure):
    _fields_ = [("dwSize", w.DWORD), ("cntUsage", w.DWORD), ("th32ProcessID", w.DWORD),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", w.DWORD),
                ("cntThreads", w.DWORD), ("th32ParentProcessID", w.DWORD),
                ("pcPriClassBase", w.LONG), ("dwFlags", w.DWORD), ("szExeFile", w.WCHAR*260)]
kernel.CreateToolhelp32Snapshot.restype = w.HANDLE
kernel.Process32FirstW.argtypes = [w.HANDLE, ctypes.POINTER(PE)]
kernel.Process32NextW.argtypes = [w.HANDLE, ctypes.POINTER(PE)]
kernel.CloseHandle.argtypes = [w.HANDLE]
user.GetWindowThreadProcessId.argtypes = [w.HWND, ctypes.POINTER(w.DWORD)]
user.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user.GetClassNameW.argtypes = [w.HWND, w.LPWSTR, ctypes.c_int]
user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
CALLBACK = ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
user.EnumWindows.argtypes = [CALLBACK, w.LPARAM]
user.EnumChildWindows.argtypes = [w.HWND, CALLBACK, w.LPARAM]
user.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
def dialog_text(hwnd):
    texts = []
    @CALLBACK
    def child(child_hwnd, _):
        buffer = ctypes.create_unicode_buffer(24000)
        user.SendMessageW(child_hwnd, 13, len(buffer), ctypes.cast(buffer, ctypes.c_void_p).value)
        if buffer.value:
            texts.append(buffer.value)
        return True
    user.EnumChildWindows(hwnd, child, 0)
    return "\n".join(texts)

user.IsWindowVisible.argtypes = [w.HWND]

def descendants(root_pid):
    parents = {}
    snap = kernel.CreateToolhelp32Snapshot(2, 0)
    entry = PE()
    entry.dwSize = ctypes.sizeof(entry)
    ok = kernel.Process32FirstW(snap, ctypes.byref(entry))
    while ok:
        parents[entry.th32ProcessID] = entry.th32ParentProcessID
        ok = kernel.Process32NextW(snap, ctypes.byref(entry))
    kernel.CloseHandle(snap)
    found = {root_pid}
    while True:
        updated = found | {pid for pid, parent in parents.items() if parent in found}
        if updated == found:
            return found
        found = updated

def windows(pids):
    found = []
    @CALLBACK
    def callback(hwnd, _):
        pid = w.DWORD()
        user.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user.IsWindowVisible(hwnd):
            title, cls = ctypes.create_unicode_buffer(1000), ctypes.create_unicode_buffer(200)
            user.GetWindowTextW(hwnd, title, len(title))
            user.GetClassNameW(hwnd, cls, len(cls))
            found.append((hwnd, title.value, cls.value))
        return True
    user.EnumWindows(callback, 0)
    return found

environment = dict(os.environ)
environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
environment["TEMP"] = environment["TMP"] = str(ROOT / ".qa" / "temp")
for key in ("PYTHONPATH", "PYTHONHOME", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "TCL_LIBRARY", "TK_LIBRARY"):
    environment.pop(key, None)

reports = []
for name, arguments, expected in [
    ("editor", [], lambda item: "Tkinter++" in item[1] and item[2].startswith("Qt")),
    ("tk_preview", ["--preview", str(ROOT / "examples" / "starter.json")],
     lambda item: item[1] == "Параметры проекта" and item[2].startswith("Tk")),
    ("all_widgets_preview", ["--preview", str(custom_path)],
     lambda item: item[1] == "HEX / RGB widgets" and item[2].startswith("Tk")),
]:
    process = subprocess.Popen([str(EXE), *arguments], cwd=RUN, env=environment,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic()+45
        while time.monotonic() < deadline:
            owned = windows(descendants(process.pid))
            for item in owned:
                if item[2] == "#32770":
                    raise RuntimeError("Bundled executable error: " + dialog_text(item[0]))
            matched = next((item for item in owned if expected(item)), None)
            if matched:
                break
            if process.poll() is not None:
                raise RuntimeError(f"{name}: exited early, code {process.returncode}, windows {owned}")
            time.sleep(.15)
        else:
            raise RuntimeError(f"{name}: window not found, owned windows: {owned}")
        print(name, "window:", matched[1], matched[2], flush=True)
        # Exercise the editor's F5 action too; only the application window receives these events.
        if name == "editor":
            native_children = []
            @CALLBACK
            def native_child(hwnd, _):
                cls = ctypes.create_unicode_buffer(200)
                user.GetClassNameW(hwnd, cls, len(cls))
                if cls.value.startswith("Tk") and user.IsWindowVisible(hwnd):
                    native_children.append(cls.value)
                return True
            for _ in range(30):
                native_children.clear()
                user.EnumChildWindows(matched[0], native_child, 0)
                if len(native_children) >= 2:
                    break
                time.sleep(.1)
            assert len(native_children) >= 2, f"Native Tk canvas missing: {native_children}"
            print("embedded native Tk canvas: OK", flush=True)
            user.PostMessageW(matched[0], 0x0100, 0x74, 0)
            user.PostMessageW(matched[0], 0x0101, 0x74, 0)
            for _ in range(60):
                previews = [item for item in windows(descendants(process.pid))
                            if item[1] == "Form1" and item[2].startswith("Tk")]
                if previews:
                    print("editor -> F5 -> bundled Tk preview: OK", flush=True)
                    break
                time.sleep(.15)
            else:
                raise RuntimeError("F5 did not start a Tk preview")
        user.PostMessageW(matched[0], 0x0010, 0, 0)
        result = process.wait(timeout=20)
        if result != 0:
            raise RuntimeError(f"{name}: exit code {result}")
        reports.append({"mode": name, "window": matched[1], "class": matched[2], "exit_code": result})
        print(name, "clean exit: OK", flush=True)
    finally:
        if process.poll() is None:
            for hwnd, _, _ in windows(descendants(process.pid)):
                user.PostMessageW(hwnd, 0x0010, 0, 0)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
(ROOT / ".qa" / "standalone-report.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
