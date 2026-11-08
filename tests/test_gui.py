from pathlib import Path
from types import SimpleNamespace
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

import tkinterplus as ui
from tkinterplus.builder import Builder
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


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.app = Builder()
        self.app._style_chrome()
        self.app.update()

    def tearDown(self):
        for preview in self.app.previews:
            try:
                preview.destroy()
            except tk.TclError:
                pass
        self.app.destroy()

    def test_add_duplicate_delete_undo_redo(self):
        app = self.app
        app.add_widget("Button")
        first = app.selected.id
        app.duplicate()
        self.assertEqual(len(app.project.widgets), 2)
        self.assertNotEqual(first, app.selected.id)
        app.delete_selected()
        self.assertEqual(len(app.project.widgets), 1)
        app.undo()
        self.assertEqual(len(app.project.widgets), 2)
        app.redo()
        self.assertEqual(len(app.project.widgets), 1)

    def test_drag_and_resize_form_a_single_undo_step(self):
        app = self.app
        app.add_widget("Button", 32, 32)
        app.update()
        history_size = len(app.history)
        app._drag_start(SimpleNamespace(x_root=100, y_root=100), app.selected.id)
        app._drag_motion(SimpleNamespace(x_root=145, y_root=128))
        app._drag_motion(SimpleNamespace(x_root=164, y_root=148))
        app._drag_end(None)
        self.assertEqual((app.selected.x, app.selected.y), (96, 80))
        self.assertEqual(len(app.history), history_size+1)
        app.undo()
        self.assertEqual((app.project.widgets[0].x, app.project.widgets[0].y), (32, 32))
        app.select(app.project.widgets[0].id)
        app._drag_start(SimpleNamespace(x_root=100, y_root=100), app.selected.id, resize=True)
        app._drag_motion(SimpleNamespace(x_root=140, y_root=130))
        app._drag_end(None)
        self.assertEqual((app.selected.width, app.selected.height), (200, 72))

    def test_invalid_properties_leave_project_unchanged(self):
        app = self.app
        app.add_widget("Label")
        before = app.project.to_dict()
        app.fields["width"] = lambda: "not a number"
        with patch.object(app, "_error") as error:
            app.apply_properties()
        error.assert_called_once()
        self.assertEqual(app.project.to_dict(), before)

    def test_properties_and_duplicate_names(self):
        app = self.app
        app.add_widget("Label")
        app.fields["prop:text"] = lambda: "Новый текст\nстрока 2"
        app.fields["width"] = lambda: "320"
        app.apply_properties()
        self.assertEqual(app.selected.props["text"], "Новый текст\nстрока 2")
        self.assertEqual(app.selected.width, 320)
        first = app.selected_id
        app.add_widget("Entry")
        before = app.project.to_dict()
        app.fields["id"] = lambda: first
        with patch.object(app, "_error") as error:
            app.apply_properties()
        error.assert_called_once()
        self.assertEqual(app.project.to_dict(), before)

    def test_theme_change_and_undo(self):
        app = self.app
        app.toggle_theme()
        self.assertEqual(app.theme, "light")
        self.assertEqual(app.project.theme, "light")
        app.undo()
        self.assertEqual(app.theme, "dark")

    def test_save_open_export_and_cancel(self):
        app = self.app
        qa = WORKSPACE / ".qa"
        qa.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=qa) as folder:
            json_path = Path(folder) / "test.json"
            py_path = Path(folder) / "test.py"
            app.add_widget("Switch")
            with patch("tkinterplus.builder.filedialog.asksaveasfilename", return_value=str(json_path)):
                self.assertTrue(app.save_project())
            self.assertFalse(app.dirty)
            expected = app.project.to_dict()
            app.add_widget("Button")
            with patch("tkinterplus.builder.messagebox.askyesnocancel", return_value=None):
                app.new_project()
            self.assertEqual(len(app.project.widgets), 2)
            with patch("tkinterplus.builder.messagebox.askyesnocancel", return_value=False), patch(
                "tkinterplus.builder.filedialog.askopenfilename", return_value=str(json_path)
            ):
                app.open_project()
            self.assertEqual(app.project.to_dict(), expected)
            with patch("tkinterplus.builder.filedialog.asksaveasfilename", return_value=str(py_path)):
                app.export_python()
            compile(py_path.read_text(encoding="utf-8"), str(py_path), "exec")

    def test_failed_save_preserves_dirty_state_and_path(self):
        app = self.app
        app.add_widget("Button")
        with patch.object(Project, "save", side_effect=OSError("No access")), patch.object(app, "_error"):
            self.assertFalse(app._save_to(WORKSPACE / ".qa" / "blocked.json"))
        self.assertTrue(app.dirty)
        self.assertIsNone(app.path)

    def test_palette_drop_uses_artboard_coordinates(self):
        app = self.app
        app._palette_start(SimpleNamespace(x_root=10, y_root=10), "Entry")
        app._palette_motion(SimpleNamespace(x_root=100, y_root=100))
        app._palette_drop(SimpleNamespace(x_root=app.artboard.winfo_rootx()+120,
                                         y_root=app.artboard.winfo_rooty()+160))
        self.assertEqual((app.selected.x, app.selected.y), (120, 160))

    def test_layers_and_preview_do_not_mutate_project(self):
        app = self.app
        app._replace_project(demo_project())
        first = app.project.widgets[0]
        app.select(first.id)
        app.reorder(1)
        self.assertEqual(app.project.widgets[1].id, first.id)
        before = app.project.to_dict()
        preview = app.preview()
        preview.update()
        switch = next(child for child in preview.winfo_children() if isinstance(child, ui.Switch))
        switch.set(False)
        self.assertEqual(app.project.to_dict(), before)

    def test_layer_selection_events_do_not_repeat_refresh(self):
        app = self.app
        app._replace_project(demo_project())
        app.select("button_1")
        with patch.object(app, "select", wraps=app.select) as select:
            app.layers.event_generate("<<ListboxSelect>>")
            app.update()
        select.assert_not_called()

    def test_real_widget_mouse_events_move_without_invoking(self):
        app = self.app
        app.add_widget("Button", 32, 32)
        widget = app.views[app.selected_id]
        invoked = []
        widget.command = lambda: invoked.append(True)
        app.update()
        widget.event_generate("<ButtonPress-1>", x=10, y=10)
        widget.event_generate("<B1-Motion>", x=74, y=58)
        widget.event_generate("<ButtonRelease-1>", x=10, y=10)
        app.update()
        self.assertEqual(invoked, [])
        self.assertEqual((app.selected.x, app.selected.y), (96, 80))


if __name__ == "__main__":
    unittest.main()
