"""Windows design surface hosting the same Tk widgets as exported applications."""
import ctypes
from ctypes import wintypes
import sys
import tkinter as tk

from PyQt6.QtCore import QEvent, QMimeData, QPoint, QPointF, QRectF, QTimer, Qt
from PyQt6.QtGui import QDrag
from PyQt6.QtWidgets import QListWidget, QScrollArea, QWidget

from .project import SPECS, create_widget
from .widgets import App

MIME_WIDGET = "application/x-tkinterplus-widget"


class PaletteList(QListWidget):
    def startDrag(self, supported_actions):
        item = self.currentItem()
        if item is None:
            return
        mime = QMimeData()
        mime.setData(MIME_WIDGET, item.data(Qt.ItemDataRole.UserRole).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)


class WidgetHandle:
    """Adapter between the editor selection model and a real Tk widget."""
    def __init__(self, view, model, widget):
        self.view, self.model, self.widget = view, model, widget

    def setPos(self, x, y):
        self.widget.place(x=x, y=y)

    def update(self):
        self.widget.place(width=self.model.width, height=self.model.height)
        self.view.refresh_selection()

    def isSelected(self):
        return self.model.id in self.view.editor.selected_ids


class DesignView(QScrollArea):
    def __init__(self, editor):
        super().__init__()
        if sys.platform != "win32":
            raise RuntimeError("Встроенный конструктор этой версии поддерживает Windows.")
        self.editor = editor
        self.zoom = 1.0
        self.testing = False
        self.root = None
        self.handles = {}
        self._targets = {}
        self._outlines = []
        self._gesture = None
        self._pumping = False
        self._closed = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setAcceptDrops(True)
        self.host = QWidget()
        self.host.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
        self.host.setAcceptDrops(True)
        self.host.installEventFilter(self)
        self.setWidget(self.host)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.pump)
        self.timer.start(10)
        self.api = ctypes.windll.user32
        self.api.SetParent.argtypes = [wintypes.HWND, wintypes.HWND]
        self.api.SetParent.restype = wintypes.HWND
        self.api.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.api.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.api.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        self.api.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        self.api.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                         ctypes.c_int, ctypes.c_int, wintypes.UINT]
        self.api.GetParent.argtypes = [wintypes.HWND]
        self.api.GetParent.restype = wintypes.HWND

    @property
    def density(self):
        return self.devicePixelRatioF()*self.zoom

    def _make_root(self, project):
        self.root = App(width=project.width, height=project.height, theme=project.theme,
                        colors=project.colors, scale=self.density)
        self.root.overrideredirect(True)
        self.root.geometry(f"{project.width}x{project.height}+10000+10000")
        self.root.update()
        self.native_handle = int(self.root.frame(), 16)
        self.api.SetParent(self.native_handle, int(self.host.winId()))
        style = self.api.GetWindowLongPtrW(self.native_handle, -16)
        self.api.SetWindowLongPtrW(self.native_handle, -16, (style | 0x40000000) & ~0x80000000)
        for sequence, callback in [("<ButtonPress-1>", self._press), ("<B1-Motion>", self._motion),
                                   ("<ButtonRelease-1>", self._release), ("<KeyPress>", self._key),
                                   ("<ButtonPress-3>", self._context_menu),
                                   ("<MouseWheel>", self._wheel), ("<Enter>", self._hover),
                                   ("<Leave>", self._hover), ("<Motion>", self._hover)]:
            self.root.bind_class("TPDesigner", sequence, callback)

    def render(self, project):
        if self._closed:
            return
        if self.root is None:
            self._make_root(project)
        self._gesture = None
        for child in self.root.winfo_children():
            child.destroy()
        self._outlines = []
        self.handles.clear()
        self._targets.clear()
        self.root._radio_groups = {}
        self.root._density = self.density
        self.root.tk.call("tk", "scaling", (4/3)*self.density)
        self.root._theme.overrides = dict(project.colors)
        self.root.set_theme(project.theme)
        self.host.setFixedSize(round(project.width*self.zoom), round(project.height*self.zoom))
        self.root.geometry(f"{project.width}x{project.height}")
        self.api.SetWindowPos(self.native_handle, None, 0, 0,
                              self.root.px(project.width), self.root.px(project.height), 0x0040 | 0x0020 | 0x0010)
        self.background = tk.Canvas(self.root, highlightthickness=0, borderwidth=0,
                                    background=self.root.colors.background)
        self.background.place(x=0, y=0, relwidth=1, relheight=1)
        self._bind_widget(self.background, None)
        for model in project.widgets:
            widget = create_widget(self.root, model)
            self.handles[model.id] = WidgetHandle(self, model, widget)
            self._bind_widget(widget, model.id)
        self.draw_grid()
        self.refresh_selection()
        self.pump()

    def _show_native(self):
        if self.root is not None and not self._closed and self.isVisible():
            self.api.SetWindowPos(self.native_handle, None, 0, 0,
                                  self.root.px(self.editor.project.width), self.root.px(self.editor.project.height),
                                  0x0040 | 0x0020 | 0x0010)
            self.pump()

    def showEvent(self, event):
        super().showEvent(event)
        # Qt maps its host after this event. Restore Tk's foreign child afterwards,
        # including when returning from the Code tab.
        QTimer.singleShot(0, self._show_native)

    def event(self, event):
        result = super().event(event)
        if event.type() == QEvent.Type.DevicePixelRatioChange and getattr(self, "root", None) is not None:
            QTimer.singleShot(0, lambda: self.render(self.editor.project))
        return result

    def _bind_widget(self, widget, name):
        self._targets[str(widget)] = name
        widget.bindtags(("TPDesigner",) + tuple(tag for tag in widget.bindtags() if tag != "TPDesigner"))
        for child in widget.winfo_children():
            self._bind_widget(child, name)

    def pump(self):
        if self._closed or self._pumping or self.root is None:
            return
        self._pumping = True
        try:
            self.root.update()
        finally:
            self._pumping = False

    def set_testing(self, enabled):
        self.testing = bool(enabled)
        self.render(self.editor.project)
        self.editor.views = self.handles
        self.editor.tabs.setTabText(0, "Проверка" if enabled else "Конструктор")
        self.editor.statusBar().showMessage("Проверка: элементы работают. F6 — вернуться в конструктор."
                                            if enabled else "Конструктор: выделение, перемещение и размер элементов")

    def draw_grid(self):
        if self.root is None:
            return
        canvas, p = self.background, self.root.colors
        canvas.delete("grid")
        if self.editor.snap_action.isChecked() and not self.testing:
            step = max(1, self.root.px(8))
            grid = "#"+"".join(f"{round(int(p.border[i:i+2], 16)*0.35+int(p.background[i:i+2], 16)*0.65):02x}"
                               for i in (1, 3, 5))
            for y in range(step, self.root.px(self.editor.project.height), step):
                canvas.create_line(step, y, self.root.px(self.editor.project.width)-1, y,
                                   dash=(1, max(1, step-1)), fill=grid, tags="grid")

    def refresh_selection(self):
        if self.root is None:
            return
        # Reuse outlines while dragging so Tk retains its pressed window and mouse grab.
        needed = [] if self.testing else list(self.editor.selected_items)
        while len(self._outlines) < len(needed)*5:
            frame = tk.Frame(self.root, borderwidth=0)
            self._outlines.append(frame)
        for index, frame in enumerate(self._outlines):
            if index >= len(needed)*5:
                frame.place_forget()
                continue
            model = needed[index//5]
            x, y, w, h = model.x, model.y, model.width, model.height
            rx, ry, rw, rh, resize = [(x, y, w, 1, False), (x, y+h-1, w, 1, False),
                                     (x, y, 1, h, False), (x+w-1, y, 1, h, False),
                                     (x+w-7, y+h-7, 7, 7, True)][index % 5]
            frame.configure(bg=self.editor.editor_colors.get("accent", "#007acc"),
                            cursor="size_nw_se" if resize else "fleur")
            frame.place(x=self.root.px(rx), y=self.root.px(ry),
                        width=max(1, self.root.px(rw)), height=max(1, self.root.px(rh)))
            frame.lift()
            frame._resize_handle = resize
            self._bind_widget(frame, model.id)

    def _point(self, event):
        return ((event.x + event.widget.winfo_rootx()-self.root.winfo_rootx())/self.density,
                (event.y + event.widget.winfo_rooty()-self.root.winfo_rooty())/self.density)

    def _press(self, event):
        if self.testing:
            return
        x, y = self._point(event)
        name = self._targets.get(str(event.widget))
        additive = bool(event.state & 0x0004)
        resize = getattr(event.widget, "_resize_handle", False)
        if name is None:
            if not additive:
                self.editor.select(None)
        elif additive:
            self.editor.select(name, additive=True, toggle=True)
        elif name not in self.editor.selected_ids:
            self.editor.select(name)
        event.widget.focus_set()
        self._gesture = {"start": (x, y), "before": self.editor.project.to_dict(), "name": name,
                         "resize": resize, "base_selection": set(self.editor.selected_ids),
                         "originals": {item.id: item.to_dict() for item in self.editor.selected_items}}
        return "break"

    def _motion(self, event):
        if self.testing:
            return
        if not self._gesture:
            return "break"
        g = self._gesture
        x, y = self._point(event)
        sx, sy = g["start"]
        if g["name"] is None:
            area = QRectF(QPointF(sx, sy), QPointF(x, y)).normalized()
            selected = {item.id for item in self.editor.project.widgets
                        if area.intersects(QRectF(item.x, item.y, item.width, item.height))}
            self.editor.set_selection(g["base_selection"] | selected)
            self.background.delete("rubber")
            self.background.create_rectangle(self.root.px(sx), self.root.px(sy), self.root.px(x), self.root.px(y),
                                              outline=self.root.colors.accent, dash=(4, 3), tags="rubber")
        elif g["resize"] and g["name"] in g["originals"]:
            model = next(item for item in self.editor.project.widgets if item.id == g["name"])
            original = g["originals"][model.id]
            model.width = max(16, min(self.editor.project.width-model.x, self.editor.snap(original["width"]+x-sx)))
            model.height = max(2, min(self.editor.project.height-model.y, self.editor.snap(original["height"]+y-sy)))
            self.handles[model.id].update()
            self.editor.update_geometry_fields()
        else:
            self.editor.move_selection(self.editor.snap(x-sx), self.editor.snap(y-sy), g["originals"])
        return "break"

    def _release(self, event):
        if self.testing:
            return
        if self._gesture:
            before = self._gesture["before"]
            self._gesture = None
            self.background.delete("rubber")
            self.editor._commit(before, rebuild_scene=False)
        return "break"

    def _hover(self, event):
        return None if self.testing else "break"

    def _context_menu(self, event):
        if self.testing:
            return
        name = self._targets.get(str(event.widget))
        if name not in self.editor.selected_ids:
            self.editor.select(name)
        x, y = self._point(event)
        position = self.host.mapToGlobal(QPoint(round(x*self.zoom), round(y*self.zoom)))
        self._defer(lambda: self.editor.context_menu(position))
        return "break"

    def _defer(self, callback):
        QTimer.singleShot(0, callback)

    def _key(self, event):
        key = event.keysym
        ctrl = bool(event.state & 0x0004)
        if key in ("F6", "F5"):
            self._defer(self.editor.test_action.trigger if key == "F6" else self.editor.preview)
            return "break"
        if self.testing:
            return
        moves = {"Left": (-1, 0), "Right": (1, 0), "Up": (0, -1), "Down": (0, 1)}
        callbacks = {"Delete": self.editor.delete_selected, "Escape": lambda: self.editor.select(None)}
        if ctrl:
            callbacks.update({"a": self.editor.select_all, "c": self.editor.copy_widgets, "x": self.editor.cut_widgets,
                              "v": self.editor.paste_widgets, "d": self.editor.duplicate, "z": self.editor.undo,
                              "y": self.editor.redo, "s": self.editor.save_project, "o": self.editor.open_project,
                              "n": self.editor.new_project, "e": self.editor.export_python})
            if event.state & 0x0001:
                callbacks.update(z=self.editor.redo, s=self.editor.save_as)
        if key in moves:
            self._defer(lambda: self.editor.nudge(*moves[key]))
        elif key.lower() in callbacks or key in callbacks:
            self._defer(callbacks.get(key, callbacks.get(key.lower())))
        return "break"

    def _wheel(self, event):
        if event.state & 0x0004:
            self._defer(lambda: self.zoom_to(self.zoom*(1.15 if event.delta > 0 else 1/1.15)))
        elif not self.testing:
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-event.delta//3)
        else:
            return
        return "break"

    def zoom_to(self, factor):
        self.zoom = max(0.25, min(3.0, factor))
        self.render(self.editor.project)
        self.editor.views = self.handles
        self.editor.statusBar().showMessage(f"Масштаб: {round(self.zoom*100)}%")

    def fit_artboard(self):
        self.zoom_to(min((self.viewport().width()-16)/self.editor.project.width,
                         (self.viewport().height()-16)/self.editor.project.height))

    def setBackgroundBrush(self, color):
        self.viewport().setStyleSheet(f"background: {color.name()};")

    def update(self, *args):
        super().update(*args)
        self.draw_grid()
        self.refresh_selection()

    def add_drop(self, kind, position):
        if not self.testing and kind in SPECS and QRectF(0, 0, self.editor.project.width, self.editor.project.height).contains(position):
            self.editor.add_widget(kind, self.editor.snap(position.x()), self.editor.snap(position.y()))
            return True
        return False

    def dragEnterEvent(self, event):
        if not self.testing and event.mimeData().hasFormat(MIME_WIDGET):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        self.dragEnterEvent(event)

    def dropEvent(self, event):
        point = self.host.mapFrom(self.viewport(), event.position().toPoint())
        self._drop(event, QPointF(point.x()/self.zoom, point.y()/self.zoom))

    def _drop(self, event, point):
        try:
            kind = bytes(event.mimeData().data(MIME_WIDGET)).decode("utf-8")
        except UnicodeError:
            event.ignore()
            return
        if self.add_drop(kind, point):
            event.acceptProposedAction()
        else:
            event.ignore()

    def eventFilter(self, obj, event):
        if obj is self.host:
            if event.type() in (QEvent.Type.DragEnter, QEvent.Type.DragMove):
                self.dragEnterEvent(event)
                return True
            if event.type() == QEvent.Type.Drop:
                self._drop(event, QPointF(event.position().x()/self.zoom, event.position().y()/self.zoom))
                return True
        return super().eventFilter(obj, event)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_to(self.zoom*(1.15 if event.angleDelta().y() > 0 else 1/1.15))
            event.accept()
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        moves = {Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
                 Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1)}
        if event.key() in moves and not self.testing:
            self.editor.nudge(*moves[event.key()])
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.editor.select(None)
        else:
            super().keyPressEvent(event)

    def shutdown(self):
        self._closed = True
        self.timer.stop()
        if self.root is not None:
            self.root.destroy()
            self.root = None
