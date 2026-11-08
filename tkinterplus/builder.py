"""PyQt6 editor for Tkinter++ projects."""
from copy import deepcopy
from pathlib import Path
import os
import re
import sys

from PyQt6.QtCore import QProcess, QProcessEnvironment, QRectF, QSize, Qt
from PyQt6.QtGui import QAction, QActionGroup, QColor, QFont, QIcon, QKeySequence, QPainter, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDockWidget, QDoubleSpinBox, QFileDialog,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QStyle, QTabWidget, QToolBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from .codegen import generate_python
from .designer import Artboard, DesignItem, DesignScene, DesignView, PaletteList
from .project import MAX_WIDGETS, Project, ProjectError, SPECS, WidgetModel, demo_project
from .qt_theme import COLORS, apply_theme

PROPERTY_LABELS = {
    "text": "Текст", "value": "Значение", "options": "Варианты",
    "font_size": "Размер шрифта", "weight": "Начертание", "muted": "Приглушённый цвет",
    "anchor": "Выравнивание", "variant": "Оформление",
}


class PythonHighlighter(QSyntaxHighlighter):
    theme = "dark"

    def highlightBlock(self, text):
        rules = [
            (r"\b(?:import|from|as|def|return|if|else|True|False|None)\b", "#569cd6"),
            (r"\b\d+(?:\.\d+)?\b", "#b5cea8"),
            (r"\b(?:App|Button|Label|Entry|Frame|Textbox|CheckBox|Switch|ComboBox|Slider|ProgressBar|Separator)\b", "#4ec9b0"),
            (r"""'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*" """.strip(), "#ce9178"),
            (r"#.*$", "#6a9955"),
        ]
        for pattern, color in rules:
            if self.theme == "light":
                color = {"#569cd6": "#0000ff", "#b5cea8": "#098658", "#4ec9b0": "#267f99",
                         "#ce9178": "#a31515", "#6a9955": "#008000"}[color]
            formatting = QTextCharFormat()
            formatting.setForeground(QColor(color))
            for match in re.finditer(pattern, text):
                # QTextDocument uses UTF-16 positions, including non-BMP text.
                start = len(text[:match.start()].encode("utf-16-le"))//2
                length = len(match.group().encode("utf-16-le"))//2
                self.setFormat(start, length, formatting)


class Builder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setObjectName("TkinterPlusBuilder")
        self.setDockNestingEnabled(True)
        screen = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1440, screen.width()-40), min(920, screen.height()-60))
        self.setMinimumSize(1000, 650)
        self.project = Project()
        self.path = None
        self.selected_id = None
        self.history = []
        self.future = []
        self.saved = self.project.dumps()
        self.views = {}
        self.previews = []
        self.editor_theme = "dark"
        self._build_actions()
        self._build_ui()
        self.set_editor_theme("dark")
        self._refresh()
        self.default_layout = self.saveState()
        self.statusBar().showMessage("Готово")

    @property
    def selected(self):
        return next((item for item in self.project.widgets if item.id == self.selected_id), None)

    @property
    def dirty(self):
        return self.project.dumps() != self.saved

    def _action(self, text, callback, shortcut=None, icon=None):
        action = QAction(text, self)
        action.triggered.connect(lambda checked=False: callback())
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if icon is not None:
            action.setIcon(self.style().standardIcon(icon))
            if icon == QStyle.StandardPixmap.SP_MediaPlay:
                pixmap = action.icon().pixmap(16, 16)
                painter = QPainter(pixmap)
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
                painter.fillRect(pixmap.rect(), QColor("#6a9955"))
                painter.end()
                action.setIcon(QIcon(pixmap))
        return action

    def _build_actions(self):
        sp = QStyle.StandardPixmap
        self.new_action = self._action("Создать", self.new_project, "Ctrl+N", sp.SP_FileIcon)
        self.open_action = self._action("Открыть…", self.open_project, "Ctrl+O", sp.SP_DirOpenIcon)
        self.save_action = self._action("Сохранить", self.save_project, "Ctrl+S", sp.SP_DialogSaveButton)
        self.save_as_action = self._action("Сохранить как…", self.save_as, "Ctrl+Shift+S")
        self.export_action = self._action("Экспорт Python…", self.export_python, "Ctrl+E", sp.SP_FileDialogDetailedView)
        self.undo_action = self._action("Отменить", self.undo, "Ctrl+Z", sp.SP_ArrowBack)
        self.redo_action = self._action("Повторить", self.redo, "Ctrl+Y", sp.SP_ArrowForward)
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        self.duplicate_action = self._action("Дублировать", self.duplicate, "Ctrl+D")
        self.delete_action = self._action("Удалить", self.delete_selected, "Delete")
        self.preview_action = self._action("Предпросмотр", self.preview, "F5", sp.SP_MediaPlay)
        self.snap_action = QAction("Сетка 8 px", self, checkable=True, checked=True)
        self.snap_action.toggled.connect(lambda checked: self.scene.update())
        file_menu = self.menuBar().addMenu("Файл")
        file_menu.addActions([self.new_action, self.open_action, self.save_action, self.save_as_action])
        file_menu.addSeparator()
        file_menu.addAction(self.export_action)
        file_menu.addSeparator()
        file_menu.addAction(self._action("Выход", self.close, "Alt+F4"))
        edit = self.menuBar().addMenu("Правка")
        edit.addActions([self.undo_action, self.redo_action])
        edit.addSeparator()
        edit.addActions([self.duplicate_action, self.delete_action])
        edit.addAction(self._action("На слой выше", lambda: self.reorder(1)))
        edit.addAction(self._action("На слой ниже", lambda: self.reorder(-1)))
        self.view_menu = self.menuBar().addMenu("Вид")
        self.view_menu.addAction(self.snap_action)
        themes = self.view_menu.addMenu("Тема редактора")
        self.theme_group = QActionGroup(self)
        self.theme_actions = {}
        for key, label in [("dark", "Тёмная"), ("light", "Светлая")]:
            action = QAction(label, self, checkable=True)
            action.triggered.connect(lambda checked, name=key: self.set_editor_theme(name))
            self.theme_group.addAction(action)
            themes.addAction(action)
            self.theme_actions[key] = action
        self.view_menu.addSeparator()
        project_menu = self.menuBar().addMenu("Проект")
        project_menu.addAction(self._action("Параметры окна", lambda: self.select(None)))
        project_menu.addAction(self._action("Открыть пример", self.open_demo))
        project_menu.addSeparator()
        project_menu.addAction(self.preview_action)

    def _build_ui(self):
        toolbar = QToolBar("Стандартная", self)
        toolbar.setObjectName("standardToolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(toolbar)
        toolbar.addActions([self.new_action, self.open_action, self.save_action])
        toolbar.addSeparator()
        toolbar.addActions([self.undo_action, self.redo_action])
        toolbar.addSeparator()
        toolbar.addActions([self.preview_action, self.export_action])
        toolbar.addSeparator()
        toolbar.addAction(self.snap_action)
        self.document_label = QLabel("Без названия.json")
        toolbar.addWidget(self.document_label)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.view = DesignView(self)
        self.scene = DesignScene(self)
        self.view.setScene(self.scene)
        self.tabs.addTab(self.view, "Конструктор")
        code_page = QWidget()
        code_layout = QVBoxLayout(code_page)
        code_layout.setContentsMargins(0, 0, 0, 0)
        code_bar = QHBoxLayout()
        code_bar.addWidget(QLabel("  Python / Tkinter++"))
        code_bar.addStretch()
        copy = QPushButton("Копировать")
        copy.clicked.connect(self.copy_code)
        code_bar.addWidget(copy)
        code_layout.addLayout(code_bar)
        self.code = QPlainTextEdit()
        self.code.setObjectName("codeEditor")
        self.code.setReadOnly(True)
        self.code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code.setFont(QFont("Consolas", 10))
        self.highlighter = PythonHighlighter(self.code.document())
        code_layout.addWidget(self.code)
        self.tabs.addTab(code_page, "Код")
        self.setCentralWidget(self.tabs)

        toolbox = QWidget()
        layout = QVBoxLayout(toolbox)
        layout.setContentsMargins(5, 5, 5, 5)
        self.palette_search = QLineEdit()
        self.palette_search.setPlaceholderText("Поиск элементов")
        self.palette_search.textChanged.connect(self._filter_palette)
        layout.addWidget(self.palette_search)
        self.palette = PaletteList()
        self.palette.setDragEnabled(True)
        for kind, spec in SPECS.items():
            self.palette.addItem(f"{kind}  ·  {spec.label}")
            item = self.palette.item(self.palette.count()-1)
            item.setData(Qt.ItemDataRole.UserRole, kind)
            item.setToolTip("Двойной щелчок — добавить; перетаскивание — разместить")
        self.palette.itemDoubleClicked.connect(lambda item: self.add_widget(item.data(Qt.ItemDataRole.UserRole)))
        layout.addWidget(self.palette)
        self.toolbox_dock = self._dock("Панель элементов", "toolbox", toolbox, Qt.DockWidgetArea.LeftDockWidgetArea)

        outline = QWidget()
        outline_layout = QVBoxLayout(outline)
        outline_layout.setContentsMargins(0, 0, 0, 0)
        self.layers = QTreeWidget()
        self.layers.setHeaderLabels(["Имя", "Тип"])
        self.layers.setColumnWidth(0, 155)
        self.layers.currentItemChanged.connect(self._layer_select)
        outline_layout.addWidget(self.layers)
        row = QHBoxLayout()
        row.setContentsMargins(5, 0, 5, 5)
        for text, direction in [("Выше", 1), ("Ниже", -1)]:
            button = QPushButton(text)
            button.clicked.connect(lambda checked=False, d=direction: self.reorder(d))
            row.addWidget(button)
        outline_layout.addLayout(row)
        self.outline_dock = self._dock("Структура документа", "outline", outline, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.splitDockWidget(self.toolbox_dock, self.outline_dock, Qt.Orientation.Vertical)

        inspector = QWidget()
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(0, 0, 0, 0)
        self.object_label = QLabel("Окно приложения")
        self.object_label.setContentsMargins(8, 6, 8, 6)
        inspector_layout.addWidget(self.object_label)
        self.property_tree = QTreeWidget()
        self.property_tree.setHeaderLabels(["Свойство", "Значение"])
        self.property_tree.setIndentation(10)
        self.property_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.property_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        inspector_layout.addWidget(self.property_tree)
        self.apply_button = QPushButton("Применить")
        self.apply_button.clicked.connect(self.apply_properties)
        inspector_layout.addWidget(self.apply_button)
        self.inspector_dock = self._dock("Свойства", "properties", inspector, Qt.DockWidgetArea.RightDockWidgetArea)
        self.output = QPlainTextEdit()
        self.output.setObjectName("outputLog")
        self.output.setReadOnly(True)
        self.output.setMaximumBlockCount(300)
        self.output.setFont(QFont("Consolas", 9))
        self.output_dock = self._dock("Вывод", "output", self.output, Qt.DockWidgetArea.BottomDockWidgetArea)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.resizeDocks([self.toolbox_dock, self.inspector_dock], [255, 330], Qt.Orientation.Horizontal)
        self.resizeDocks([self.toolbox_dock, self.outline_dock], [380, 230], Qt.Orientation.Vertical)
        self.resizeDocks([self.output_dock], [110], Qt.Orientation.Vertical)
        self.view_menu.addAction(self._action("Восстановить расположение панелей", self.restore_layout))
        self.dimensions_label = QLabel()
        self.statusBar().addPermanentWidget(self.dimensions_label)

    def _dock(self, title, name, widget, area):
        dock = QDockWidget(title, self)
        dock.setObjectName(name)
        dock.setWidget(widget)
        self.addDockWidget(area, dock)
        self.view_menu.addAction(dock.toggleViewAction())
        return dock

    def restore_layout(self):
        self.restoreState(self.default_layout)

    def _filter_palette(self, text):
        for index in range(self.palette.count()):
            item = self.palette.item(index)
            item.setHidden(text.casefold() not in item.text().casefold())

    def snap(self, value):
        return round(value/8)*8 if self.snap_action.isChecked() else round(value)

    def set_editor_theme(self, name):
        self.editor_theme = name
        apply_theme(self, name)
        self.theme_actions[name].setChecked(True)
        self.view.setBackgroundBrush(QColor(COLORS[name]["window"]))
        self.highlighter.theme = name
        self.highlighter.rehighlight()
        self.scene.update()

    def _refresh(self, rebuild_scene=True):
        if rebuild_scene:
            self._render_scene()
        self._refresh_layers()
        self._render_inspector()
        self.code.setPlainText(generate_python(self.project))
        self._update_title()
        self.undo_action.setEnabled(bool(self.history))
        self.redo_action.setEnabled(bool(self.future))
        self.duplicate_action.setEnabled(self.selected is not None)
        self.delete_action.setEnabled(self.selected is not None)

    def _render_scene(self):
        self.scene.clear()
        self.views.clear()
        self.scene.setSceneRect(QRectF(-28, -28, self.project.width+56, self.project.height+56))
        self.scene.addItem(Artboard(self))
        for index, item in enumerate(self.project.widgets):
            view = DesignItem(self, item)
            view.setZValue(index)
            self.scene.addItem(view)
            view.setSelected(item.id == self.selected_id)
            self.views[item.id] = view

    def select(self, item_id):
        self.selected_id = item_id
        for name, item in self.views.items():
            item.setSelected(name == item_id)
        self.layers.blockSignals(True)
        self.layers.setCurrentItem(self.layer_items.get(item_id))
        self.layers.blockSignals(False)
        self._render_inspector()
        self.duplicate_action.setEnabled(self.selected is not None)
        self.delete_action.setEnabled(self.selected is not None)

    def _refresh_layers(self):
        self.layers.blockSignals(True)
        self.layers.clear()
        root = QTreeWidgetItem([self.project.title, "App"])
        self.layers.addTopLevelItem(root)
        root.setExpanded(True)
        self.layer_items = {None: root}
        selected = root
        for item in reversed(self.project.widgets):
            row = QTreeWidgetItem([item.id, item.kind])
            row.setData(0, Qt.ItemDataRole.UserRole, item.id)
            self.layer_items[item.id] = row
            root.addChild(row)
            if item.id == self.selected_id:
                selected = row
        self.layers.setCurrentItem(selected)
        self.layers.blockSignals(False)

    def _layer_select(self, current, previous):
        if current is not None:
            name = current.data(0, Qt.ItemDataRole.UserRole)
            if name != self.selected_id:
                self.select(name)

    def _render_inspector(self):
        self.property_tree.clear()
        self.fields = {}
        self.field_widgets = {}
        item = self.selected
        self.object_label.setText(f"{item.id} : {item.kind}" if item else f"{self.project.title} : App")
        common = self._property_group("Общие")
        if item:
            self._field(common, "id", "Имя", item.id)
            geometry = self._property_group("Расположение")
            for name, label in [("x", "X"), ("y", "Y"), ("width", "Ширина"), ("height", "Высота")]:
                self._field(geometry, name, label, getattr(item, name))
            content = self._property_group("Содержимое")
            for name, value in item.props.items():
                options = None
                if name == "weight":
                    options = ("normal", "bold")
                elif name == "anchor":
                    options = ("w", "center", "e")
                elif name == "variant":
                    options = ("primary", "secondary", "danger") if item.kind == "Button" else ("surface", "panel", "background")
                self._field(content, "prop:"+name, PROPERTY_LABELS[name], value, options,
                            multiline=name in ("text", "options") or (name == "value" and item.kind == "Textbox"))
        else:
            self._field(common, "title", "Заголовок", self.project.title)
            self._field(common, "theme", "Тема окна", self.project.theme, ("dark", "light"))
            geometry = self._property_group("Расположение")
            self._field(geometry, "width", "Ширина", self.project.width)
            self._field(geometry, "height", "Высота", self.project.height)
        self.property_tree.expandAll()

    def _property_group(self, label):
        item = QTreeWidgetItem([label])
        self.property_tree.addTopLevelItem(item)
        item.setFirstColumnSpanned(True)
        return item

    def _field(self, group, key, label, value, options=None, multiline=False):
        row = QTreeWidgetItem([label])
        group.addChild(row)
        if type(value) is bool:
            widget = QCheckBox()
            widget.setChecked(value)
            getter = widget.isChecked
        elif options:
            widget = QComboBox()
            widget.addItems(options)
            widget.setCurrentText(value)
            getter = widget.currentText
        elif multiline:
            widget = QPlainTextEdit("\n".join(value) if isinstance(value, list) else value)
            widget.setFixedHeight(65)
            widget.setTabChangesFocus(True)
            getter = widget.toPlainText
        elif type(value) in (int, float):
            if key.startswith("prop:") and key != "prop:font_size":
                widget = QDoubleSpinBox()
                widget.setRange(0, 100)
                widget.setDecimals(2)
            else:
                widget = QSpinBox()
                widget.setRange(0, 4096)
                if key == "prop:font_size":
                    widget.setRange(8, 72)
            widget.setValue(value)
            getter = widget.value
        else:
            widget = QLineEdit(str(value))
            widget.returnPressed.connect(self.apply_properties)
            getter = widget.text
        self.property_tree.setItemWidget(row, 1, widget)
        self.fields[key] = getter
        self.field_widgets[key] = widget

    def update_geometry_fields(self):
        if self.selected:
            for name in ("x", "y", "width", "height"):
                field = self.field_widgets.get(name)
                if isinstance(field, QSpinBox):
                    field.setValue(getattr(self.selected, name))

    def apply_properties(self):
        before = self.project.to_dict()
        try:
            data = self.project.to_dict()
            if self.selected:
                candidate = self.selected.to_dict()
                for key, getter in self.fields.items():
                    value = getter()
                    if key.startswith("prop:"):
                        name = key[5:]
                        original = candidate["props"][name]
                        if name == "options":
                            value = value.splitlines()
                        elif name == "font_size":
                            value = int(value)
                        elif type(original) is bool:
                            value = bool(value)
                        elif type(original) in (float, int):
                            value = float(value)
                        candidate["props"][name] = value
                    else:
                        candidate[key] = value.strip() if key == "id" else int(value)
                node = WidgetModel.from_dict(candidate)
                index = next(i for i, w in enumerate(self.project.widgets) if w.id == self.selected_id)
                data["widgets"][index] = node.to_dict()
                updated = Project.from_dict(data)
                self.project, self.selected_id = updated, node.id
            else:
                data["window"].update(title=self.fields["title"](), width=int(self.fields["width"]()),
                                      height=int(self.fields["height"]()), theme=self.fields["theme"]())
                self.project = Project.from_dict(data)
        except (ValueError, OverflowError) as error:
            self._error(error if isinstance(error, ProjectError) else "Проверьте числовые значения свойств.")
            return
        self._commit(before)
        self.statusBar().showMessage("Свойства применены")

    def add_widget(self, kind, x=32, y=32):
        before = self.project.to_dict()
        try:
            item = self.project.add(kind, x, y)
        except ProjectError as error:
            self._error(error)
            return
        self.selected_id = item.id
        self._commit(before)

    def _commit(self, before, rebuild_scene=True):
        if before != self.project.to_dict():
            self.history.append(before)
            self.history = self.history[-100:]
            self.future.clear()
        self._refresh(rebuild_scene)

    def undo(self):
        if not self.history:
            return
        self.future.append(self.project.to_dict())
        self.project = Project.from_dict(self.history.pop())
        self.selected_id = None
        self._refresh()

    def redo(self):
        if not self.future:
            return
        self.history.append(self.project.to_dict())
        self.project = Project.from_dict(self.future.pop())
        self.selected_id = None
        self._refresh()

    def duplicate(self):
        item = self.selected
        if item is None:
            return
        if len(self.project.widgets) >= MAX_WIDGETS:
            self._error(f"Предел — {MAX_WIDGETS} виджетов.")
            return
        before = self.project.to_dict()
        clone = deepcopy(item)
        clone.id = self.project.next_id(item.kind)
        clone.x = min(item.x+16, self.project.width-item.width)
        clone.y = min(item.y+16, self.project.height-item.height)
        self.project.widgets.append(clone)
        self.selected_id = clone.id
        self._commit(before)

    def delete_selected(self):
        if self.selected is None:
            return
        before = self.project.to_dict()
        self.project.widgets.remove(self.selected)
        self.selected_id = None
        self._commit(before)

    def nudge(self, dx, dy):
        if self.selected is None:
            return
        item = self.selected
        before = self.project.to_dict()
        step = 8 if self.snap_action.isChecked() else 1
        item.x = max(0, min(item.x+dx*step, self.project.width-item.width))
        item.y = max(0, min(item.y+dy*step, self.project.height-item.height))
        self._commit(before)

    def reorder(self, direction):
        if self.selected is None:
            return
        before = self.project.to_dict()
        index = self.project.widgets.index(self.selected)
        new_index = max(0, min(index+direction, len(self.project.widgets)-1))
        self.project.widgets.insert(new_index, self.project.widgets.pop(index))
        self._commit(before)

    def context_menu(self, position):
        menu = QMenu(self)
        menu.addActions([self.duplicate_action, self.delete_action])
        menu.addSeparator()
        menu.addAction("На слой выше", lambda: self.reorder(1))
        menu.addAction("На слой ниже", lambda: self.reorder(-1))
        menu.exec(position)

    def _update_title(self):
        name = self.path.name if self.path else "Без названия.json"
        self.setWindowTitle(f"{name}{' *' if self.dirty else ''} — Tkinter++")
        self.document_label.setText(f"  {name}")
        self.dimensions_label.setText(f"{self.project.width} × {self.project.height}   |   {len(self.project.widgets)} элементов   |   Tkinter")

    def _replace_project(self, project, path=None, saved=True):
        self.project = project
        self.path = Path(path) if path else None
        self.selected_id = None
        self.history.clear()
        self.future.clear()
        self.saved = project.dumps() if saved else ""
        self._refresh()
        self.view.horizontalScrollBar().setValue(self.view.horizontalScrollBar().minimum())
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().minimum())

    def _confirm_discard(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(self, "Несохранённые изменения", "Сохранить текущий проект?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if answer == QMessageBox.StandardButton.Cancel:
            return False
        return self.save_project() if answer == QMessageBox.StandardButton.Save else True

    def new_project(self):
        if self._confirm_discard():
            self._replace_project(Project())
            self.log("Создан проект")

    def open_demo(self):
        if self._confirm_discard():
            self._replace_project(demo_project(), saved=False)
            self.log("Открыт пример формы")

    def open_project(self):
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Открыть проект", "", "Проект Tkinter++ (*.json)")
        if not path:
            return
        try:
            project = Project.load(path)
        except (OSError, ProjectError) as error:
            self._error(error)
            return
        self._replace_project(project, path)
        self.log(f"Открыт: {path}")

    def save_project(self):
        return self.save_as() if self.path is None else self._save_to(self.path)

    def save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить проект", str(self.path or "project.json"), "Проект Tkinter++ (*.json)")
        if path and not Path(path).suffix:
            path += ".json"
        return self._save_to(Path(path)) if path else False

    def _save_to(self, path):
        path = Path(path)
        try:
            self.project.save(path)
        except (OSError, ProjectError) as error:
            self._error(error)
            return False
        self.path = path
        self.saved = self.project.dumps()
        self._update_title()
        self.log(f"Сохранено: {path}")
        return True

    def export_python(self):
        path, _ = QFileDialog.getSaveFileName(self, "Экспорт Python", "app.py", "Python (*.py)")
        if not path:
            return
        if not Path(path).suffix:
            path += ".py"
        try:
            Path(path).write_text(generate_python(self.project), encoding="utf-8")
        except (OSError, ProjectError) as error:
            self._error(error)
            return
        self.log(f"Экспорт: {path}")

    def show_code(self):
        self.tabs.setCurrentIndex(1)

    def copy_code(self):
        QApplication.clipboard().setText(generate_python(self.project))
        self.statusBar().showMessage("Код скопирован")

    def preview(self):
        process = QProcess(self)
        process.setProgram(sys.executable)
        process.setArguments(["-m", "tkinterplus.preview"])
        environment = QProcessEnvironment.systemEnvironment()
        package_root = str(Path(__file__).resolve().parent.parent)
        environment.insert("PYTHONPATH", package_root + os.pathsep + environment.value("PYTHONPATH", ""))
        process.setProcessEnvironment(environment)
        payload = self.project.dumps().encode("utf-8")
        def started():
            process.write(payload)
            process.closeWriteChannel()
            self.log("Предпросмотр запущен")
        process.started.connect(started)
        process.readyReadStandardError.connect(lambda: self.log(bytes(process.readAllStandardError()).decode("utf-8", errors="replace").strip()))
        process.errorOccurred.connect(lambda error: self._preview_error(process, error))
        process.finished.connect(lambda code, status: self._preview_finished(process, code))
        self.previews.append(process)
        process.start()
        return process

    def _preview_error(self, process, error):
        self.log(f"Предпросмотр: {process.errorString()}")
        if error == QProcess.ProcessError.FailedToStart:
            if process in self.previews:
                self.previews.remove(process)
            process.deleteLater()

    def _preview_finished(self, process, code):
        if process in self.previews:
            self.previews.remove(process)
        self.log(f"Предпросмотр завершён, код {code}")
        process.deleteLater()

    def log(self, message):
        if message:
            self.output.appendPlainText(message)
            self.statusBar().showMessage(message.splitlines()[-1])

    def _error(self, error):
        self.log(f"Ошибка: {error}")
        QMessageBox.critical(self, "Tkinter++", str(error))

    def closeEvent(self, event):
        if not self._confirm_discard():
            event.ignore()
            return
        for process in list(self.previews):
            process.terminate()
            if not process.waitForFinished(1000):
                process.kill()
                process.waitForFinished(1000)
        event.accept()


def main():
    application = QApplication.instance() or QApplication(sys.argv)
    application.setApplicationName("Tkinter++")
    application.setStyle("Fusion")
    window = Builder()
    window.show()
    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())
