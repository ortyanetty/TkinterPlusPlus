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

    def test_custom_hex_rgb_colors_are_inherited_and_survive_theme_change(self):
        self.app.set_colors(surface=(30, 40, 50), accent="#8844cc")
        frame = ui.Frame(self.app, colors={"text": (200, 210, 220)})
        label = ui.Label(frame, text="Inherited")
        entry = ui.Entry(frame, colors={"surface": "#443322"})
        checkbox = ui.CheckBox(frame, value=True, colors={"on_accent": "#aabbcc"})
        for theme in ("light", "dark", "light"):
            self.app.set_theme(theme)
            self.app.update()
            self.assertEqual(label.cget("foreground"), "#c8d2dc")
            self.assertEqual(frame.cget("background"), "#1e2832")
            self.assertEqual(self.app._theme.style.lookup(entry.cget("style"), "fieldbackground"), "#443322")
            self.assertEqual(checkbox._kept_indicators[1].get(6, 10), (170, 187, 204))
        entry.set_colors()
        self.assertEqual(self.app._theme.style.lookup(entry.cget("style"), "fieldbackground"), "#1e2832")
        with self.assertRaises(ValueError):
            entry.set_colors(surface=(256, 0, 0))

    def test_radio_group_and_disabled_switch(self):
        first = ui.RadioButton(self.app, group="mode", value="first", selected=True)
        second = ui.RadioButton(self.app, group="mode", value="second")
        second.invoke()
        self.assertEqual(first.get(), "second")
        self.assertIs(first.variable, second.variable)
        calls = []
        switch = ui.Switch(self.app, value=False, command=calls.append, state="disabled")
        switch._toggle()
        self.assertFalse(switch.get())
        switch.configure(state="normal")
        switch._toggle()
        self.assertEqual(calls, [True])

    def test_custom_slider_remains_interactive_and_export_exposes_named_widgets(self):
        slider = ui.Slider(self.app, value=50)
        slider.place(x=20, y=20, width=240, height=36)
        self.app.update()
        slider.event_generate("<ButtonPress-1>", x=120, y=18)
        slider.event_generate("<B1-Motion>", x=180, y=18)
        slider.event_generate("<ButtonRelease-1>", x=180, y=18)
        self.assertGreater(slider.get(), 60)
        project = Project(colors={"accent": (60, 90, 120)})
        item = project.add("Button")
        item.props["colors"] = {"on_accent": "#123456"}
        namespace = {"__name__": "export_test"}
        exec(generate_python(project), namespace)
        exported = namespace["build_app"]()
        try:
            self.assertEqual(exported.colors.accent, "#3c5a78")
            self.assertEqual(exported.widgets[item.id].colors.on_accent, "#123456")
        finally:
            exported.destroy()

    def test_documented_example_callbacks_work(self):
        from examples.button import build_app as button_app
        from examples.form import build_app as form_app
        for factory in (button_app, form_app):
            app = factory()
            try:
                app.update()
                if "button" in app.widgets:
                    app.widgets["button"].invoke()
                    self.assertEqual(app.widgets["status"].cget("text"), "Кнопка нажата")
                else:
                    app.widgets["name"].insert(0, "Roman")
                    app.widgets["save"].invoke()
                    self.assertIn("Roman", app.widgets["status"].cget("text"))
            finally:
                app.destroy()

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
