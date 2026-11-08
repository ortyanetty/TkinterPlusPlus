"""Tkinter++: themed widgets and a visual interface builder."""
from .widgets import (
    App, Button, CheckBox, ComboBox, Entry, Frame, Label, ProgressBar,
    Separator, Slider, Switch, Textbox, RadioButton, SpinBox,
)

__version__ = "0.4.0"
__all__ = [
    "App", "Button", "CheckBox", "ComboBox", "Entry", "Frame", "Label",
    "ProgressBar", "Separator", "Slider", "Switch", "Textbox", "RadioButton", "SpinBox",
]

# Familiar Tkinter spellings; the existing names remain supported.
Tk = App
Text = Textbox
Checkbutton = CheckBox
Radiobutton = RadioButton
Spinbox = SpinBox
Scale = Slider
Combobox = ComboBox
Progressbar = ProgressBar
from tkinter import StringVar, BooleanVar, IntVar, DoubleVar, END, NORMAL, DISABLED, LEFT, RIGHT, TOP, BOTTOM, BOTH, X, Y
__all__ += ["Tk", "Text", "Checkbutton", "Radiobutton", "Spinbox", "Scale", "Combobox", "Progressbar",
            "StringVar", "BooleanVar", "IntVar", "DoubleVar", "END", "NORMAL", "DISABLED",
            "LEFT", "RIGHT", "TOP", "BOTTOM", "BOTH", "X", "Y"]
