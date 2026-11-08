import ast
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from tkinterplus.codegen import generate_python
from tkinterplus.project import Project, ProjectError, SPECS, demo_project

WORKSPACE = Path(__file__).resolve().parents[1]


class ProjectTests(unittest.TestCase):
    def test_round_trip_all_widget_types_and_unicode(self):
        project = Project(title="Окно ‘тест’\n第二", width=1000, height=800, theme="light")
        for index, kind in enumerate(SPECS):
            project.add(kind, 40+index*8, 50+index*8)
        restored = Project.loads(project.dumps())
        self.assertEqual(restored.to_dict(), project.to_dict())

    def test_defaults_are_independent(self):
        project = Project()
        first = project.add("ComboBox")
        second = project.add("ComboBox")
        first.props["options"].append("Custom")
        self.assertNotIn("Custom", second.props["options"])
        self.assertNotIn("Custom", SPECS["ComboBox"].defaults["options"])

    def test_save_load_and_no_partial_overwrite_on_invalid_project(self):
        qa = WORKSPACE / ".qa"
        qa.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=qa) as folder:
            path = Path(folder) / "проект.json"
            project = demo_project()
            project.save(path)
            source = path.read_bytes()
            self.assertEqual(Project.load(path), project)
            project.width = -1
            with self.assertRaises(ProjectError):
                project.save(path)
            self.assertEqual(path.read_bytes(), source)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_schema_rejects_invalid_input(self):
        base = demo_project().to_dict()
        mutations = [
            lambda d: d.update(version=True),
            lambda d: d.update(version=2),
            lambda d: d["window"].update(width=239),
            lambda d: d["window"].update(height="560"),
            lambda d: d["window"].update(theme="unknown"),
            lambda d: d["widgets"][0].update(kind="__import__"),
            lambda d: d["widgets"][0].update(id="class"),
            lambda d: d["widgets"][0].update(id="a; print('bad')"),
            lambda d: d["widgets"][0].update(width=True),
            lambda d: d["widgets"][0].update(x=-5),
            lambda d: d["widgets"][0].update(x=4096),
            lambda d: d["widgets"].append(deepcopy(d["widgets"][0])),
            lambda d: d["widgets"][0]["props"].update(command="print('bad')"),
            lambda d: d["widgets"][0]["props"].update(text="bad\x00text"),
        ]
        for mutate in mutations:
            data = deepcopy(base)
            mutate(data)
            with self.subTest(data=data):
                with self.assertRaises(ProjectError):
                    Project.from_dict(data)

    def test_numeric_and_boolean_property_validation(self):
        for kind, value in [("Slider", float("nan")), ("ProgressBar", float("inf")),
                            ("Slider", -1), ("ProgressBar", 101), ("CheckBox", "false"),
                            ("Switch", 1)]:
            project = Project()
            project.add(kind).props["value"] = value
            with self.subTest(kind=kind, value=value), self.assertRaises(ProjectError):
                Project.from_dict(project.to_dict())

    def test_combobox_requires_matching_value(self):
        project = Project()
        project.add("ComboBox").props["value"] = "Missing"
        with self.assertRaises(ProjectError):
            project.dumps()

    def test_invalid_json_is_friendly_error(self):
        for source in ("", "{", "[]", "null", '{"version": 1}'):
            with self.subTest(source=source), self.assertRaises(ProjectError):
                Project.loads(source)

    def test_add_clamps_coordinates_to_window(self):
        project = Project(width=240, height=200)
        item = project.add("Frame", 900, -50)
        self.assertEqual((item.x, item.y, item.width, item.height), (0, 0, 240, 180))
        self.assertEqual(project, project.clone())

    def test_export_is_deterministic_and_strings_remain_literals(self):
        project = Project(title="'; raise RuntimeError('injected') #")
        item = project.add("Button")
        item.props["text"] = "'); __import__('os').system('bad') #\nКнопка"
        source = generate_python(project)
        self.assertEqual(source, generate_python(project))
        tree = ast.parse(source)
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
        self.assertFalse(any(isinstance(call.func, ast.Name) and call.func.id in
                             ("__import__", "exec", "eval", "RuntimeError") for call in calls))
        self.assertIn(item.props["text"], [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)])

    def test_export_revalidates_mutated_objects(self):
        project = Project()
        item = project.add("Button")
        item.kind = "NotAWidget"
        with self.assertRaises(ProjectError):
            generate_python(project)


if __name__ == "__main__":
    unittest.main()
