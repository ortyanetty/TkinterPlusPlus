"""Themed Tk widgets. Every widget accepts colors={role: HEX_or_RGB}."""
import tkinter as tk
import math
from tkinter import ttk
from .theme import FONT, Theme, get_theme, get_colors, parent_color, validate_colors
from .geometry import LogicalGeometry, geometry


class Themed(LogicalGeometry):
    def __getitem__(self, key):
        return self.cget(key)

    def _init_colors(self, colors, master, options):
        self._density = get_theme(master).root._density
        self._color_overrides = validate_colors(colors)
        self._read_colors(options, master)

    def _bg_role(self):
        if isinstance(self, Button):
            return {"primary": "accent", "secondary": "surface", "danger": "danger"}[self.variant]
        if isinstance(self, (Entry, Textbox, ComboBox, SpinBox)):
            return "surface"
        if isinstance(self, ProgressBar):
            return "panel"
        if isinstance(self, Separator):
            return "border"
        return "background"

    def _read_colors(self, options, master=None):
        changed = False
        for key, role in [("bg", self._bg_role()), ("background", self._bg_role()),
                          ("fg", "text"), ("foreground", "text"), ("activebackground", "hover"),
                          ("bordercolor", "border"), ("troughcolor", "panel")]:
            if key in options:
                value = options.pop(key)
                if isinstance(value, str):
                    rgb = (master or self).winfo_rgb(value)
                    value = tuple(round(channel/257) for channel in rgb)
                self._color_overrides.update(validate_colors({role: value}))
                changed = True
        return changed

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs, cnf = {**cnf, **kwargs}, None
        changed = self._read_colors(kwargs) if kwargs else False
        result = super().configure(cnf, **kwargs)
        if changed:
            get_theme(self).refresh(self)
        return result

    config = configure

    def cget(self, key):
        roles = {"bg": self._bg_role(), "background": self._bg_role(),
                 "fg": "text", "foreground": "text", "activebackground": "hover",
                 "bordercolor": "border", "troughcolor": "panel"}
        if key in roles:
            if key in ("bg", "background") and self._bg_role() == "background":
                try:
                    return self.tk.call(self._w, "cget", "-background")
                except tk.TclError:
                    return self._color_overrides.get("background", parent_color(self))
            if key in ("fg", "foreground"):
                if isinstance(self, Button):
                    return self._color_overrides.get("text", self.colors.text if self.variant == "secondary" else self.colors.on_accent)
                if isinstance(self, Label) and self.muted:
                    return self._color_overrides.get("text", self.colors.muted)
            return getattr(self.colors, roles[key])
        return super().cget(key)

    @property
    def colors(self):
        return get_colors(self)

    def set_colors(self, colors=None, **roles):
        """Replace local overrides; omit roles to inherit the window palette again."""
        self._color_overrides = validate_colors({**(colors or {}), **roles})
        get_theme(self).refresh(self)

    def _style(self, suffix):
        name = f"TP{str(self)}.{suffix}"
        ttk.Widget.configure(self, style=name)
        return get_theme(self).style, name


class App(LogicalGeometry, tk.Tk):
    def __init__(self, title="Tkinter++", width=960, height=640, theme="dark", colors=None, scale=None, **kwargs):
        background = kwargs.pop("bg", kwargs.pop("background", None))
        super().__init__(**kwargs)
        self._density = round(float(self.tk.call("tk", "scaling"))/(4/3), 2) if scale is None else float(scale)
        self.tk.call("tk", "scaling", (4/3)*self._density)
        self.title(title)
        self.geometry(f"{width}x{height}")
        self._theme = Theme(self, theme, colors)
        self._theme.register(self)
        if background is not None:
            self.configure(bg=background)

    def geometry(self, value=None):
        return geometry(self, value)

    wm_geometry = geometry

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs, cnf = {**cnf, **kwargs}, None
        background = kwargs.pop("bg", kwargs.pop("background", None))
        result = super().configure(cnf, **kwargs)
        if background is not None and hasattr(self, "_theme"):
            if isinstance(background, str):
                background = tuple(round(channel/257) for channel in self.winfo_rgb(background))
            self._theme.overrides.update(validate_colors({"background": background}))
            self._theme.refresh(self)
        return result

    config = configure

    def _apply_theme(self):
        tk.Tk.configure(self, background=self.colors.background)

    @property
    def theme(self):
        return self._theme.name

    @property
    def colors(self):
        return self._theme.colors

    def set_theme(self, name):
        self._theme.set(name)

    def set_colors(self, colors=None, **roles):
        self._theme.overrides = validate_colors({**(colors or {}), **roles})
        self._theme.set(self.theme)


class Frame(Themed, tk.Frame):
    def __init__(self, master, variant="surface", colors=None, **kwargs):
        if variant not in ("surface", "panel", "background"):
            raise ValueError("Unknown frame variant")
        self.variant = variant
        self._init_colors(colors, master, kwargs)
        super().__init__(master, borderwidth=0, **kwargs)
        get_theme(self).register(self)

    def _apply_theme(self):
        tk.Frame.configure(self, background=self._color_overrides.get("background", getattr(self.colors, self.variant)))


class Label(Themed, tk.Label):
    def __init__(self, master, text="Label", font_size=11, weight="normal", muted=False, colors=None, **kwargs):
        self.muted = muted
        self._init_colors(colors, master, kwargs)
        super().__init__(master, text=text, font=kwargs.pop("font", (FONT, font_size, weight)),
                         borderwidth=0, anchor=kwargs.pop("anchor", "w"), **kwargs)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = self.colors
        tk.Label.configure(self, background=self._color_overrides.get("background", parent_color(self)),
                           foreground=self._color_overrides.get("text", p.muted if self.muted else p.text))


def _rounded(canvas, x1, y1, x2, y2, radius=5, **kwargs):
    r = max(0, min(radius, (x2-x1)/2, (y2-y1)/2))
    fill, outline = kwargs.get("fill", ""), kwargs.get("outline", "")
    width = kwargs.get("width", 1)
    if r < 1:
        return canvas.create_rectangle(x1, y1, x2, y2, **kwargs)
    corners = [(x1, y1, x1+2*r, y1+2*r, 90), (x2-2*r, y1, x2, y1+2*r, 0),
               (x2-2*r, y2-2*r, x2, y2, 270), (x1, y2-2*r, x1+2*r, y2, 180)]
    if fill:
        canvas.create_rectangle(x1+r, y1, x2-r, y2, fill=fill, outline="")
        canvas.create_rectangle(x1, y1+r, x2, y2-r, fill=fill, outline="")
        for a, b, c, d, angle in corners:
            canvas.create_arc(a, b, c, d, start=angle, extent=90, fill=fill, outline="", style="pieslice")
    if outline:
        for a, b, c, d, angle in corners:
            canvas.create_arc(a, b, c, d, start=angle, extent=90, outline=outline, width=width, style="arc")
        for line in [(x1+r, y1, x2-r, y1), (x1+r, y2, x2-r, y2),
                     (x1, y1+r, x1, y2-r), (x2, y1+r, x2, y2-r)]:
            canvas.create_line(*line, fill=outline, width=width)


def _pill_image(widget, width, height, fill, outline, background):
    """Small antialiased ttk elements, generated with the standard library."""
    image = tk.PhotoImage(master=widget, width=width, height=height)
    def rgb(color):
        return tuple(int(color[i:i+2], 16) for i in (1, 3, 5))
    bg, fg, edge = rgb(background), rgb(fill), rgb(outline)
    rows = []
    radius = height/2-1
    for y in range(height):
        pixels = []
        for x in range(width):
            center = max(height/2, min(x+0.5, width-height/2))
            distance = math.hypot(x+0.5-center, y+0.5-height/2)
            coverage = max(0, min(1, radius+0.5-distance))
            inside = max(0, min(1, radius-0.5-distance))
            color = tuple(round(bg[i]*(1-coverage)+edge[i]*(coverage-inside)+fg[i]*inside) for i in range(3))
            pixels.append("#{:02x}{:02x}{:02x}".format(*color))
        rows.append("{"+" ".join(pixels)+"}")
    image.put(" ".join(rows))
    return image


class Button(Themed, tk.Canvas):
    def __init__(self, master, text="Button", command=None, variant="primary", state="normal",
                 font_size=10, radius=5, colors=None, **kwargs):
        if variant not in ("primary", "secondary", "danger") or state not in ("normal", "disabled"):
            raise ValueError("Invalid button variant or state")
        self.text, self.command, self.variant = text, command, variant
        self.font_size, self.radius = font_size, radius
        self._font = kwargs.pop("font", None)
        self._enabled, self._hover, self._pressed = state == "normal", False, False
        self._init_colors(colors, master, kwargs)
        super().__init__(master, width=self.px(kwargs.pop("width", 140)), height=self.px(kwargs.pop("height", 38)),
                         highlightthickness=0, borderwidth=0, takefocus=True, **kwargs)
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<space>", lambda e: self.invoke())
        self.bind("<Return>", lambda e: self.invoke())
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)
        get_theme(self).register(self)

    def _set_hover(self, value):
        self._hover = value
        self._draw()

    def _press(self, event):
        if self._enabled:
            self.focus_set()
            self._pressed = True
            self._draw()

    def _release(self, event):
        pressed, self._pressed = self._pressed, False
        self._draw()
        if pressed and 0 <= event.x < tk.Canvas.winfo_width(self) and 0 <= event.y < tk.Canvas.winfo_height(self):
            self.invoke()

    def invoke(self):
        if self._enabled and self.command is not None:
            return self.command()

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs, cnf = {**cnf, **kwargs}, None
        if cnf is not None:
            return super().configure(cnf, **kwargs)
        if "variant" in kwargs:
            if kwargs["variant"] not in ("primary", "secondary", "danger"):
                raise ValueError("Unknown button variant")
            self.variant = kwargs.pop("variant")
        if "state" in kwargs:
            if kwargs["state"] not in ("normal", "disabled"):
                raise ValueError("Button state must be normal or disabled")
            self._enabled = kwargs.pop("state") == "normal"
            kwargs["cursor"] = "hand2" if self._enabled else "arrow"
        if "font" in kwargs:
            self._font = kwargs.pop("font")
        for key in ("text", "command", "font_size", "radius"):
            if key in kwargs:
                setattr(self, key, kwargs.pop(key))
        result = super().configure(**kwargs) if kwargs else None
        if hasattr(self, "_enabled") and self.winfo_exists():
            self._draw()
        return result

    config = configure

    def cget(self, key):
        if key == "font":
            return self._font or (FONT, self.font_size)
        if key in ("text", "command", "variant", "font_size", "radius"):
            return getattr(self, key)
        if key == "state":
            return "normal" if self._enabled else "disabled"
        return super().cget(key)

    def _apply_theme(self):
        tk.Canvas.configure(self, background=self._color_overrides.get("background", parent_color(self)),
                            cursor="hand2" if self._enabled else "arrow")
        self._draw()

    def _draw(self, event=None):
        self.delete("all")
        p = self.colors
        fill = {"primary": p.accent, "secondary": p.surface, "danger": p.danger}[self.variant]
        if self._enabled and self._hover:
            fill = p.hover if self.variant == "primary" else p.panel if self.variant == "secondary" else p.danger
        if self._enabled and self._pressed:
            fill = p.selection
        if not self._enabled:
            fill = p.panel
        foreground = self._color_overrides.get("text", p.text if self.variant == "secondary" else p.on_accent)
        if not self._enabled:
            foreground = p.muted
        w, h = tk.Canvas.winfo_width(self), tk.Canvas.winfo_height(self)
        if w <= 1:
            w, h = int(self.cget("width")), int(self.cget("height"))
        _rounded(self, self.px(1), self.px(1), w-self.px(1), h-self.px(1), self.px(self.radius), fill=fill, width=self.px(1),
                 outline=p.border if self.variant == "secondary" or not self._enabled else fill)
        if self.focus_get() == self and self._enabled:
            _rounded(self, self.px(3), self.px(3), w-self.px(3), h-self.px(3), self.px(max(0, self.radius-2)), fill="", outline=foreground, width=self.px(1))
        self.create_text(w/2, h/2, text=self.text, fill=foreground,
                         font=self._font or (FONT, self.font_size), width=max(10, w-self.px(20)))


class Entry(Themed, ttk.Entry):
    def __init__(self, master, value="", colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        state = kwargs.pop("state", "normal")
        super().__init__(master, font=kwargs.pop("font", (FONT, 10)), **kwargs)
        if value:
            self.insert(0, value)
        self.configure(state=state)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = self.colors
        s, name = self._style("TEntry")
        s.configure(name, fieldbackground=p.surface, foreground=p.text, insertcolor=p.text,
                    bordercolor=p.border, lightcolor=p.surface, darkcolor=p.surface,
                    selectbackground=p.selection, selectforeground=p.text, padding=(self.px(10), self.px(7)), borderwidth=1)
        s.map(name, bordercolor=[("focus", p.accent), ("active", p.hover)],
              fieldbackground=[("disabled", p.panel)], foreground=[("disabled", p.muted)])


class Textbox(Themed, tk.Text):
    def __init__(self, master, value="", colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        state = kwargs.pop("state", "normal")
        super().__init__(master, font=kwargs.pop("font", (FONT, 10)), wrap="word", relief="flat",
                         padx=self.px(10), pady=self.px(8), highlightthickness=self.px(1), undo=True, **kwargs)
        self.insert("1.0", value)
        self.configure(state=state)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = self.colors
        tk.Text.configure(self, background=p.surface, foreground=p.text, insertbackground=p.text,
                       selectbackground=p.selection, selectforeground=p.text,
                       highlightbackground=p.border, highlightcolor=p.accent)

    def get_value(self):
        return self.get("1.0", "end-1c")


class CheckBox(Themed, ttk.Checkbutton):
    def __init__(self, master, text="Check box", value=False, variable=None, colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        self.variable = variable if variable is not None else tk.BooleanVar(master, value=value)
        super().__init__(master, text=text, variable=self.variable, **kwargs)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = self.colors
        s, name = self._style("TCheckbutton")
        self._indicators = []
        for checked, disabled in [(False, False), (True, False), (False, True), (True, True)]:
            image = tk.PhotoImage(master=self, width=self.px(24), height=self.px(20))
            fill = p.muted if disabled and checked else p.accent if checked else p.surface
            image.put(p.border, to=tuple(self.px(n) for n in (1, 1, 19, 19)))
            image.put(fill, to=tuple(self.px(n) for n in (2, 2, 18, 18)))
            if checked:
                for x, y in [(5, 9), (6, 10), (7, 11), (8, 12), (9, 11), (10, 10), (11, 9), (12, 8), (13, 7), (14, 6)]:
                    image.put(p.on_accent, to=tuple(self.px(n) for n in (x, y, x+2, y+2)))
            self._indicators.append(image)
        element = name+".indicator"
        if element not in s.element_names():
            s.element_create(element, "image", self._indicators[0],
                ("disabled", "selected", self._indicators[3]), ("disabled", self._indicators[2]),
                ("selected", self._indicators[1]), width=self.px(24), sticky="w")
            s.layout(name, [("Checkbutton.padding", {"sticky": "nswe", "children": [
                (element, {"side": "left", "sticky": ""}),
                ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                    ("Checkbutton.label", {"sticky": "nswe"})]})]})])
            self._indicator_names = [str(i) for i in self._indicators]
        else:
            # Existing elements refer to image names; keep those names stable across theme changes.
            for original, replacement in zip(self._indicator_names, self._indicators):
                self.tk.call(original, "copy", str(replacement))
        if not hasattr(self, "_kept_indicators"):
            self._kept_indicators = self._indicators
        s.configure(name, background=self._color_overrides.get("background", parent_color(self)),
                    foreground=p.text, font=(FONT, 10), padding=(0, self.px(4)), focuscolor=p.accent)
        s.map(name, foreground=[("disabled", p.muted)])

    def get(self):
        return bool(self.variable.get())

    def set(self, value):
        self.variable.set(bool(value))


class RadioButton(Themed, ttk.Radiobutton):
    def __init__(self, master, text="Option", value="option", variable=None, selected=False, group=None, colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        if variable is None and group:
            if not hasattr(master, "_radio_groups"):
                master._radio_groups = {}
            if group not in master._radio_groups:
                master._radio_groups[group] = tk.StringVar(master, value="")
            variable = master._radio_groups[group]
        self.variable = variable if variable is not None else tk.StringVar(master, value="")
        if selected:
            self.variable.set(value)
        super().__init__(master, text=text, value=value, variable=self.variable, **kwargs)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = self.colors
        s, name = self._style("TRadiobutton")
        background = self._color_overrides.get("background", parent_color(self))
        images = []
        for selected, disabled in [(False, False), (True, False), (False, True), (True, True)]:
            circle = _pill_image(self, self.px(20), self.px(20), p.surface, p.muted if disabled else p.accent if selected else p.border, background)
            image = tk.PhotoImage(master=self, width=self.px(25), height=self.px(20))
            self.tk.call(str(image), "copy", str(circle), "-to", 0, 0)
            if selected:
                for y in range(self.px(6), self.px(14)):
                    for x in range(self.px(6), self.px(14)):
                        if math.hypot(x-self.px(9.5), y-self.px(9.5)) < self.px(4):
                            image.put(p.muted if disabled else p.accent, to=(x, y))
            images.append(image)
        element = name+".indicator"
        if element not in s.element_names():
            self._radio_images = images
            s.element_create(element, "image", images[0], ("disabled", "selected", images[3]),
                             ("disabled", images[2]), ("selected", images[1]), width=self.px(25))
            s.layout(name, [("Radiobutton.padding", {"sticky": "nswe", "children": [
                (element, {"side": "left", "sticky": ""}), ("Radiobutton.focus", {"side": "left", "sticky": "w", "children": [
                    ("Radiobutton.label", {"sticky": "nswe"})]})]})])
        else:
            for original, replacement in zip(self._radio_images, images):
                self.tk.call(str(original), "copy", str(replacement))
        s.configure(name, background=background,
                    foreground=p.text, font=(FONT, 10), indicatorbackground=p.surface,
                    indicatorforeground=p.accent, bordercolor=p.border, padding=(0, self.px(4)), focuscolor=p.accent)
        s.map(name, indicatorbackground=[("selected", p.accent)], foreground=[("disabled", p.muted)])

    def get(self):
        return self.variable.get()


class Switch(Themed, tk.Canvas):
    def __init__(self, master, text="Switch", value=False, command=None, state="normal", colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        self.text, self.command, self._state = text, command, state
        self.variable = tk.BooleanVar(master, value=value)
        super().__init__(master, width=self.px(kwargs.pop("width", 190)), height=self.px(kwargs.pop("height", 36)),
                         highlightthickness=0, borderwidth=0, takefocus=True, **kwargs)
        self.bind("<Configure>", self._draw)
        self.bind("<ButtonRelease-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.bind("<FocusIn>", self._draw)
        self.bind("<FocusOut>", self._draw)
        self.variable.trace_add("write", self._draw)
        get_theme(self).register(self)

    def _toggle(self, event=None):
        if self._state == "disabled":
            return
        self.focus_set()
        self.set(not self.get())
        if self.command:
            self.command(self.get())

    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs, cnf = {**cnf, **kwargs}, None
        for key in ("text", "command"):
            if key in kwargs:
                setattr(self, key, kwargs.pop(key))
        if "state" in kwargs:
            state = kwargs.pop("state")
            if state not in ("normal", "disabled"):
                raise ValueError("Switch state must be normal or disabled")
            self._state = state
        result = super().configure(cnf, **kwargs)
        if hasattr(self, "variable"):
            self._draw()
        return result

    config = configure

    def cget(self, key):
        if key == "state":
            return self._state
        if key in ("text", "command"):
            return getattr(self, key)
        return super().cget(key)

    def get(self):
        return bool(self.variable.get())

    def set(self, value):
        self.variable.set(bool(value))

    def _apply_theme(self):
        tk.Canvas.configure(self, background=self._color_overrides.get("background", parent_color(self)))
        self._draw()

    def _draw(self, *args):
        self.delete("all")
        p = self.colors
        enabled = self._state != "disabled"
        self.tk.call(self._w, "configure", "-cursor", "hand2" if enabled else "arrow")
        h = tk.Canvas.winfo_height(self)
        if h <= 1:
            h = int(self.cget("height"))
        y = h/2
        _rounded(self, self.px(1), y-self.px(10), self.px(39), y+self.px(10), self.px(10),
                 fill=p.accent if self.get() and enabled else p.panel, outline=p.border, width=self.px(1))
        x = self.px(29 if self.get() else 11)
        self.create_oval(x-self.px(7), y-self.px(7), x+self.px(7), y+self.px(7), fill=p.muted if not enabled else p.thumb, outline="")
        self.create_text(self.px(50), y, text=self.text, anchor="w", fill=p.text if enabled else p.muted, font=(FONT, 10))
        if self.focus_get() == self:
            _rounded(self, 0, y-self.px(12), self.px(41), y+self.px(12), self.px(12), fill="", outline=p.accent, width=self.px(1))


class ComboBox(Themed, ttk.Combobox):
    def __init__(self, master, options=("Option 1", "Option 2"), value=None, colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        super().__init__(master, values=tuple(kwargs.pop("values", options)), state=kwargs.pop("state", "readonly"),
                         font=kwargs.pop("font", (FONT, 10)), **kwargs)
        self.set(value if value is not None else (self.cget("values")[0] if self.cget("values") else ""))
        get_theme(self).register(self)

    def _apply_theme(self):
        p = self.colors
        s, name = self._style("TCombobox")
        s.configure(name, fieldbackground=p.surface, background=p.surface, foreground=p.text,
                    arrowcolor=p.muted, bordercolor=p.border, lightcolor=p.surface, darkcolor=p.surface,
                    padding=(self.px(10), self.px(7)), arrowsize=self.px(14), borderwidth=1)
        s.map(name, fieldbackground=[("disabled", p.panel), ("readonly", p.surface)],
              foreground=[("disabled", p.muted), ("readonly", p.text)],
              selectbackground=[("readonly", p.surface)], selectforeground=[("readonly", p.text)],
              bordercolor=[("focus", p.accent), ("active", p.hover)])
        popdown = self.tk.call("ttk::combobox::PopdownWindow", str(self))
        self.tk.call(popdown+".f.l", "configure", "-background", p.surface, "-foreground", p.text,
                     "-selectbackground", p.selection, "-selectforeground", p.text, "-font", (FONT, 10))


class SpinBox(Themed, ttk.Spinbox):
    def __init__(self, master, value=0, from_=0, to=100, increment=1, colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        super().__init__(master, from_=from_, to=to, increment=increment,
                         font=kwargs.pop("font", (FONT, 10)), **kwargs)
        self.set(value)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = self.colors
        s, name = self._style("TSpinbox")
        s.configure(name, fieldbackground=p.surface, background=p.panel, foreground=p.text,
                    arrowcolor=p.text, bordercolor=p.border, lightcolor=p.surface, darkcolor=p.surface,
                    insertcolor=p.text, padding=(self.px(10), self.px(7)), arrowsize=self.px(12))
        s.map(name, bordercolor=[("focus", p.accent)], foreground=[("disabled", p.muted)],
              fieldbackground=[("disabled", p.panel)])


class Slider(Themed, ttk.Scale):
    def __init__(self, master, value=50, command=None, colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        super().__init__(master, from_=kwargs.pop("from_", 0), to=kwargs.pop("to", 100),
                         orient="horizontal", command=command, **kwargs)
        self.set(value)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = self.colors
        s, name = self._style("Horizontal.TScale")
        background = self._color_overrides.get("background", parent_color(self))
        images = [_pill_image(self, self.px(12), self.px(6), p.panel, p.panel, background),
                  _pill_image(self, self.px(22), self.px(22), p.thumb, p.accent, background),
                  _pill_image(self, self.px(22), self.px(22), p.thumb, p.hover, background),
                  _pill_image(self, self.px(22), self.px(22), p.muted, p.border, background)]
        trough, thumb = name+".trough", name+".slider"
        if trough not in s.element_names():
            self._scale_images = images
            s.element_create(trough, "image", images[0], border=self.px(3), sticky="we")
            s.element_create(thumb, "image", images[1], ("disabled", images[3]), ("active", images[2]))
            s.layout(name, [(trough, {"sticky": "we", "children": [(thumb, {"side": "left", "sticky": ""})]})])
        else:
            for original, replacement in zip(self._scale_images, images):
                self.tk.call(str(original), "copy", str(replacement))
        s.configure(name, background=background, borderwidth=0)


class ProgressBar(Themed, ttk.Progressbar):
    def __init__(self, master, value=65, colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        super().__init__(master, maximum=kwargs.pop("maximum", 100), value=value, orient="horizontal", **kwargs)
        get_theme(self).register(self)

    def _apply_theme(self):
        p = self.colors
        s, name = self._style("Horizontal.TProgressbar")
        s.configure(name, background=p.accent, troughcolor=p.panel, bordercolor=p.panel,
                    lightcolor=p.accent, darkcolor=p.accent, borderwidth=0, thickness=self.px(6))


class Separator(Themed, tk.Frame):
    def __init__(self, master, colors=None, **kwargs):
        self._init_colors(colors, master, kwargs)
        super().__init__(master, height=kwargs.pop("height", 1), borderwidth=0, **kwargs)
        get_theme(self).register(self)

    def _apply_theme(self):
        tk.Frame.configure(self, background=self.colors.border)
