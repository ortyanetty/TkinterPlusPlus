"""Per-window themes. Uses only the Python standard library."""
from dataclasses import dataclass
from weakref import WeakSet
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class Palette:
    background: str
    surface: str
    panel: str
    text: str
    muted: str
    border: str
    accent: str
    hover: str
    danger: str
    selection: str


PALETTES = {
    "dark": Palette("#101827", "#182335", "#202e43", "#e9effa", "#97a9c4",
                    "#34455f", "#2563eb", "#3b78fa", "#dc354f", "#203f6b"),
    "light": Palette("#edf2f9", "#ffffff", "#e5ecf6", "#18283f", "#596d88",
                     "#c3cee0", "#2563eb", "#174ec7", "#c42d45", "#dbe8ff"),
}
FONT = "Segoe UI"


class Theme:
    def __init__(self, root, name="dark"):
        self.root = root
        self.widgets = WeakSet()
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.set(name)

    @property
    def colors(self):
        return PALETTES[self.name]

    def set(self, name):
        if name not in PALETTES:
            raise ValueError("Theme must be 'light' or 'dark'")
        self.name = name
        p = self.colors
        s = self.style
        s.configure("TPlus.TEntry", fieldbackground=p.surface, foreground=p.text,
                    insertcolor=p.text, bordercolor=p.border, lightcolor=p.border,
                    darkcolor=p.border, padding=8)
        s.map("TPlus.TEntry", bordercolor=[("focus", p.accent)],
              fieldbackground=[("disabled", p.panel)],
              foreground=[("disabled", p.muted)])
        s.configure("TPlus.TCombobox", fieldbackground=p.surface, background=p.panel,
                    foreground=p.text, arrowcolor=p.muted, bordercolor=p.border,
                    lightcolor=p.border, darkcolor=p.border, padding=7)
        s.map("TPlus.TCombobox", fieldbackground=[("readonly", p.surface)],
              foreground=[("readonly", p.text)], selectbackground=[("readonly", p.surface)],
              selectforeground=[("readonly", p.text)], bordercolor=[("focus", p.accent)])
        s.configure("TPlus.TCheckbutton", background=p.surface, foreground=p.text,
                    font=(FONT, 10), indicatorbackground=p.panel,
                    indicatorforeground="#ffffff", bordercolor=p.border, padding=4)
        s.map("TPlus.TCheckbutton", background=[("active", p.surface)],
              indicatorbackground=[("selected", p.accent)],
              foreground=[("disabled", p.muted)])
        s.configure("TPlus.Horizontal.TScale", background=p.surface,
                    troughcolor=p.panel, bordercolor=p.border)
        s.configure("TPlus.Horizontal.TProgressbar", background=p.accent,
                    troughcolor=p.panel, bordercolor=p.panel,
                    lightcolor=p.accent, darkcolor=p.accent)
        for orientation in ("Vertical", "Horizontal"):
            scrollbar = f"TPlus.{orientation}.TScrollbar"
            s.configure(scrollbar, background=p.border, troughcolor=p.background,
                        arrowcolor=p.muted, bordercolor=p.background,
                        lightcolor=p.border, darkcolor=p.border, width=12)
            s.map(scrollbar, background=[("active", p.muted), ("pressed", p.accent)])
        self.root.option_add("*TCombobox*Listbox.background", p.surface)
        self.root.option_add("*TCombobox*Listbox.foreground", p.text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", p.accent)
        for widget in list(self.widgets):
            try:
                if widget.winfo_exists():
                    widget._apply_theme()
            except tk.TclError:
                pass

    def register(self, widget):
        self.widgets.add(widget)
        widget._apply_theme()


def get_theme(widget):
    current = widget
    while current is not None:
        if "_theme" in current.__dict__:
            return current._theme
        current = getattr(current, "master", None)
    raise ValueError("Use a tkinterplus.App as the root window")


def parent_color(widget):
    try:
        return widget.master.cget("background")
    except tk.TclError:
        return get_theme(widget).colors.surface
