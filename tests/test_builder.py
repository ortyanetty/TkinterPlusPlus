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
    from tkinterplus.designer import Artboard

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

    def tearDown(self):
        self.app.saved = self.app.project.dumps()
        self.app.close()
        self.app.deleteLater()
        self.qt.processEvents()

    def focus_design(self):
        self.app.view.setFocus()
        self.qt.processEvents()

    def test_editor_is_qt_and_empty_canvas_has_no_banners(self):
        import tkinter
        self.assertIsInstance(self.app, QMainWindow)
        self.assertIsNone(tkinter._default_root)
        self.assertEqual(len(self.app.scene.items()), 1)
        self.assertIsInstance(self.app.scene.items()[0], Artboard)
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
        app = self.app
        for kind in SPECS:
            app.add_widget(kind)
        self.qt.processEvents()
        self.assertFalse(app.grab().isNull())
        self.assertEqual(len(app.views), len(SPECS))
        compile(generate_python(app.project), "export.py", "exec")

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
        start = app.view.mapFromScene(QPointF(45, 45))
        QTest.mousePress(app.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(app.view.viewport(), start+QPoint(64, 48), 10)
        QTest.mouseRelease(app.view.viewport(), Qt.MouseButton.LeftButton, pos=start+QPoint(64, 48))
        self.qt.processEvents()
        self.assertEqual((app.selected.x, app.selected.y), (96, 80))
        self.assertEqual(len(app.history), before+1)
        app.undo()
        self.assertEqual((app.project.widgets[0].x, app.project.widgets[0].y), (32, 32))
        app.select(app.project.widgets[0].id)
        node = app.selected
        start = app.view.mapFromScene(QPointF(node.x+node.width-3, node.y+node.height-3))
        QTest.mousePress(app.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
        QTest.mouseMove(app.view.viewport(), start+QPoint(40, 30), 10)
        QTest.mouseRelease(app.view.viewport(), Qt.MouseButton.LeftButton, pos=start+QPoint(40, 30))
        self.qt.processEvents()
        self.assertEqual((app.selected.width, app.selected.height), (200, 72))

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
