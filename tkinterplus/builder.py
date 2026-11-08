"""Visual Tkinter++ editor: drag, inspect, save JSON, export Python."""
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import widgets as ui
from .codegen import generate_python
from .project import MAX_WIDGETS, Project, ProjectError, SPECS, WidgetModel, create_widget, demo_project
from .theme import FONT


PROPERTY_LABELS = {
    "text": "Текст", "value": "Значение", "options": "Варианты (по одному в строке)",
    "font_size": "Размер шрифта", "weight": "Начертание", "muted": "Приглушённый цвет",
    "anchor": "Выравнивание", "variant": "Оформление",
}


class Builder(ui.App):
    def __init__(self):
        super().__init__(title="Tkinter++ · Визуальный редактор", width=1440, height=900)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{min(1440, sw-60)}x{min(900, sh-60)}")
        self.minsize(min(1100, sw-60), min(700, sh-100))
        self.project = Project()
        self.path = None
        self.selected_id = None
        self.history = []
        self.future = []
        self.saved = self.project.dumps()
        self.views = {}
        self.selection_parts = []
        self.previews = []
        self._drag = None
        self._palette_drag = None
        self._refreshing_layers = False
        self.snap = tk.BooleanVar(self, True)
        self.status = tk.StringVar(self, "Начните с виджета слева или откройте пример.")
        self._build_chrome()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._refresh()

    @property
    def selected(self):
        return next((item for item in self.project.widgets if item.id == self.selected_id), None)

    @property
    def dirty(self):
        return self.project.dumps() != self.saved

    def _build_chrome(self):
        top = ui.Frame(self)
        top.pack(fill="x")
        brand = ui.Frame(top)
        brand.pack(side="left", padx=22, pady=16)
        logo = tk.Canvas(brand, width=38, height=38, highlightthickness=0,
                         background=self.colors.surface)
        logo.pack(side="left", padx=(0, 12))
        logo.create_rectangle(2, 2, 36, 36, fill=self.colors.accent, outline="")
        logo.create_text(19, 19, text="++", fill="white", font=(FONT, 16, "bold"))
        self.logo = logo
        ui.Label(brand, "Tkinter++", font_size=19, weight="bold").pack(side="left")
        ui.Label(brand, "ВИЗУАЛЬНЫЙ РЕДАКТОР", font_size=9, muted=True).pack(side="left", padx=20)
        self.theme_button = self._button(top, "Светлая тема", self.toggle_theme, 140, "secondary")
        self.theme_button.pack(side="right", padx=(8, 22), pady=16)
        self._button(top, "▶  Предпросмотр", self.preview, 160, "secondary").pack(side="right", padx=4)
        self._button(top, "Экспорт Python", self.export_python, 160).pack(side="right", padx=4)
        toolbar = ui.Frame(self, variant="panel")
        toolbar.pack(fill="x", pady=(1, 0))
        for text, command, width in [
            ("Новый", self.new_project, 78), ("Открыть", self.open_project, 90),
            ("Сохранить", self.save_project, 105), ("Пример", self.open_demo, 85),
        ]:
            self._button(toolbar, text, command, width, "secondary").pack(side="left", padx=(10, 0), pady=8)
        self._button(toolbar, "Код", self.show_code, 65, "secondary").pack(side="right", padx=10)
        self.redo_button = self._button(toolbar, "Повторить", self.redo, 100, "secondary")
        self.redo_button.pack(side="right", padx=4)
        self.undo_button = self._button(toolbar, "Отменить", self.undo, 100, "secondary")
        self.undo_button.pack(side="right", padx=4)
        footer = ui.Frame(self)
        footer.pack(side="bottom", fill="x", pady=(1, 0))
        ui.Label(footer, textvariable=self.status, font_size=9, muted=True).pack(side="left", padx=18, pady=8)
        ui.Label(footer, "Python + Tk  ·  v0.1", font_size=9, muted=True).pack(side="right", padx=18)
        body = ui.Frame(self, variant="background")
        body.pack(fill="both", expand=True)
        left = ui.Frame(body, width=218)
        left.pack(side="left", fill="y", padx=(0, 1))
        left.pack_propagate(False)
        self._build_palette(left)
        self.inspector = ui.Frame(body, width=282)
        self.inspector.pack(side="right", fill="y", padx=(1, 0))
        self.inspector.pack_propagate(False)
        center = ui.Frame(body, variant="background")
        center.pack(fill="both", expand=True)
        heading = ui.Frame(center, variant="background")
        heading.pack(fill="x", padx=22, pady=(16, 10))
        ui.Label(heading, "РАБОЧАЯ ОБЛАСТЬ", font_size=9, weight="bold", muted=True).pack(side="left")
        self.size_label = ui.Label(heading, "", font_size=9, muted=True)
        self.size_label.pack(side="right")
        grid_check = ui.CheckBox(heading, text="Сетка 8 px", variable=self.snap)
        grid_check.pack(side="right", padx=12)
        hint = ui.Label(center, "Перетащите виджет из палитры. Выделите элемент, чтобы изменить его свойства.",
                        font_size=9, muted=True)
        hint.pack(anchor="w", padx=22, pady=(0, 12))
        viewport = ui.Frame(center, variant="background")
        viewport.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.canvas = tk.Canvas(viewport, background=self.colors.background, highlightthickness=0)
        vs = ttk.Scrollbar(viewport, orient="vertical", command=self.canvas.yview,
                           style="TPlus.Vertical.TScrollbar")
        hs = ttk.Scrollbar(viewport, orient="horizontal", command=self.canvas.xview,
                           style="TPlus.Horizontal.TScrollbar")
        self.canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        hs.pack(side="bottom", fill="x")
        self.canvas.pack(fill="both", expand=True)
        self.artboard = ui.Frame(self.canvas, highlightthickness=1,
                                 highlightbackground=self.colors.border)
        self.artboard_window = self.canvas.create_window(24, 24, anchor="nw", window=self.artboard)
        self.artboard.bind("<Button-1>", lambda event: self.select(None))
        self.artboard.bind("<MouseWheel>", self._scroll)
        self.canvas.bind("<MouseWheel>", self._scroll)
        self.canvas.bind("<Button-1>", lambda event: self.select(None))

    def _button(self, parent, text, command, width=120, variant="primary"):
        button = ui.Button(parent, text=text, command=command, variant=variant)
        button.configure(width=width, height=34)
        return button

    def _build_palette(self, parent):
        ui.Label(parent, "ЭЛЕМЕНТЫ", font_size=9, weight="bold", muted=True).pack(anchor="w", padx=18, pady=(18, 3))
        ui.Label(parent, "Нажмите или перетащите", font_size=9, muted=True).pack(anchor="w", padx=18, pady=(0, 12))
        bottom = ui.Frame(parent, height=174)
        bottom.pack(side="bottom", fill="x")
        bottom.pack_propagate(False)
        ui.Separator(bottom).pack(fill="x", padx=18, pady=(8, 12))
        ui.Label(bottom, "СЛОИ", font_size=9, weight="bold", muted=True).pack(anchor="w", padx=18, pady=(0, 8))
        actions = ui.Frame(bottom)
        actions.pack(side="bottom", fill="x", padx=14, pady=(4, 12))
        self._button(actions, "Выше", lambda: self.reorder(1), 86, "secondary").pack(side="left")
        self._button(actions, "Ниже", lambda: self.reorder(-1), 86, "secondary").pack(side="right")
        self.layers = tk.Listbox(bottom, height=4, borderwidth=0, highlightthickness=0,
                                 font=(FONT, 10), activestyle="none", exportselection=False)
        self.layers.pack(fill="both", expand=True, padx=14)
        self.layers.bind("<<ListboxSelect>>", self._layer_select)
        palette_host = ui.Frame(parent)
        palette_host.pack(fill="both", expand=True)
        self.palette_canvas = tk.Canvas(palette_host, background=self.colors.surface, highlightthickness=0)
        palette_scroll = ttk.Scrollbar(palette_host, orient="vertical", command=self.palette_canvas.yview,
                                      style="TPlus.Vertical.TScrollbar")
        palette_scroll.pack(side="right", fill="y")
        self.palette_canvas.pack(fill="both", expand=True)
        self.palette_canvas.configure(yscrollcommand=palette_scroll.set)
        palette = ui.Frame(self.palette_canvas)
        palette_window = self.palette_canvas.create_window(0, 0, anchor="nw", window=palette)
        self.palette_canvas.bind("<Configure>", lambda e: self.palette_canvas.itemconfigure(palette_window, width=e.width))
        palette.bind("<Configure>", lambda e: self.palette_canvas.configure(scrollregion=self.palette_canvas.bbox("all")))
        def wheel(event):
            self.palette_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"
        self.palette_canvas.bind("<MouseWheel>", wheel)
        symbols = ["Aa", "▣", "I_", "≡", "☑", "◉", "⌄", "↔", "━", "□", "—"]
        for (kind, spec), symbol in zip(SPECS.items(), symbols):
            button = self._button(palette, f"{symbol}   {spec.label}", None, 180, "secondary")
            button.configure(height=32)
            button.pack(fill="x", padx=(14, 4), pady=3)
            button.bind("<ButtonPress-1>", lambda event, k=kind: self._palette_start(event, k))
            button.bind("<B1-Motion>", self._palette_motion)
            button.bind("<ButtonRelease-1>", self._palette_drop)
            button.bind("<MouseWheel>", wheel)

    def _bind_shortcuts(self):
        for sequence, callback in {
            "<Control-n>": self.new_project, "<Control-o>": self.open_project,
            "<Control-s>": self.save_project, "<Control-Shift-S>": self.save_as,
            "<Control-e>": self.export_python, "<F5>": self.preview,
        }.items():
            self.bind(sequence, lambda event, fn=callback: (fn(), "break")[1])
        for sequence, callback in {
            "<Control-z>": self.undo, "<Control-y>": self.redo,
            "<Control-Shift-Z>": self.redo, "<Control-d>": self.duplicate,
            "<Delete>": self.delete_selected,
        }.items():
            self.bind(sequence, lambda event, fn=callback: self._editing_shortcut(event, fn))
        for key, dx, dy in [("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)]:
            self.bind(f"<{key}>", lambda event, x=dx, y=dy: self._nudge(event, x, y))
        self.bind("<Escape>", lambda event: self.select(None))

    def _text_focus(self):
        return isinstance(self.focus_get(), (tk.Entry, ttk.Entry, tk.Text, ttk.Combobox))

    def _editing_shortcut(self, event, callback):
        if not self._text_focus():
            callback()
            return "break"

    def _nudge(self, event, dx, dy):
        if self._text_focus() or not self.selected:
            return
        step = 8 if self.snap.get() else 1
        item = self.selected
        before = self.project.to_dict()
        item.x = max(0, min(item.x + dx*step, self.project.width-item.width))
        item.y = max(0, min(item.y + dy*step, self.project.height-item.height))
        self._commit(before)
        return "break"

    def _scroll(self, event):
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _palette_start(self, event, kind):
        self._palette_drag = (kind, event.x_root, event.y_root, False)
        self.status.set(f"{SPECS[kind].label}: отпустите на рабочей области или нажмите для добавления.")
        return "break"

    def _palette_motion(self, event):
        if self._palette_drag:
            kind, x, y, moved = self._palette_drag
            self._palette_drag = (kind, x, y, moved or abs(event.x_root-x)+abs(event.y_root-y) > 8)
        return "break"

    def _palette_drop(self, event):
        if not self._palette_drag:
            return "break"
        kind, _, _, moved = self._palette_drag
        self._palette_drag = None
        x = event.x_root - self.artboard.winfo_rootx()
        y = event.y_root - self.artboard.winfo_rooty()
        if not moved:
            offset = 32 + (len(self.project.widgets) % 10)*16
            self.add_widget(kind, offset, offset)
        elif 0 <= x < self.project.width and 0 <= y < self.project.height:
            self.add_widget(kind, self._snap(x), self._snap(y))
        else:
            self.status.set("Добавление отменено: отпустите виджет внутри окна приложения.")
        return "break"

    def _snap(self, value):
        return round(value/8)*8 if self.snap.get() else round(value)

    def add_widget(self, kind, x=32, y=32):
        before = self.project.to_dict()
        try:
            item = self.project.add(kind, x, y)
        except ProjectError as error:
            self._error(error)
            return
        self.selected_id = item.id
        self._commit(before)
        self.status.set(f"Добавлен {SPECS[kind].label.lower()} · {item.id}")

    def _refresh(self):
        self._render_artboard()
        self._refresh_layers()
        self._render_inspector()
        self._update_title()

    def _update_title(self):
        name = self.path.name if self.path else "Без названия"
        self.title(f"{'● ' if self.dirty else ''}{name} — Tkinter++")
        self.size_label.configure(text=f"{self.project.width} × {self.project.height} px  ·  100%")

    def _render_artboard(self):
        for child in self.artboard.winfo_children():
            child.destroy()
        self.views.clear()
        self.selection_parts.clear()
        self.artboard.configure(width=self.project.width, height=self.project.height,
                                background=self.colors.surface, highlightbackground=self.colors.border)
        self.canvas.itemconfigure(self.artboard_window, width=self.project.width, height=self.project.height)
        self.canvas.configure(scrollregion=(0, 0, self.project.width+48, self.project.height+48))
        for item in self.project.widgets:
            widget = create_widget(self.artboard, item)
            self.views[item.id] = widget
            self._bind_design_widget(widget, item.id)
        if not self.project.widgets:
            empty = ui.Label(self.artboard, "Ваш интерфейс начинается здесь", font_size=20, weight="bold", anchor="center")
            empty.place(relx=.5, rely=.42, anchor="center", relwidth=.9, height=42)
            hint = ui.Label(self.artboard, "Добавьте элемент слева или нажмите «Пример»", font_size=11, muted=True, anchor="center")
            hint.place(relx=.5, rely=.51, anchor="center", relwidth=.9, height=32)
            for label in (empty, hint):
                label.bind("<Button-1>", lambda event: self.select(None))
        self._draw_selection()

    def _bind_design_widget(self, widget, item_id):
        widget.bind("<ButtonPress-1>", lambda event, name=item_id: self._drag_start(event, name))
        widget.bind("<B1-Motion>", self._drag_motion)
        widget.bind("<ButtonRelease-1>", self._drag_end)
        widget.bind("<Button-3>", lambda event, name=item_id: self._context_menu(event, name))
        widget.bind("<Double-Button-1>", lambda event: "break")
        widget.configure(takefocus=False)
        for child in widget.winfo_children():
            self._bind_design_widget(child, item_id)

    def select(self, item_id):
        self.selected_id = item_id
        self._draw_selection()
        self._refresh_layers()
        self._render_inspector()

    def _draw_selection(self):
        for part in self.selection_parts:
            part.destroy()
        self.selection_parts.clear()
        item = self.selected
        if item is None:
            return
        x, y, w, h = item.x, item.y, item.width, item.height
        for px, py, pw, ph in [(x, y, w, 2), (x, y+h-2, w, 2), (x, y, 2, h), (x+w-2, y, 2, h)]:
            edge = tk.Frame(self.artboard, background=self.colors.accent, borderwidth=0)
            edge.place(x=px, y=py, width=pw, height=ph)
            self._bind_design_widget(edge, item.id)
            self.selection_parts.append(edge)
        handle = tk.Frame(self.artboard, background=self.colors.accent, cursor="sizing")
        handle.place(x=x+w-9, y=y+h-9, width=9, height=9)
        handle.bind("<ButtonPress-1>", lambda event: self._drag_start(event, item.id, resize=True))
        handle.bind("<B1-Motion>", self._drag_motion)
        handle.bind("<ButtonRelease-1>", self._drag_end)
        self.selection_parts.append(handle)

    def _drag_start(self, event, item_id, resize=False):
        # Keep the event's widget alive while it owns the pointer grab.
        if self.selected_id != item_id:
            self.selected_id = item_id
            self._draw_selection()
            self._refresh_layers()
            self._render_inspector()
        item = self.selected
        self.focus_set()
        self._drag = {"x": event.x_root, "y": event.y_root, "before": self.project.to_dict(),
                      "item": item.to_dict(), "resize": resize}
        return "break"

    def _drag_motion(self, event):
        if not self._drag or not self.selected:
            return "break"
        drag, item = self._drag, self.selected
        dx, dy = event.x_root-drag["x"], event.y_root-drag["y"]
        original = drag["item"]
        if drag["resize"]:
            item.width = max(16, min(self._snap(original["width"]+dx), self.project.width-item.x))
            item.height = max(2, min(self._snap(original["height"]+dy), self.project.height-item.y))
        else:
            item.x = max(0, min(self._snap(original["x"]+dx), self.project.width-item.width))
            item.y = max(0, min(self._snap(original["y"]+dy), self.project.height-item.height))
        self.views[item.id].place_configure(x=item.x, y=item.y, width=item.width, height=item.height)
        # Reposition existing handles; destroying a grabbed handle cancels dragging on Windows.
        x, y, w, h = item.x, item.y, item.width, item.height
        positions = [(x, y, w, 2), (x, y+h-2, w, 2), (x, y, 2, h),
                     (x+w-2, y, 2, h), (x+w-9, y+h-9, 9, 9)]
        if not self.selection_parts:
            self._draw_selection()
        for part, (px, py, pw, ph) in zip(self.selection_parts, positions):
            part.place_configure(x=px, y=py, width=pw, height=ph)
        self.status.set(f"{item.id} · X {x}  Y {y}  ·  {w} × {h} px")
        return "break"

    def _drag_end(self, event):
        if self._drag:
            before = self._drag["before"]
            self._drag = None
            self._commit(before)
        return "break"

    def _refresh_layers(self):
        self._refreshing_layers = True
        self.layers.delete(0, "end")
        for index, item in enumerate(reversed(self.project.widgets)):
            self.layers.insert("end", f"  {item.id}  ·  {SPECS[item.kind].label}")
            if item.id == self.selected_id:
                self.layers.selection_set(index)
                self.layers.see(index)
        self._refreshing_layers = False

    def _layer_select(self, event):
        if not self._refreshing_layers and self.layers.curselection():
            index = self.layers.curselection()[0]
            name = list(reversed(self.project.widgets))[index].id
            if name != self.selected_id:
                self.select(name)

    def _render_inspector(self):
        for child in self.inspector.winfo_children():
            child.destroy()
        ui.Label(self.inspector, "СВОЙСТВА", font_size=9, weight="bold", muted=True).pack(anchor="w", padx=18, pady=(18, 10))
        scroll_host = ui.Frame(self.inspector)
        scroll_host.pack(fill="both", expand=True)
        canvas = tk.Canvas(scroll_host, background=self.colors.surface, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_host, orient="vertical", command=canvas.yview,
                                  style="TPlus.Vertical.TScrollbar")
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        form = ui.Frame(canvas)
        window_id = canvas.create_window(0, 0, anchor="nw", window=form)
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window_id, width=event.width))
        form.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        def wheel(event):
            canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"
        self.fields = {}
        item = self.selected
        ui.Label(form, SPECS[item.kind].label if item else "Окно приложения", font_size=16, weight="bold").pack(anchor="w", padx=18, pady=(0, 4))
        ui.Label(form, item.id if item else "Выберите виджет для настройки", font_size=9, muted=True).pack(anchor="w", padx=18, pady=(0, 14))
        if item:
            self._field(form, "id", "Имя в проекте", item.id)
            for name, label in [("x", "X, px"), ("y", "Y, px"), ("width", "Ширина, px"), ("height", "Высота, px")]:
                self._field(form, name, label, getattr(item, name))
            for name, value in item.props.items():
                options = None
                if name == "weight":
                    options = ("normal", "bold")
                elif name == "anchor":
                    options = ("w", "center", "e")
                elif name == "variant":
                    options = ("primary", "secondary", "danger") if item.kind == "Button" else ("surface", "panel", "background")
                self._field(form, "prop:"+name, PROPERTY_LABELS[name], value, options=options,
                            multiline=name in ("text", "options") or (name == "value" and item.kind == "Textbox"))
            self._button(form, "Применить", self.apply_properties, 220).pack(fill="x", padx=18, pady=(14, 8))
            self._button(form, "Дублировать · Ctrl+D", self.duplicate, 220, "secondary").pack(fill="x", padx=18, pady=4)
            self._button(form, "Удалить · Delete", self.delete_selected, 220, "danger").pack(fill="x", padx=18, pady=(4, 18))
        else:
            self._field(form, "title", "Заголовок окна", self.project.title)
            self._field(form, "width", "Ширина окна, px", self.project.width)
            self._field(form, "height", "Высота окна, px", self.project.height)
            self._field(form, "theme", "Тема", self.project.theme, options=("dark", "light"))
            self._button(form, "Применить", self.apply_properties, 220).pack(fill="x", padx=18, pady=16)
            ui.Label(form, "Размер: 240–4096 × 200–4096 px.\n\nF5 — интерактивный просмотр\nCtrl+S — сохранить JSON\nCtrl+E — экспорт Python\n\nСтрелки — перемещение\nНижний правый угол — размер", font_size=9,
                     muted=True, justify="left", wraplength=222).pack(anchor="w", padx=18, pady=10)
        def bind_wheel(parent):
            parent.bind("<MouseWheel>", wheel)
            for child in parent.winfo_children():
                bind_wheel(child)
        bind_wheel(form)

    def _field(self, parent, key, label, value, options=None, multiline=False):
        ui.Label(parent, label, font_size=9, muted=True).pack(anchor="w", padx=18, pady=(7, 4))
        if type(value) is bool:
            variable = tk.BooleanVar(self, value=value)
            field = ui.CheckBox(parent, text="Включено", variable=variable)
            getter = variable.get
        elif options:
            field = ui.ComboBox(parent, options=options, value=value)
            getter = field.get
        elif multiline:
            field = ui.Textbox(parent, value="\n".join(value) if isinstance(value, list) else str(value), height=3)
            getter = field.get_value
        else:
            field = ui.Entry(parent, value=str(value))
            getter = field.get
        field.pack(fill="x", padx=18, pady=(0, 2))
        if not multiline:
            field.bind("<Return>", lambda event: self.apply_properties())
        self.fields[key] = getter

    def apply_properties(self):
        before = self.project.to_dict()
        try:
            if self.selected:
                candidate = self.selected.to_dict()
                for key, getter in self.fields.items():
                    value = getter()
                    if key.startswith("prop:"):
                        name = key[5:]
                        original = candidate["props"][name]
                        if type(original) is bool:
                            value = bool(value)
                        elif name == "options":
                            value = value.splitlines()
                        elif name == "font_size":
                            value = int(value)
                        elif type(original) in (float, int):
                            value = float(value)
                        candidate["props"][name] = value
                    else:
                        candidate[key] = value.strip() if key == "id" else int(value)
                node = WidgetModel.from_dict(candidate)
                data = self.project.to_dict()
                index = next(i for i, w in enumerate(self.project.widgets) if w.id == self.selected_id)
                data["widgets"][index] = node.to_dict()
                updated = Project.from_dict(data)
                self.project = updated
                self.selected_id = node.id
            else:
                data = self.project.to_dict()
                data["window"].update(title=self.fields["title"](), width=int(self.fields["width"]()),
                                      height=int(self.fields["height"]()), theme=self.fields["theme"]())
                self.project = Project.from_dict(data)
                self.set_theme(self.project.theme)
                self._style_chrome()
        except (ValueError, OverflowError) as error:
            self._error(error if isinstance(error, ProjectError) else "Проверьте числовые значения свойств.")
            return
        self._commit(before)
        self.status.set("Свойства применены.")

    def _commit(self, before):
        if before != self.project.to_dict():
            self.history.append(before)
            self.history = self.history[-100:]
            self.future.clear()
        self._refresh()

    def undo(self):
        if not self.history:
            self.status.set("Нет действий для отмены.")
            return
        self.future.append(self.project.to_dict())
        self.project = Project.from_dict(self.history.pop())
        self.selected_id = None
        self._sync_theme()
        self._refresh()
        self.status.set("Действие отменено.")

    def redo(self):
        if not self.future:
            return
        self.history.append(self.project.to_dict())
        self.project = Project.from_dict(self.future.pop())
        self.selected_id = None
        self._sync_theme()
        self._refresh()
        self.status.set("Действие повторено.")

    def duplicate(self):
        item = self.selected
        if not item:
            return
        if len(self.project.widgets) >= MAX_WIDGETS:
            self._error(f"Предел — {MAX_WIDGETS} виджетов.")
            return
        before = self.project.to_dict()
        clone = deepcopy(item)
        clone.id = self.project.next_id(item.kind)
        clone.x = min(item.x+16, self.project.width-item.width)
        clone.y = min(item.y+16, self.project.height-item.height)
        self.project.widgets.append(clone)
        self.selected_id = clone.id
        self._commit(before)

    def delete_selected(self):
        if not self.selected:
            return
        before = self.project.to_dict()
        self.project.widgets.remove(self.selected)
        self.selected_id = None
        self._commit(before)

    def reorder(self, direction):
        item = self.selected
        if not item:
            return
        index = self.project.widgets.index(item)
        new_index = max(0, min(index+direction, len(self.project.widgets)-1))
        before = self.project.to_dict()
        self.project.widgets.insert(new_index, self.project.widgets.pop(index))
        self._commit(before)

    def _context_menu(self, event, item_id):
        self.select(item_id)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Дублировать", command=self.duplicate)
        menu.add_command(label="На слой выше", command=lambda: self.reorder(1))
        menu.add_command(label="На слой ниже", command=lambda: self.reorder(-1))
        menu.add_separator()
        menu.add_command(label="Удалить", command=self.delete_selected)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
            menu.destroy()
        return "break"

    def _confirm_discard(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("Несохранённые изменения", "Сохранить текущий проект?", parent=self)
        if answer is None:
            return False
        return self.save_project() if answer else True

    def _replace_project(self, project, path=None, saved=True):
        self.project = project
        self.path = Path(path) if path else None
        self.selected_id = None
        self.history.clear()
        self.future.clear()
        self.saved = project.dumps() if saved else ""
        self._sync_theme()
        self._refresh()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def new_project(self):
        if self._confirm_discard():
            self._replace_project(Project(theme=self.theme))
            self.status.set("Новый проект.")

    def open_demo(self):
        if self._confirm_discard():
            self._replace_project(demo_project(), saved=False)
            self.status.set("Демонстрационный проект: перемещайте элементы и меняйте свойства.")

    def open_project(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self, title="Открыть проект Tkinter++", filetypes=[("Проект JSON", "*.json")])
        if not path:
            return
        try:
            project = Project.load(path)
        except (OSError, ProjectError) as error:
            self._error(error)
            return
        self._replace_project(project, path)
        self.status.set(f"Открыт {Path(path).name}")

    def save_project(self):
        if self.path is None:
            return self.save_as()
        return self._save_to(self.path)

    def save_as(self):
        path = filedialog.asksaveasfilename(parent=self, title="Сохранить проект", defaultextension=".json",
                                          initialfile=self.path.name if self.path else "project.json",
                                          filetypes=[("Проект JSON", "*.json")])
        return self._save_to(Path(path)) if path else False

    def _save_to(self, path):
        try:
            self.project.save(path)
        except (OSError, ProjectError) as error:
            self._error(error)
            return False
        self.path = path
        self.saved = self.project.dumps()
        self._update_title()
        self.status.set(f"Сохранено: {path.name}")
        return True

    def export_python(self):
        path = filedialog.asksaveasfilename(parent=self, title="Экспорт Python", defaultextension=".py",
                                          initialfile="app.py", filetypes=[("Python", "*.py")])
        if not path:
            return
        try:
            source = generate_python(self.project)
            Path(path).write_text(source, encoding="utf-8")
        except (OSError, ProjectError) as error:
            self._error(error)
            return
        self.status.set(f"Экспортирован {Path(path).name} · запуск: python {Path(path).name}")

    def show_code(self):
        window = tk.Toplevel(self)
        window.title("Python-код · Tkinter++")
        window.geometry("850x640")
        window.configure(background=self.colors.surface)
        bar = ui.Frame(window)
        bar.pack(fill="x")
        ui.Label(bar, "Код текущего проекта", font_size=13, weight="bold").pack(side="left", padx=18, pady=12)
        code = generate_python(self.project)
        self._button(bar, "Копировать", lambda: self._copy_code(code), 120, "secondary").pack(side="right", padx=12)
        text = ui.Textbox(window, value=code, font=("Consolas", 11))
        text.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        text.configure(state="disabled")

    def _copy_code(self, code):
        self.clipboard_clear()
        self.clipboard_append(code)
        self.status.set("Python-код скопирован.")

    def preview(self):
        # A separate root has an independent theme and cannot change the editor.
        preview = ui.App(title=f"Предпросмотр · {self.project.title}", width=self.project.width,
                         height=self.project.height, theme=self.project.theme)
        preview.resizable(False, False)
        preview.configure(background=preview.colors.surface)
        for item in self.project.widgets:
            create_widget(preview, item)
        preview.update_idletasks()
        self.previews.append(preview)
        self.status.set("Предпросмотр открыт. Поля и переключатели доступны для проверки.")
        return preview

    def toggle_theme(self):
        before = self.project.to_dict()
        self.project.theme = "light" if self.project.theme == "dark" else "dark"
        self._sync_theme()
        self._commit(before)

    def _sync_theme(self):
        self.set_theme(self.project.theme)
        self._style_chrome()

    def _style_chrome(self):
        p = self.colors
        self.canvas.configure(background=p.background)
        self.palette_canvas.configure(background=p.surface)
        self.layers.configure(background=p.surface, foreground=p.text,
                              selectbackground=p.selection, selectforeground=p.text)
        self.logo.configure(background=p.surface)
        self.theme_button.text = "Светлая тема" if self.theme == "dark" else "Тёмная тема"
        self.theme_button._draw()

    def _error(self, error):
        messagebox.showerror("Tkinter++", str(error), parent=self)

    def close(self):
        if self._confirm_discard():
            for preview in self.previews:
                try:
                    preview.destroy()
                except tk.TclError:
                    pass
            self.destroy()


def main():
    app = Builder()
    app._style_chrome()
    app.mainloop()


if __name__ == "__main__":
    main()
