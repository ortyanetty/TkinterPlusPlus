"""Theme palettes shared by the Tk library and the Qt designer."""
from dataclasses import dataclass, fields, replace
from weakref import WeakSet
import re
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
    on_accent: str = "#ffffff"
    thumb: str = "#ffffff"


PALETTES = {
    "dark": Palette("#18191d", "#222328", "#2c2d34", "#f0f0f3", "#a2a4ae",
                    "#464851", "#3975eb", "#5088f5", "#d63f51", "#294478"),
    "light": Palette("#f3f4f7", "#ffffff", "#eaecf1", "#20212a", "#636675",
                     "#bfc4ce", "#2563db", "#1954c5", "#c53046", "#dbe7ff"),
}
FONT = "Segoe UI"
COLOR_NAMES = tuple(field.name for field in fields(Palette))


def validate_colors(colors):
    """Normalize HEX / RGB roles into serializable #RRGGBB overrides."""
    if colors is None:
        return {}
    if not isinstance(colors, dict) or colors.keys() - set(COLOR_NAMES):
        raise ValueError("Цвета: ожидается словарь с именами из " + ", ".join(COLOR_NAMES))
    return {key: normalize_color(value) for key, value in colors.items()}


def normalize_color(value):
    if isinstance(value, (tuple, list)) and len(value) == 3 and all(
            type(channel) is int and 0 <= channel <= 255 for channel in value):
        return "#{:02x}{:02x}{:02x}".format(*value)
    if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return value.lower()
    raise ValueError("Цвет: HEX #RRGGBB или RGB (R, G, B), каналы от 0 до 255.")


def palette(name, overrides=None):
    return replace(PALETTES[name], **validate_colors(overrides))


class Theme:
    def __init__(self, root, name="dark", colors=None):
        self.root = root
        root._theme = self
        self.widgets = WeakSet()
        self.overrides = validate_colors(colors)
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.set(name)

    @property
    def colors(self):
        return palette(self.name, self.overrides)

    def set(self, name):
        if name not in PALETTES:
            raise ValueError("Theme must be 'light' or 'dark'")
        self.name = name
        p = self.colors
        for orientation in ("Vertical", "Horizontal"):
            self.style.configure(f"TPlus.{orientation}.TScrollbar", background=p.border,
                                 troughcolor=p.background, arrowcolor=p.muted, borderwidth=0)
        for name, color in [("background", p.surface), ("foreground", p.text),
                            ("selectBackground", p.accent), ("selectForeground", p.on_accent)]:
            self.root.option_add("*TCombobox*Listbox."+name, color)
        self.refresh(self.root)

    def refresh(self, widget):
        # Walk parents first so transparent-looking controls inherit the new surface.
        if hasattr(widget, "_apply_theme"):
            widget._apply_theme()
        for child in widget.winfo_children():
            self.refresh(child)

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


def get_colors(widget):
    theme = get_theme(widget)
    chain = []
    current = widget
    while current is not None and current is not theme.root:
        chain.append(getattr(current, "_color_overrides", {}))
        current = getattr(current, "master", None)
    overrides = dict(theme.overrides)
    for colors in reversed(chain):
        overrides.update(colors)
    return palette(theme.name, overrides)


def parent_color(widget):
    try:
        return widget.master.cget("background")
    except tk.TclError:
        return get_colors(widget).surface
