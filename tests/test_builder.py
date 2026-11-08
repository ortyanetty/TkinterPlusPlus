"""Qt integration tests; install the 'editor' extra to run this module."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HAS_QT = importlib.util.find_spec("PyQt6") is not None
if HAS_QT:
    from PyQt6.QtCore import QPoint, QPointF, QProcess, Qt
    from PyQt6.QtTest import QSignalSpy, QTest
    from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
    from tkinterplus.builder import Builder

from tkinterplus.codegen import generate_python
from tkinterplus.project import Project, SPECS, demo_project

WORKSPACE = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_QT, "Install PyQt6 (the editor extra) to test the editor")
class BuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])
        cls.qt.setStyle("Fusion")

    def setUp(self):
        self.app = Builder()
        self.app.show()
        self.qt.processEvents()
        self.app.view.pump()

    def tearDown(self):
        self.app.saved = self.app.project.dumps()
        self.app.close()
        self.app.deleteLater()
        self.qt.processEvents()

    def focus_design(self):
        self.app.view.setFocus()
        self.qt.processEvents()

    def native_event(self, widget, sequence, x, y, state=0):
        view = self.app.view
        view.pump()
        widget.event_generate(sequence, x=round(x*view.density), y=round(y*view.density), state=state)
        view.pump()
        self.qt.processEvents()

    def test_editor_is_qt_and_empty_canvas_has_no_banners(self):
        import tkinter
        self.assertIsInstance(self.app, QMainWindow)
        view = self.app.view
        self.assertIsInstance(view.root, tkinter.Tk)
        self.assertEqual(view.handles, {})
        self.assertEqual(view.api.GetParent(view.native_handle), int(view.host.winId()))
        self.assertTrue(view.root.winfo_viewable())
        self.assertEqual(self.app.tabs.tabText(0), "Конструктор")
        self.assertEqual(self.app.tabs.tabText(1), "Код")
        self.assertFalse(self.app.output_dock.isHidden())

    def test_add_duplicate_delete_undo_redo(self):
        app = self.app
        app.add_widget("Button")
        first = app.selected_id
        app.duplicate()
        self.assertEqual(len(app.project.widgets), 2)
        self.assertNotEqual(first, app.selected_id)
        app.delete_selected()
        self.assertEqual(len(app.project.widgets), 1)
        app.undo()
        self.assertEqual(len(app.project.widgets), 2)
        app.redo()
        self.assertEqual(len(app.project.widgets), 1)

    def test_all_widget_types_paint_and_export(self):
        from tkinterplus import widgets
        app = self.app
        for kind in SPECS:
            app.add_widget(kind)
        self.qt.processEvents()
        self.assertFalse(app.grab().isNull())
        self.assertEqual(len(app.views), len(SPECS))
        for model in app.project.widgets:
            actual = app.views[model.id].widget
            self.assertIsInstance(actual, getattr(widgets, model.kind))
            self.assertEqual((actual.winfo_width(), actual.winfo_height()), (model.width, model.height))
        compile(generate_python(app.project), "export.py", "exec")

    def test_real_widgets_test_mode_and_design_mode_do_not_change_saved_values(self):
        import tkinter as tk
        from tkinterplus import widgets
        app = self.app
        for kind in ("Entry", "Slider", "CheckBox", "ComboBox", "SpinBox", "Button"):
            app.add_widget(kind)
        before, history = app.project.to_dict(), len(app.history)
        self.assertIsInstance(app.views["slider_1"].widget, widgets.Slider)
        app.test_action.trigger()
        self.assertTrue(app.view.testing)
        self.assertFalse(app.view.background.find_withtag("grid"))
        entry = app.views["entry_1"].widget
        entry.delete(0, "end")
        entry.insert(0, "Проверка ввода")
        self.assertEqual(entry.get(), "Проверка ввода")
        slider = app.views["slider_1"].widget
        self.native_event(slider, "<ButtonPress-1>", 120, 18)
        self.native_event(slider, "<B1-Motion>", 200, 18, 256)
        self.native_event(slider, "<ButtonRelease-1>", 200, 18)
        self.assertGreater(slider.get(), 60)
        checkbox = app.views["checkbox_1"].widget
        old = checkbox.get()
        checkbox.invoke()
        self.assertNotEqual(checkbox.get(), old)
        calls = []
        button = app.views["button_1"].widget
        button.configure(command=lambda: calls.append(True))
        self.native_event(button, "<ButtonPress-1>", 20, 20)
        self.native_event(button, "<ButtonRelease-1>", 20, 20)
        self.assertEqual(calls, [True])
        self.assertEqual(app.project.to_dict(), before)
        self.assertEqual(len(app.history), history)
        app.test_action.trigger()
        self.assertEqual(app.views["entry_1"].widget.get(), before["widgets"][0]["props"]["value"])
        button = app.views["button_1"].widget
        button.configure(command=lambda: calls.append(True))
        self.native_event(button, "<ButtonPress-1>", 20, 20)
        self.native_event(button, "<ButtonRelease-1>", 20, 20)
        self.assertEqual(calls, [True])

    def test_zoom_keeps_real_geometry_and_exported_properties(self):
        import tkinter as tk
        app = self.app
        app.add_widget("Slider", 80, 120)
        app.selected.props["colors"] = {"thumb": "#e05293", "border": "#193d5a"}
        before = app.project.to_dict()
        for zoom in (0.5, 1.0, 1.5):
            app.view.zoom_to(zoom)
            widget = app.views["slider_1"].widget
            self.assertEqual(widget.winfo_width(), app.selected.width)
            self.assertEqual(tk.Widget.winfo_width(widget), round(app.selected.width*app.view.density))
            self.assertEqual(widget.colors.thumb, "#e05293")
            self.assertEqual(app.project.to_dict(), before)

    def test_multiple_selection_ctrl_click_drag_and_undo(self):
        app = self.app
        app.add_widget("Button", 32, 32)
        first = app.selected_id
        app.add_widget("Entry", 240, 120)
        second = app.selected_id
        app.select(first)
        second_widget = app.views[second].widget
        self.native_event(second_widget, "<ButtonPress-1>", 20, 15, 4)
        self.native_event(second_widget, "<ButtonRelease-1>", 20, 15, 4)
        self.assertEqual(app.selected_ids, {first, second})
        before = app.project.to_dict()
        history = len(app.history)
        widget = app.views[first].widget
        self.native_event(widget, "<ButtonPress-1>", 18, 13)
        self.native_event(widget, "<B1-Motion>", 58, 45, 256)
        self.native_event(widget, "<ButtonRelease-1>", 18, 13)
        self.assertEqual([(item.x, item.y) for item in app.project.widgets], [(72, 64), (280, 152)])
        self.assertEqual(len(app.history), history+1)
        app.undo()
        self.assertEqual(app.project.to_dict(), before)

    def test_rubber_band_selects_multiple_widgets(self):
        app = self.app
        app.add_widget("Button", 32, 32)
        app.add_widget("Entry", 240, 120)
        app.select(None)
        widget = app.view.background
        self.native_event(widget, "<ButtonPress-1>", 12, 12)
        self.native_event(widget, "<B1-Motion>", 500, 205, 256)
        self.native_event(widget, "<ButtonRelease-1>", 500, 205)
        self.assertEqual(len(app.selected_ids), 2)

    def test_group_clipboard_delete_and_atomic_paste_rejection(self):
        app = self.app
        app.add_widget("Button", 40, 40)
        app.add_widget("Entry", 240, 160)
        app.select_all()
        app.copy_widgets()
        app.paste_widgets()
        self.assertEqual(len(app.project.widgets), 4)
        clones = app.selected_items
        self.assertEqual((clones[1].x-clones[0].x, clones[1].y-clones[0].y), (200, 120))
        self.assertEqual(len({item.id for item in app.project.widgets}), 4)
        app.delete_selected()
        self.assertEqual(len(app.project.widgets), 2)
        app.undo()
        self.assertEqual(len(app.project.widgets), 4)
        app._replace_project(Project(width=240, height=200))
        with patch.object(app, "_error") as error:
            app.paste_widgets()
        error.assert_called_once()
        self.assertEqual(app.project.widgets, [])

    def test_duplicate_radio_gets_a_distinct_default_value(self):
        app = self.app
        app.add_widget("RadioButton")
        first = app.selected
        first.props["selected"] = True
        app.duplicate()
        self.assertNotEqual(first.props["value"], app.selected.props["value"])
        self.assertFalse(app.selected.props["selected"])
        self.assertEqual(first.props["group"], app.selected.props["group"])

    def test_arrange_alignment_distribution_and_equal_dimensions(self):
        app = self.app
        for x, y in [(32, 32), (280, 160), (600, 280)]:
            app.add_widget("Button", x, y)
        app.select_all()
        app.arrange("horizontal")
        items = app.project.widgets
        self.assertEqual(items[1].x-items[0].x-items[0].width, items[2].x-items[1].x-items[1].width)
        app.arrange("top")
        self.assertEqual({item.y for item in items}, {32})
        app.selected.width = 120
        app.arrange("width")
        self.assertEqual({item.width for item in items}, {120})
        app.undo()
        self.assertEqual([item.width for item in app.project.widgets], [120, 160, 160])

    def test_hex_rgb_fields_export_and_invalid_input_is_atomic(self):
        app = self.app
        field = app.field_widgets["color:accent"]
        field.edit.setText("#112233")
        field.mode.setCurrentText("RGB")
        self.assertEqual(field.edit.text(), "17, 34, 51")
        field.edit.setText("124, 92, 224")
        app.apply_properties()
        self.assertEqual(app.project.colors["accent"], "#7c5ce0")
        self.assertEqual(app.field_widgets["color:accent"].mode.currentText(), "RGB")
        app.add_widget("Button")
        field = app.field_widgets["color:on_accent"]
        field.mode.setCurrentText("RGB")
        field.edit.setText("2, 40, 70")
        app.apply_properties()
        self.assertEqual(app.selected.props["colors"]["on_accent"], "#022846")
        self.assertIn("#022846", generate_python(app.project))
        before = app.project.to_dict()
        app.field_widgets["color:border"].edit.setText("#12")
        with patch.object(app, "_error") as error:
            app.apply_properties()
        error.assert_called_once()
        self.assertEqual(app.project.to_dict(), before)

    def test_widget_copy_shortcut_does_not_replace_text_copy(self):
        app = self.app
        app.add_widget("Entry")
        field = app.field_widgets["prop:value"]
        field.setText("Обычный текст")
        field.setFocus()
        field.selectAll()
        QTest.keyClick(field, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(QApplication.clipboard().text(), "Обычный текст")

    def test_palette_double_click_and_search(self):
        app = self.app
        app.palette_search.setText("Button")
        self.assertFalse(app.palette.item(1).isHidden())
        self.assertTrue(app.palette.item(0).isHidden())
        item = app.palette.item(1)
        position = app.palette.visualItemRect(item).center()
        QTest.mouseClick(app.palette.viewport(), Qt.MouseButton.LeftButton, pos=position)
        QTest.mouseDClick(app.palette.viewport(), Qt.MouseButton.LeftButton, pos=position)
        self.qt.processEvents()
        self.assertEqual(app.selected.kind, "Button")

    def test_drag_and_resize_are_single_undo_steps(self):
        app = self.app
        app.add_widget("Button", 32, 32)
        self.qt.processEvents()
        before = len(app.history)
        widget = app.views[app.selected_id].widget
        self.native_event(widget, "<ButtonPress-1>", 13, 13)
        self.native_event(widget, "<B1-Motion>", 77, 61, 256)
        self.native_event(widget, "<ButtonRelease-1>", 13, 13)
        self.qt.processEvents()
        self.assertEqual((app.selected.x, app.selected.y), (96, 80))
        self.assertEqual(len(app.history), before+1)
        app.undo()
        self.assertEqual((app.project.widgets[0].x, app.project.widgets[0].y), (32, 32))
        app.select(app.project.widgets[0].id)
        node = app.selected
        expected_height = app.snap(node.height+30)
        handle = app.view._outlines[-1]
        self.native_event(handle, "<ButtonPress-1>", 4, 4)
        self.native_event(handle, "<B1-Motion>", 44, 34, 256)
        self.native_event(handle, "<ButtonRelease-1>", 4, 4)
        self.qt.processEvents()
        self.assertEqual((app.selected.width, app.selected.height), (200, expected_height))

    def test_drop_clamps_geometry_and_rejects_outside_canvas(self):
        app = self.app
        self.assertTrue(app.view.add_drop("Entry", QPointF(120, 160)))
        self.assertEqual((app.selected.x, app.selected.y), (120, 160))
        self.assertTrue(app.view.add_drop("Button", QPointF(799, 559)))
        self.assertEqual(app.selected.x+app.selected.width, app.project.width)
        self.assertFalse(app.view.add_drop("Button", QPointF(-2, 20)))
        self.assertFalse(app.view.add_drop("Unknown", QPointF(20, 20)))

    def test_arrows_and_text_editing_use_the_correct_target(self):
        app = self.app
        app.add_widget("Entry", 32, 32)
        self.focus_design()
        QTest.keyClick(app.view, Qt.Key.Key_Right)
        self.assertEqual(app.selected.x, 40)
        field = app.field_widgets["prop:value"]
        field.setText("Текст для проверки Undo")
        field.setFocus()
        field.selectAll()
        QTest.keyClick(field, Qt.Key.Key_Delete)
        self.assertEqual(field.text(), "")
        self.assertEqual(len(app.project.widgets), 1)
        QTest.keyClick(field, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        self.assertNotEqual(field.text(), "")
        self.assertEqual(app.selected.x, 40)

    def test_property_changes_and_duplicate_name_validation(self):
        app = self.app
        app.add_widget("Label")
        app.fields["prop:text"] = lambda: "Текст\nстрока 2"
        app.fields["width"] = lambda: 320
        app.apply_properties()
        self.assertEqual(app.selected.props["text"], "Текст\nстрока 2")
        self.assertEqual(app.selected.width, 320)
        first = app.selected_id
        app.add_widget("Entry")
        before = app.project.to_dict()
        app.fields["id"] = lambda: first
        with patch.object(app, "_error") as error:
            app.apply_properties()
        error.assert_called_once()
        self.assertEqual(app.project.to_dict(), before)

    def test_invalid_properties_do_not_change_project(self):
        app = self.app
        app.add_widget("Button")
        before = app.project.to_dict()
        app.fields["width"] = lambda: "bad"
        with patch.object(app, "_error") as error:
            app.apply_properties()
        error.assert_called_once()
        self.assertEqual(app.project.to_dict(), before)

    def test_editor_theme_is_independent_from_exported_theme(self):
        app = self.app
        before = app.project.to_dict()
        app.set_editor_theme("light")
        self.qt.processEvents()
        self.assertEqual(app.editor_theme, "light")
        self.assertEqual(app.project.to_dict(), before)
        app.fields["theme"] = lambda: "light"
        app.apply_properties()
        self.assertEqual(app.project.theme, "light")
        app.undo()
        self.assertEqual(app.project.theme, "dark")
        self.assertEqual(app.editor_theme, "light")

    def test_layers_select_and_reorder_without_recursive_refresh(self):
        app = self.app
        app._replace_project(demo_project())
        app.layers.setCurrentItem(app.layer_items["entry_1"])
        self.qt.processEvents()
        self.assertEqual(app.selected_id, "entry_1")
        index = app.project.widgets.index(app.selected)
        app.reorder(1)
        self.assertEqual(app.project.widgets[index+1].id, "entry_1")

    def test_save_open_export_and_cancel(self):
        app = self.app
        qa = WORKSPACE / ".qa"
        qa.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=qa) as folder:
            json_path, py_path = Path(folder)/"test.json", Path(folder)/"test.py"
            app.add_widget("Switch")
            with patch("tkinterplus.builder.QFileDialog.getSaveFileName", return_value=(str(json_path), "")):
                self.assertTrue(app.save_project())
            self.assertFalse(app.dirty)
            expected = app.project.to_dict()
            app.add_widget("Button")
            with patch("tkinterplus.builder.QMessageBox.question", return_value=QMessageBox.StandardButton.Cancel):
                app.new_project()
            self.assertEqual(len(app.project.widgets), 2)
            with patch("tkinterplus.builder.QMessageBox.question", return_value=QMessageBox.StandardButton.Discard), patch(
                "tkinterplus.builder.QFileDialog.getOpenFileName", return_value=(str(json_path), "")
            ):
                app.open_project()
            self.assertEqual(app.project.to_dict(), expected)
            with patch("tkinterplus.builder.QFileDialog.getSaveFileName", return_value=(str(py_path), "")):
                app.export_python()
            self.assertEqual(py_path.read_text(encoding="utf-8"), generate_python(app.project))

    def test_failed_save_preserves_path_and_dirty_state(self):
        app = self.app
        app.add_widget("Button")
        with patch.object(Project, "save", side_effect=OSError("No access")), patch.object(app, "_error"):
            self.assertFalse(app._save_to(WORKSPACE / ".qa" / "blocked.json"))
        self.assertTrue(app.dirty)
        self.assertIsNone(app.path)

    def test_code_tab_tracks_project_and_copies_current_source(self):
        app = self.app
        app.add_widget("Textbox")
        app.show_code()
        self.assertEqual(app.tabs.currentIndex(), 1)
        self.assertEqual(app.code.toPlainText(), generate_python(app.project))
        app.copy_code()
        self.assertEqual(QApplication.clipboard().text(), generate_python(app.project))
        app.tabs.setCurrentIndex(0)
        self.qt.processEvents()
        app.view.pump()
        self.assertTrue(app.view.root.winfo_viewable())

    def test_dock_panels_can_be_restored(self):
        app = self.app
        app.output_dock.hide()
        app.toolbox_dock.hide()
        app.restore_layout()
        self.assertFalse(app.output_dock.isHidden())
        self.assertFalse(app.toolbox_dock.isHidden())

    def test_real_tk_preview_is_separate_process_and_stops_on_close(self):
        app = self.app
        app._replace_project(demo_project())
        before = app.project.to_dict()
        process = app.preview()
        project_path = Path(process.project_file.fileName())
        self.assertTrue(project_path.is_file())
        self.assertTrue(process.waitForStarted(5000))
        finished = QSignalSpy(process.finished)
        QTest.qWait(500)
        self.assertEqual(process.state(), QProcess.ProcessState.Running)
        self.assertEqual(app.project.to_dict(), before)
        app.close()
        self.assertEqual(len(finished), 1)
        self.assertEqual(app.previews, [])
        self.assertFalse(project_path.exists())

    def test_frozen_preview_calls_bundled_worker_mode(self):
        app = self.app
        with patch("tkinterplus.builder.sys.frozen", True, create=True), patch.object(QProcess, "start"):
            process = app.preview()
        self.assertEqual(process.arguments()[0], "--preview")
        self.assertEqual(Project.load(process.arguments()[1]), app.project)
        process.project_file.remove()
        app.previews.remove(process)
        process.deleteLater()

    def test_executable_entry_dispatches_preview_before_editor(self):
        import run_builder
        with patch("run_builder.sys.argv", ["program.exe", "--preview", "project.json"]), patch(
            "tkinterplus.preview.main"
        ) as preview:
            self.assertEqual(run_builder.main(), 0)
        preview.assert_called_once_with(["project.json"])


if __name__ == "__main__":
    unittest.main()
