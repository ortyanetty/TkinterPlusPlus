"""Logical pixels shared by standalone apps and the embedded designer."""
import re


class LogicalGeometry:
    _density = 1.0

    def px(self, value):
        return round(float(value)*self._density)

    def place_configure(self, cnf=None, **kwargs):
        options = {**(cnf or {}), **kwargs}
        for key in ('x', 'y', 'width', 'height'):
            if key in options and options[key] is not None:
                options[key] = self.px(options[key])
        return super().place_configure(**options)

    place = place_configure

    def place_info(self):
        options = super().place_info()
        for key in ('x', 'y', 'width', 'height'):
            if options.get(key):
                options[key] = str(round(float(options[key])/self._density))
        return options

    def winfo_x(self):
        return round(super().winfo_x()/self._density)

    def winfo_y(self):
        return round(super().winfo_y()/self._density)

    def winfo_width(self):
        return round(super().winfo_width()/self._density)

    def winfo_height(self):
        return round(super().winfo_height()/self._density)


def geometry(window, value=None):
    if value is None:
        actual = window.tk.call('wm', 'geometry', window._w)
        match = re.fullmatch(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)', actual)
        if match:
            width,height,x,y = map(int,match.groups())
            return f'{round(width/window._density)}x{round(height/window._density)}{x:+d}{y:+d}'
        return actual
    match = re.fullmatch(r'(\d+)x(\d+)(.*)', value)
    if match:
        value=f'{window.px(match[1])}x{window.px(match[2])}{match[3]}'
    return window.tk.call('wm', 'geometry', window._w, value)
