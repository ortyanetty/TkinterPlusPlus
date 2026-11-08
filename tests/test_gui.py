from pathlib import Path


import tkinter as tk
import unittest


import tkinterplus as ui

from tkinterplus.codegen import generate_python
from tkinterplus.project import Project, SPECS, create_widget, demo_project

WORKSPACE = Path(__file__).resolve().parents[1]


class WidgetTests(unittest.TestCase):
    def setUp(self):
        self.app = ui.App(width=1000, height=800)

    def tearDown(self):
        self.app.destroy()

    def test_every_widget_renders_and_switches_themes(self):
        p = Project(width=1000, height=800)
        for i, kind in enumerate(SPECS):
            create_widget(self.app, p.add(kind, 20+i*12, 20+i*40))
        self.app.update()
        self.app.set_theme("light")
        self.app.update()
        self.assertEqual(len(self.app.winfo_children()), len(SPECS))
        self.assertEqual(self.app.cget("background"), self.app.colors.background)

    def test_theme_refreshes_nested_parent_backgrounds(self):
        frame = ui.Frame(self.app, variant="panel")
        frame.pack()
        label = ui.Label(frame, text="Nested")
        label.pack()
        self.app.set_theme("light")
        self.assertEqual(label.cget("background"), frame.cget("background"))

    def test_widget_values_and_button_callback(self):
        called = []
        button = ui.Button(self.app, command=lambda: called.append(True), width=180)
        button.invoke()
        self.assertEqual(called, [True])
        disabled = ui.Button(self.app, command=lambda: called.append(False), state="disabled")
        disabled.invoke()
        self.assertEqual(called, [True])
        button.configure(text="Обновлено", state="disabled", variant="secondary")
        button.invoke()
        self.assertEqual(button.cget("text"), "Обновлено")
        self.assertEqual(button.cget("state"), "disabled")
        self.assertEqual(called, [True])
        button.config(state="normal")
        button.invoke()
        self.assertEqual(called, [True, True])
        for widget in (ui.Switch(self.app, value=False), ui.CheckBox(self.app, value=False)):
            widget.set(True)
            self.assertTrue(widget.get())
        self.assertEqual(ui.Entry(self.app, value="Привет").get(), "Привет")
        self.assertEqual(ui.Textbox(self.app, value="two\nlines").get_value(), "two\nlines")

    def test_exported_application_runs_with_every_widget(self):
        p = Project(width=1000, height=800)
        for i, kind in enumerate(SPECS):
            p.add(kind, 20+i*10, 20+i*40)
        scope = {"__name__": "generated_test"}
        exec(compile(generate_python(p), "generated_app.py", "exec"), scope)
        exported = scope["build_app"]()
        try:
            exported.update()
            self.assertEqual(len(exported.winfo_children()), len(SPECS))
            for actual, expected in zip(exported.winfo_children(), p.widgets):
                self.assertEqual(type(actual).__name__, expected.kind)
                self.assertEqual(actual.winfo_x(), expected.x)
                self.assertEqual(actual.winfo_y(), expected.y)
                self.assertEqual(actual.winfo_width(), expected.width)
                self.assertEqual(actual.winfo_height(), expected.height)
        finally:
            exported.destroy()
