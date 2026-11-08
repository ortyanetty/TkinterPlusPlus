"""Validated, versioned project data shared by the editor and exporter."""
from copy import deepcopy
from dataclasses import dataclass, field
import json
import keyword
import math
from pathlib import Path
import re
from .theme import validate_colors

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_WIDGETS = 500


@dataclass(frozen=True)
class WidgetSpec:
    label: str
    width: int
    height: int
    defaults: dict


SPECS = {
    "Label": WidgetSpec("Надпись", 200, 36, {"text": "Новая надпись", "font_size": 12,
                                           "weight": "normal", "muted": False, "anchor": "w"}),
    "Button": WidgetSpec("Кнопка", 160, 38, {"text": "Кнопка", "variant": "primary", "state": "normal", "font_size": 10, "radius": 5}),
    "Entry": WidgetSpec("Поле ввода", 240, 38, {"value": "", "show": "", "state": "normal"}),
    "Textbox": WidgetSpec("Текстовая область", 280, 110, {"value": "", "state": "normal"}),
    "CheckBox": WidgetSpec("Флажок", 220, 36, {"text": "Запомнить выбор", "value": True, "state": "normal"}),
    "Switch": WidgetSpec("Переключатель", 220, 36, {"text": "Уведомления", "value": True, "state": "normal"}),
    "ComboBox": WidgetSpec("Выпадающий список", 240, 40,
                          {"options": ["Вариант 1", "Вариант 2", "Вариант 3"], "value": "Вариант 1", "state": "readonly"}),
    "Slider": WidgetSpec("Ползунок", 240, 36, {"value": 50}),
    "ProgressBar": WidgetSpec("Прогресс", 240, 16, {"value": 65}),
    "Frame": WidgetSpec("Панель", 280, 180, {"variant": "panel"}),
    "Separator": WidgetSpec("Разделитель", 280, 2, {}),
    "RadioButton": WidgetSpec("Радиокнопка", 220, 36, {"text": "Вариант", "value": "option", "group": "choice", "selected": False, "state": "normal"}),
    "SpinBox": WidgetSpec("Числовое поле", 160, 38, {"value": 0, "from_": 0, "to": 100, "increment": 1, "state": "normal"}),
}
for _spec in SPECS.values():
    _spec.defaults["colors"] = {}


class ProjectError(ValueError):
    """An invalid or unsupported project; safe to display to the user."""


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ProjectError(f"{name}: требуется целое число от {low} до {high}.")
    return value


def _string(value, name, max_length=10000):
    if not isinstance(value, str) or len(value) > max_length or "\x00" in value:
        raise ProjectError(f"{name}: требуется строка длиной до {max_length} без нулевых символов.")
    return value


def _choice(value, name, choices):
    if value not in choices:
        raise ProjectError(f"{name}: допустимы {', '.join(choices)}.")
    return value


def _props(kind, source):
    if not isinstance(source, dict):
        raise ProjectError("Свойства виджета должны быть объектом.")
    defaults = SPECS[kind].defaults
    if source.keys() - defaults.keys():
        raise ProjectError(f"Неизвестные свойства {kind}: {', '.join(source.keys() - defaults.keys())}.")
    result = deepcopy(defaults)
    result.update(source)
    for name, value in result.items():
        if name == "colors":
            try:
                result[name] = validate_colors(value)
            except ValueError as error:
                raise ProjectError(str(error)) from error
        elif name in ("text", "show", "group") or (name == "value" and kind in ("Entry", "Textbox", "ComboBox", "RadioButton")):
            _string(value, name)
        elif name in ("muted", "selected") or (name == "value" and kind in ("CheckBox", "Switch")):
            if type(value) is not bool:
                raise ProjectError(f"{name}: требуется true или false.")
        elif name == "font_size":
            _integer(value, name, 8, 72)
        elif name == "radius":
            _integer(value, name, 0, 30)
        elif name == "state":
            _choice(value, name, ("normal", "disabled", "readonly") if kind in ("Entry", "ComboBox", "SpinBox") else ("normal", "disabled"))
        elif kind == "SpinBox" and name in ("value", "from_", "to", "increment"):
            if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1_000_000:
                raise ProjectError("Числовое поле: значение должно быть конечным числом от −1000000 до 1000000.")
        elif name == "weight":
            _choice(value, name, ("normal", "bold"))
        elif name == "anchor":
            _choice(value, name, ("w", "center", "e"))
        elif name == "variant":
            _choice(value, name, ("primary", "secondary", "danger") if kind == "Button" else
                    ("surface", "panel", "background"))
        elif name == "options":
            if not isinstance(value, list) or not 1 <= len(value) <= 100:
                raise ProjectError("Список должен содержать от 1 до 100 вариантов.")
            for option in value:
                _string(option, "Вариант", 1000)
        elif name == "value":
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100:
                raise ProjectError("Значение должно быть числом от 0 до 100.")
    if kind == "ComboBox" and result["value"] not in result["options"]:
        raise ProjectError("Значение списка должно совпадать с одним из вариантов.")
    if kind == "SpinBox" and (result["from_"] >= result["to"] or result["increment"] <= 0 or
                             not result["from_"] <= result["value"] <= result["to"]):
        raise ProjectError("Числовое поле: минимум < максимум, шаг > 0, значение внутри диапазона.")
    return result


@dataclass
class WidgetModel:
    id: str
    kind: str
    x: int
    y: int
    width: int
    height: int
    props: dict = field(default_factory=dict)

    def to_dict(self):
        return {"id": self.id, "kind": self.kind, "x": self.x, "y": self.y,
                "width": self.width, "height": self.height, "props": deepcopy(self.props)}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ProjectError("Виджет должен быть объектом.")
        required = {"id", "kind", "x", "y", "width", "height", "props"}
        if set(data) != required:
            raise ProjectError("Неверный набор полей виджета.")
        name = _string(data["id"], "Имя", 48)
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name) or keyword.iskeyword(name):
            raise ProjectError("Имя: латинская строчная буква, затем буквы, цифры или подчёркивание; без ключевых слов Python.")
        kind = data["kind"]
        if not isinstance(kind, str) or kind not in SPECS:
            raise ProjectError("Неизвестный тип виджета.")
        return cls(name, kind, _integer(data["x"], "X", 0, 4096),
                   _integer(data["y"], "Y", 0, 4096),
                   _integer(data["width"], "Ширина", 16, 4096),
                   _integer(data["height"], "Высота", 2, 4096), _props(kind, data["props"]))


@dataclass
class Project:
    title: str = "Form1"
    width: int = 800
    height: int = 560
    theme: str = "dark"
    widgets: list[WidgetModel] = field(default_factory=list)
    colors: dict = field(default_factory=dict)

    def to_dict(self):
        return {"version": 1, "window": {"title": self.title, "width": self.width,
                "height": self.height, "theme": self.theme, "colors": deepcopy(self.colors)},
                "widgets": [widget.to_dict() for widget in self.widgets]}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) != {"version", "window", "widgets"}:
            raise ProjectError("Это не файл проекта Tkinter++.")
        if type(data["version"]) is not int or data["version"] != 1:
            raise ProjectError("Неподдерживаемая версия проекта.")
        window = data["window"]
        if not isinstance(window, dict) or not {"title", "width", "height", "theme"} <= set(window) or set(window) - {"title", "width", "height", "theme", "colors"}:
            raise ProjectError("Неверные параметры окна.")
        title = _string(window["title"], "Заголовок", 200)
        width = _integer(window["width"], "Ширина окна", 240, 4096)
        height = _integer(window["height"], "Высота окна", 200, 4096)
        theme = _choice(window["theme"], "Тема", ("light", "dark"))
        if not isinstance(data["widgets"], list) or len(data["widgets"]) > MAX_WIDGETS:
            raise ProjectError(f"В проекте может быть не более {MAX_WIDGETS} виджетов.")
        widgets = [WidgetModel.from_dict(item) for item in data["widgets"]]
        if len({item.id for item in widgets}) != len(widgets):
            raise ProjectError("Имена виджетов не должны повторяться.")
        for item in widgets:
            if item.x + item.width > width or item.y + item.height > height:
                raise ProjectError(f"Виджет {item.id} выходит за пределы окна.")
        try:
            colors = validate_colors(window.get("colors", {}))
        except ValueError as error:
            raise ProjectError(str(error)) from error
        return cls(title, width, height, theme, widgets, colors)

    def clone(self):
        return Project.from_dict(self.to_dict())

    def dumps(self):
        validated = Project.from_dict(self.to_dict())
        return json.dumps(validated.to_dict(), ensure_ascii=False, indent=2) + "\n"

    @classmethod
    def loads(cls, source):
        if len(source.encode("utf-8")) > MAX_FILE_BYTES:
            raise ProjectError("Файл проекта слишком большой (предел — 5 МиБ).")
        try:
            return cls.from_dict(json.loads(source))
        except (json.JSONDecodeError, RecursionError) as error:
            raise ProjectError("Не удалось прочитать JSON проекта.") from error

    @classmethod
    def load(cls, path):
        path = Path(path)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ProjectError("Файл проекта слишком большой (предел — 5 МиБ).")
        try:
            return cls.loads(path.read_text(encoding="utf-8-sig"))
        except UnicodeError as error:
            raise ProjectError("Файл проекта должен быть в UTF-8.") from error

    def save(self, path):
        # Validate before writing, and replace atomically to preserve previous saves.
        source = self.dumps()
        path = Path(path)
        temporary = path.with_name(path.name + ".tmp")
        try:
            temporary.write_text(source, encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def next_id(self, kind):
        base = kind.lower()
        existing = {item.id for item in self.widgets}
        index = 1
        while f"{base}_{index}" in existing:
            index += 1
        return f"{base}_{index}"

    def add(self, kind, x=32, y=32):
        if kind not in SPECS:
            raise ProjectError("Неизвестный тип виджета.")
        if len(self.widgets) >= MAX_WIDGETS:
            raise ProjectError(f"В проекте может быть не более {MAX_WIDGETS} виджетов.")
        spec = SPECS[kind]
        width, height = min(spec.width, self.width), min(spec.height, self.height)
        item = WidgetModel(self.next_id(kind), kind, max(0, min(x, self.width-width)),
                           max(0, min(y, self.height-height)), width, height, deepcopy(spec.defaults))
        self.widgets.append(item)
        if kind == "RadioButton":
            item.props["value"] = item.id
        return item


def create_widget(master, item):
    """Instantiate the same widget class and properties used by code export."""
    from . import widgets
    widget = getattr(widgets, item.kind)(master, **item.props)
    widget.place(x=item.x, y=item.y, width=item.width, height=item.height)
    return widget


def demo_project():
    p = Project(title="Параметры проекта", width=760, height=560)
    def add(kind, x, y, width, height, **props):
        item = p.add(kind, x, y)
        item.width, item.height = width, height
        item.props.update(props)
    add("Label", 40, 28, 660, 28, text="Параметры проекта", font_size=14, weight="bold")
    add("Label", 40, 70, 660, 36, text="Общие настройки", font_size=12, weight="bold")
    add("Label", 40, 126, 660, 30, text="Конфигурация приложения", muted=True)
    add("Separator", 40, 176, 680, 2)
    add("Label", 40, 200, 300, 28, text="Название проекта", weight="bold")
    add("Entry", 40, 236, 320, 42, value="Project1")
    add("Label", 400, 200, 300, 28, text="Рабочая среда", weight="bold")
    add("ComboBox", 400, 236, 320, 42, options=["Разработка", "Дизайн", "Личный проект"], value="Разработка")
    add("Switch", 40, 305, 300, 36, text="Получать уведомления", value=True)
    add("CheckBox", 400, 305, 300, 36, text="Сохранять настройки", value=True)
    add("Label", 40, 370, 300, 28, text="Прогресс", muted=True)
    add("ProgressBar", 40, 410, 680, 12, value=75)
    add("Button", 40, 470, 210, 44, text="Применить")
    add("Button", 270, 470, 160, 44, text="Отмена", variant="secondary")
    return p
