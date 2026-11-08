"""Modern, theme-aware Tk widgets with pixel sizing through place()."""
import tkinter as tk
from tkinter import ttk
from .theme import FONT, Theme, get_theme, parent_color


class App(tk.Tk):
    def __init__(self, title="Tkinter++", width=960, height=640, theme="dark", **kwargs):
        super().__init__(**kwargs)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self._theme = Theme(self, theme)
        self._theme.register(self)

    def _apply_theme(self):
        self.configure(background=self._theme.colors.background)

    @property
    def theme(self):
        return self._theme.name

    @property
    def colors(self):
        return self._theme.colors

    def set_theme(self, name):
        self._theme.set(name)
        # Parent backgrounds must be updated before dependent children.
        def refresh(parent):
            for child in parent.winfo_children():
                if hasattr(child, "_apply_theme"):
                    child._apply_theme()
                refresh(child)
        refresh(self)


class Frame(tk.Frame):
    def __init__(self, master, variant="surface", **kwargs):
        if variant not in ("surface", "panel", "background"):
            raise ValueError("Unknown frame variant")
        self.variant = variant
        super().__init__(master, borderwidth=0, **kwargs)
        get_theme(self).register(self)

    def _apply_theme(self):
        self.configure(background=getattr(get_theme(self).colors, self.variant))


class Label(tk.Label):
    def __init__(self, master, text="Label", font_size=11, weight="normal",
                 muted=False, **kwargs):
        self.muted = muted
        super().__init__(master, text=text, font=(FONT, font_size, weight),
                         borderwidth=0, anchor=kwargs.pop("anchor", "w"), **kwargs)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = get_theme(self).colors
        self.configure(background=parent_color(self), foreground=p.muted if self.muted else p.text)


def _rounded(canvas, x1, y1, x2, y2, radius=9, **kwargs):
    radius = max(0, min(radius, (x2 - x1) / 2, (y2 - y1) / 2))
    r = radius
    return canvas.create_polygon(
        x1+r, y1, x2-r, y1, x2, y1, x2, y1+r, x2, y2-r, x2, y2,
        x2-r, y2, x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1,
        smooth=True, splinesteps=24, **kwargs,
    )


class Button(tk.Canvas):
    def __init__(self, master, text="Button", command=None, variant="primary",
                 state="normal", **kwargs):
        if variant not in ("primary", "secondary", "danger"):
            raise ValueError("Unknown button variant")
        self.text = text
        self.command = command
        self.variant = variant
        self._enabled = state != "disabled"
        self._hover = False
        super().__init__(master, width=kwargs.pop("width", 140), height=kwargs.pop("height", 40), highlightthickness=0,
                         borderwidth=0, takefocus=True, **kwargs)
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonRelease-1>", self._click)
        self.bind("<space>", lambda e: self.invoke())
        self.bind("<Return>", lambda e: self.invoke())
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)
        get_theme(self).register(self)

    def _set_hover(self, hover):
        self._hover = hover
        self._draw()

    def _click(self, event):
        if 0 <= event.x < self.winfo_width() and 0 <= event.y < self.winfo_height():
            self.focus_set()
            self.invoke()

    def invoke(self):
        if self._enabled and self.command is not None:
            return self.command()

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
            cnf = None
        if cnf is not None:
            return super().configure(cnf, **kwargs)
        if "variant" in kwargs:
            variant = kwargs.pop("variant")
            if variant not in ("primary", "secondary", "danger"):
                raise ValueError("Unknown button variant")
            self.variant = variant
        if "state" in kwargs:
            state = kwargs.pop("state")
            if state not in ("normal", "disabled"):
                raise ValueError("Button state must be normal or disabled")
            self._enabled = state == "normal"
            kwargs.setdefault("cursor", "hand2" if self._enabled else "arrow")
        for key in ("text", "command"):
            if key in kwargs:
                setattr(self, key, kwargs.pop(key))
        result = super().configure(**kwargs) if kwargs else None
        if hasattr(self, "_enabled") and self.winfo_exists():
            self._draw()
        return result

    config = configure

    def cget(self, key):
        if key in ("text", "command", "variant"):
            return getattr(self, key)
        if key == "state":
            return "normal" if self._enabled else "disabled"
        return super().cget(key)

    def _apply_theme(self):
        self.configure(background=parent_color(self), cursor="hand2" if self._enabled else "arrow")
        self._draw()

    def _draw(self, event=None):
        p = get_theme(self).colors
        self.delete("all")
        fill = {"primary": p.accent, "secondary": p.panel, "danger": p.danger}[self.variant]
        if self._hover and self._enabled:
            fill = p.hover if self.variant == "primary" else p.border
        if not self._enabled:
            fill = p.panel
        fg = p.text if self.variant == "secondary" else "#ffffff"
        if not self._enabled:
            fg = p.muted
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1:
            w, h = int(self.cget("width")), int(self.cget("height"))
        _rounded(self, 1, 1, w-1, h-1, fill=fill, outline="")
        if self.focus_get() == self:
            _rounded(self, 3, 3, w-3, h-3, fill="", outline=p.text, width=1)
        self.create_text(w/2, h/2, text=self.text, fill=fg,
                         font=(FONT, 10, "bold"), width=max(10, w-18))


class Entry(ttk.Entry):
    def __init__(self, master, value="", **kwargs):
        super().__init__(master, style="TPlus.TEntry", font=(FONT, 10), **kwargs)
        self.insert(0, value)


class Textbox(tk.Text):
    def __init__(self, master, value="", **kwargs):
        super().__init__(master, font=kwargs.pop("font", (FONT, 10)), wrap="word", relief="flat",
                         padx=10, pady=8, highlightthickness=1, undo=True, **kwargs)
        self.insert("1.0", value)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = get_theme(self).colors
        self.configure(background=p.surface, foreground=p.text, insertbackground=p.text,
                       selectbackground=p.accent, selectforeground="#ffffff",
                       highlightbackground=p.border, highlightcolor=p.accent)

    def get_value(self):
        return self.get("1.0", "end-1c")


class CheckBox(ttk.Checkbutton):
    def __init__(self, master, text="Check box", value=False, variable=None, **kwargs):
        self.variable = variable if variable is not None else tk.BooleanVar(master, value=value)
        super().__init__(master, text=text, variable=self.variable,
                         style="TPlus.TCheckbutton", **kwargs)

    def get(self):
        return bool(self.variable.get())

    def set(self, value):
        self.variable.set(bool(value))


class Switch(tk.Canvas):
    def __init__(self, master, text="Switch", value=False, command=None, **kwargs):
        self.text = text
        self.command = command
        self.variable = tk.BooleanVar(master, value=value)
        super().__init__(master, width=kwargs.pop("width", 190), height=kwargs.pop("height", 36), highlightthickness=0,
                         borderwidth=0, takefocus=True, cursor="hand2", **kwargs)
        self.bind("<Configure>", self._draw)
        self.bind("<ButtonRelease-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)
        self.variable.trace_add("write", self._draw)
        get_theme(self).register(self)

    def _toggle(self, event=None):
        self.focus_set()
        self.set(not self.get())
        if self.command:
            self.command(self.get())

    def get(self):
        return bool(self.variable.get())

    def set(self, value):
        self.variable.set(bool(value))

    def _apply_theme(self):
        self.configure(background=parent_color(self))
        self._draw()

    def _draw(self, *args):
        self.delete("all")
        p = get_theme(self).colors
        h = max(30, self.winfo_height())
        y = h/2
        _rounded(self, 1, y-11, 43, y+11, radius=11,
                 fill=p.accent if self.get() else p.border, outline="")
        x = 32 if self.get() else 12
        self.create_oval(x-8, y-8, x+8, y+8, fill="#ffffff", outline="")
        self.create_text(53, y, text=self.text, anchor="w", fill=p.text, font=(FONT, 10))
        if self.focus_get() == self:
            self.create_rectangle(0, 0, self.winfo_width()-1, h-1, outline=p.accent)


class ComboBox(ttk.Combobox):
    def __init__(self, master, options=("Option 1", "Option 2"), value=None, **kwargs):
        super().__init__(master, values=tuple(options), state="readonly",
                         style="TPlus.TCombobox", font=(FONT, 10), **kwargs)
        self.set(value if value is not None else (options[0] if options else ""))


class Slider(ttk.Scale):
    def __init__(self, master, value=50, command=None, **kwargs):
        super().__init__(master, from_=0, to=100, orient="horizontal",
                         style="TPlus.Horizontal.TScale", command=command, **kwargs)
        self.set(value)


class ProgressBar(ttk.Progressbar):
    def __init__(self, master, value=65, **kwargs):
        super().__init__(master, maximum=100, value=value, orient="horizontal",
                         style="TPlus.Horizontal.TProgressbar", **kwargs)


class Separator(tk.Frame):
    def __init__(self, master, **kwargs):
        super().__init__(master, height=2, borderwidth=0, **kwargs)
        get_theme(self).register(self)

    def _apply_theme(self):
        self.configure(background=get_theme(self).colors.border)
