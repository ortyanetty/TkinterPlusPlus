"""PyQt6 editor for Tkinter++ projects."""
from copy import deepcopy
from pathlib import Path
import os
import json
import re
import sys

from PyQt6.QtCore import QDir, QMimeData, QProcess, QProcessEnvironment, QSize, QTemporaryFile, Qt, QUrl
from PyQt6.QtGui import QAction, QActionGroup, QColor, QDesktopServices, QFont, QIcon, QKeySequence, QPainter, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDockWidget, QDoubleSpinBox, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
    QPlainTextEdit, QPushButton, QSpinBox, QStyle, QTabWidget, QToolBar,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from .codegen import generate_python
from .designer import DesignView, PaletteList
from .project import MAX_WIDGETS, Project, ProjectError, SPECS, WidgetModel, demo_project
from .qt_theme import COLORS, apply_theme
from . import __version__
from .color_field import ColorField
from .theme import COLOR_NAMES, palette

PROPERTY_LABELS = {
    "text": "Текст", "value": "Значение", "options": "Варианты",
    "font_size": "Размер шрифта", "weight": "Начертание", "muted": "Приглушённый цвет",
    "anchor": "Выравнивание", "variant": "Оформление",
    "state": "Состояние", "show": "Символ пароля", "radius": "Скругление",
    "from_": "Минимум", "to": "Максимум", "increment": "Шаг", "selected": "Выбрана", "group": "Группа выбора",
}
COLOR_LABELS = {"background": "Фон", "surface": "Поверхность / ввод", "panel": "Панель / дорожка",
                "text": "Текст", "muted": "Приглушённый текст", "border": "Граница",
                "accent": "Акцент", "hover": "Наведение", "danger": "Опасное действие", "selection": "Выделение / нажатие",
                "on_accent": "Текст на акценте", "thumb": "Бегунок переключателя"}
CLIPBOARD_MIME = "application/x-tkinterplus-selection"


class PythonHighlighter(QSyntaxHighlighter):
    theme = "dark"

    def highlightBlock(self, text):
        rules = [
            (r"\b(?:import|from|as|def|return|if|else|True|False|None)\b", "#569cd6"),
            (r"\b\d+(?:\.\d+)?\b", "#b5cea8"),
            (r"\b(?:Tk|App|Button|Label|Entry|Frame|Text|Textbox|Checkbutton|CheckBox|Switch|Combobox|ComboBox|Scale|Slider|Progressbar|ProgressBar|Separator|Radiobutton|RadioButton|Spinbox|SpinBox)\b", "#4ec9b0"),
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
        self.selected_ids = set()
        self.history = []
        self.future = []
        self.saved = self.project.dumps()
        self.views = {}
        self.previews = []
        self.editor_theme = "dark"
        self.editor_colors = {}
        self.color_modes = {}
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
    def selected_items(self):
        return [item for item in self.project.widgets if item.id in self.selected_ids]

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
        self.copy_action = self._action("Копировать элементы", self.copy_widgets, "Ctrl+C")
        self.cut_action = self._action("Вырезать элементы", self.cut_widgets, "Ctrl+X")
        self.paste_action = self._action("Вставить элементы", self.paste_widgets, "Ctrl+V")
        self.select_all_action = self._action("Выделить всё", self.select_all, "Ctrl+A")
        self.preview_action = self._action("Предпросмотр", self.preview, "F5", sp.SP_MediaPlay)
        self.test_action = QAction("Проверка", self, checkable=True)
        self.test_action.setShortcut(QKeySequence("F6"))
        self.test_action.toggled.connect(lambda enabled: self.view.set_testing(enabled))
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
        edit.addActions([self.copy_action, self.cut_action, self.paste_action, self.duplicate_action, self.delete_action, self.select_all_action])
        edit.addAction(self._action("На слой выше", lambda: self.reorder(1)))
        edit.addAction(self._action("На слой ниже", lambda: self.reorder(-1)))
        self.view_menu = self.menuBar().addMenu("Вид")
        self.view_menu.addAction(self.snap_action)
        self.view_menu.addAction(self._action("Масштаб 100%", lambda: self.view.zoom_to(1)))
        self.view_menu.addAction(self._action("Вписать окно", lambda: self.view.fit_artboard()))
        self.view_menu.addAction(self._action("Цвета редактора…", self.edit_editor_colors))
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
        project_menu.addAction(self.test_action)
        help_menu = self.menuBar().addMenu("Справка")
        help_menu.addAction(self._action("Руководство по библиотеке", lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/ortyanetty/TkinterPlusPlus/blob/main/docs/library-guide.md"))))
        help_menu.addAction(self._action("О программе", self.about))
        layout_menu = QMenu("Макет", self)
        self.menuBar().insertMenu(self.view_menu.menuAction(), layout_menu)
        self.layout_actions = []
        for key, label in [("left", "По левому краю"), ("hcenter", "По центру горизонтально"),
                           ("right", "По правому краю"), ("top", "По верхнему краю"),
                           ("vcenter", "По центру вертикально"), ("bottom", "По нижнему краю"),
                           ("width", "Одинаковая ширина"), ("height", "Одинаковая высота"),
                           ("horizontal", "Распределить по горизонтали"), ("vertical", "Распределить по вертикали")]:
            action = self._action(label, lambda operation=key: self.arrange(operation))
            layout_menu.addAction(action)
            self.layout_actions.append(action)

    def about(self):
        QMessageBox.about(self, "О программе", (
            f"<b>Tkinter++ {__version__}</b><br>"
            "Copyright (C) 2026 ortyanetty.<br>"
            "Лицензия: GNU GPL версии 3.<br>"
            "Программа предоставляется без гарантий.<br><br>"
            '<a href="https://github.com/ortyanetty/TkinterPlusPlus">Исходный код и инструкции сборки</a><br>'
            '<a href="https://github.com/ortyanetty/TkinterPlusPlus/blob/main/LICENSE">Полный текст GPLv3</a><br>'
            '<a href="https://github.com/ortyanetty/TkinterPlusPlus/blob/main/THIRD_PARTY_NOTICES.md">Лицензии компонентов</a>'
        ))

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
        toolbar.addActions([self.test_action, self.preview_action, self.export_action])
        toolbar.addSeparator()
        toolbar.addAction(self.snap_action)
        self.document_label = QLabel("Без названия.tpp")
        toolbar.addWidget(self.document_label)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.view = DesignView(self)
        self.scene = self.view
        for action in [self.copy_action, self.cut_action, self.paste_action, self.select_all_action]:
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.view.addAction(action)
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
        self.layers.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.layers.itemSelectionChanged.connect(self._layer_select)
        for action in [self.copy_action, self.cut_action, self.paste_action, self.select_all_action]:
            self.layers.addAction(action)
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
        self.property_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.property_tree.setColumnWidth(0, 135)
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
        self.resizeDocks([self.toolbox_dock, self.inspector_dock], [255, 420], Qt.Orientation.Horizontal)
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
        apply_theme(self, name, self.editor_colors)
        self.theme_actions[name].setChecked(True)
        self.view.setBackgroundBrush(QColor(self.editor_colors.get("window", COLORS[name]["window"])))
        self.highlighter.theme = name
        self.highlighter.rehighlight()
        self.scene.update()

    def edit_editor_colors(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Цвета редактора")
        form = QFormLayout(dialog)
        fields = {}
        for key, value in COLORS[self.editor_theme].items():
            field = ColorField(self.editor_colors.get(key), value)
            fields[key] = field
            form.addRow({"window": "Рабочая область", "input": "Поля ввода"}.get(key, COLOR_LABELS.get(key, key)), field)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        def accept():
            try:
                values = {key: field.value() for key, field in fields.items()}
            except ValueError as error:
                QMessageBox.warning(dialog, "Цвет", str(error))
                return
            self.editor_colors = {key: value for key, value in values.items() if value}
            self.set_editor_theme(self.editor_theme)
            dialog.accept()
        buttons.accepted.connect(accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        dialog.exec()

    def _refresh(self, rebuild_scene=True):
        if rebuild_scene:
            self._render_scene()
        self._refresh_layers()
        self._render_inspector()
        self.code.setPlainText(generate_python(self.project))
        self._update_title()
        self.undo_action.setEnabled(bool(self.history))
        self.redo_action.setEnabled(bool(self.future))
        self._selection_actions()

    def _render_scene(self):
        self.selected_ids.intersection_update(item.id for item in self.project.widgets)
        if self.selected_id not in self.selected_ids:
            self.selected_id = next((item.id for item in self.project.widgets if item.id in self.selected_ids), None)
        self.view.render(self.project)
        self.views = self.view.handles

    def select(self, item_id, additive=False, toggle=False):
        ids = set(self.selected_ids) if additive else set()
        if item_id is not None:
            if toggle and item_id in ids:
                ids.remove(item_id)
            else:
                ids.add(item_id)
        self.set_selection(ids, item_id)

    def set_selection(self, ids, active=None):
        self.selected_ids = set(ids) & {item.id for item in self.project.widgets}
        self.selected_id = active if active in self.selected_ids else next(
            (item.id for item in self.project.widgets if item.id in self.selected_ids), None)
        self.view.refresh_selection()
        self.layers.blockSignals(True)
        self.layers.clearSelection()
        for name in self.selected_ids:
            if name in self.layer_items:
                self.layer_items[name].setSelected(True)
        self.layers.blockSignals(False)
        self._render_inspector()
        self._selection_actions()

    def _selection_actions(self):
        for action in [self.duplicate_action, self.delete_action, self.copy_action, self.cut_action]:
            action.setEnabled(bool(self.selected_ids))
        for action in self.layout_actions:
            action.setEnabled(len(self.selected_ids) >= 2)

    def select_all(self):
        self.set_selection({item.id for item in self.project.widgets})

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
        self.layers.clearSelection()
        for name in self.selected_ids:
            self.layer_items[name].setSelected(True)
        self.layers.blockSignals(False)

    def _layer_select(self):
        ids = {item.data(0, Qt.ItemDataRole.UserRole) for item in self.layers.selectedItems()}
        current = self.layers.currentItem()
        self.set_selection(ids - {None}, current.data(0, Qt.ItemDataRole.UserRole) if current else None)

    def _render_inspector(self):
        self.property_tree.clear()
        self.fields = {}
        self.field_widgets = {}
        item = self.selected
        self.object_label.setText(f"{item.id} : {item.kind}" if item else f"{self.project.title} : App")
        if len(self.selected_ids) > 1:
            self.object_label.setText(f"Выделено: {len(self.selected_ids)} · Свойства: {item.id}")
        common = self._property_group("Общие")
        if item:
            self._field(common, "id", "Имя", item.id)
            geometry = self._property_group("Расположение")
            for name, label in [("x", "X"), ("y", "Y"), ("width", "Ширина"), ("height", "Высота")]:
                self._field(geometry, name, label, getattr(item, name))
            content = self._property_group("Содержимое")
            for name, value in item.props.items():
                if name == "colors":
                    continue
                options = None
                if name == "weight":
                    options = ("normal", "bold")
                elif name == "anchor":
                    options = ("w", "center", "e")
                elif name == "variant":
                    options = ("primary", "secondary", "danger") if item.kind == "Button" else ("surface", "panel", "background")
                elif name == "state":
                    options = ("normal", "disabled", "readonly") if item.kind in ("Entry", "ComboBox", "SpinBox") else ("normal", "disabled")
                self._field(content, "prop:"+name, PROPERTY_LABELS[name], value, options,
                            multiline=name in ("text", "options") or (name == "value" and item.kind == "Textbox"))
        else:
            self._field(common, "title", "Заголовок", self.project.title)
            self._field(common, "theme", "Тема окна", self.project.theme, ("dark", "light"))
            geometry = self._property_group("Расположение")
            self._field(geometry, "width", "Ширина", self.project.width)
            self._field(geometry, "height", "Высота", self.project.height)
        colors = self._property_group("Цвета · пустое поле = тема")
        overrides = item.props["colors"] if item else self.project.colors
        inherited = palette(self.project.theme, self.project.colors) if item else palette(self.project.theme)
        for name in COLOR_NAMES:
            row = QTreeWidgetItem([COLOR_LABELS[name]])
            row.setToolTip(0, COLOR_LABELS[name])
            colors.addChild(row)
            field = ColorField(overrides.get(name), getattr(inherited, name))
            field.mode.setCurrentText(self.color_modes.get(name, "HEX"))
            field.mode.currentTextChanged.connect(lambda mode, role=name: self.color_modes.update({role: mode}))
            self.property_tree.setItemWidget(row, 1, field)
            self.fields["color:"+name] = field.value
            self.field_widgets["color:"+name] = field
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
            if key.startswith("prop:") and key not in ("prop:font_size", "prop:radius"):
                widget = QDoubleSpinBox()
                widget.setRange(-1000000, 1000000) if self.selected and self.selected.kind == "SpinBox" else widget.setRange(0, 100)
                widget.setDecimals(2)
            else:
                widget = QSpinBox()
                widget.setRange(0, 4096)
                if key == "prop:font_size":
                    widget.setRange(8, 72)
                elif key == "prop:radius":
                    widget.setRange(0, 30)
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
            try:
                colors = {key[6:]: getter() for key, getter in self.fields.items() if key.startswith("color:")}
            except ValueError as error:
                raise ProjectError(str(error)) from error
            colors = {key: value for key, value in colors.items() if value is not None}
            if self.selected:
                candidate = self.selected.to_dict()
                for key, getter in self.fields.items():
                    if key.startswith("color:"):
                        continue
                    value = getter()
                    if key.startswith("prop:"):
                        name = key[5:]
                        original = candidate["props"][name]
                        if name == "options":
                            value = value.splitlines()
                        elif name in ("font_size", "radius"):
                            value = int(value)
                        elif type(original) is bool:
                            value = bool(value)
                        elif type(original) in (float, int):
                            value = float(value)
                        candidate["props"][name] = value
                    else:
                        candidate[key] = value.strip() if key == "id" else int(value)
                candidate["props"]["colors"] = colors
                node = WidgetModel.from_dict(candidate)
                index = next(i for i, w in enumerate(self.project.widgets) if w.id == self.selected_id)
                data["widgets"][index] = node.to_dict()
                if node.kind == "RadioButton" and node.props["selected"]:
                    for other in data["widgets"]:
                        if other["id"] != node.id and other["kind"] == "RadioButton" and other["props"]["group"] == node.props["group"]:
                            other["props"]["selected"] = False
                updated = Project.from_dict(data)
                self.selected_ids.discard(self.selected_id)
                self.project, self.selected_id = updated, node.id
                self.selected_ids.add(node.id)
            else:
                data["window"].update(title=self.fields["title"](), width=int(self.fields["width"]()),
                                      height=int(self.fields["height"]()), theme=self.fields["theme"](), colors=colors)
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
        self.selected_ids = {item.id}
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
        self.selected_ids.clear()
        self._refresh()

    def redo(self):
        if not self.future:
            return
        self.history.append(self.project.to_dict())
        self.project = Project.from_dict(self.future.pop())
        self.selected_id = None
        self.selected_ids.clear()
        self._refresh()

    def copy_widgets(self):
        if not self.selected_items:
            return
        source = json.dumps({"format": "tkinterplus.widgets", "widgets": [item.to_dict() for item in self.selected_items]}, ensure_ascii=False)
        mime = QMimeData()
        mime.setData(CLIPBOARD_MIME, source.encode("utf-8"))
        mime.setText(source)
        QApplication.clipboard().setMimeData(mime)
        self.statusBar().showMessage(f"Скопировано: {len(self.selected_ids)}")

    def cut_widgets(self):
        self.copy_widgets()
        self.delete_selected()

    def paste_widgets(self):
        mime = QApplication.clipboard().mimeData()
        if mime is None or not mime.hasFormat(CLIPBOARD_MIME):
            self.statusBar().showMessage("В буфере нет элементов Tkinter++")
            return
        try:
            raw = bytes(mime.data(CLIPBOARD_MIME))
            if len(raw) > 5*1024*1024:
                raise ProjectError("Буфер элементов слишком большой.")
            data = json.loads(raw)
            if data.get("format") != "tkinterplus.widgets" or not isinstance(data.get("widgets"), list):
                raise ProjectError("Неверный формат буфера элементов.")
            self._insert_copies([WidgetModel.from_dict(item) for item in data["widgets"]])
        except (ValueError, TypeError, AttributeError, RecursionError) as error:
            self._error(error)

    def duplicate(self):
        self._insert_copies(self.selected_items)

    def _insert_copies(self, items):
        if not items:
            return
        if len(self.project.widgets)+len(items) > MAX_WIDGETS:
            self._error(f"Предел — {MAX_WIDGETS} виджетов.")
            return
        left, top = min(item.x for item in items), min(item.y for item in items)
        right, bottom = max(item.x+item.width for item in items), max(item.y+item.height for item in items)
        if right-left > self.project.width or bottom-top > self.project.height:
            self._error("Группа элементов не помещается в окно.")
            return
        dx = min(left+16, self.project.width-(right-left))-left
        dy = min(top+16, self.project.height-(bottom-top))-top
        before = self.project.to_dict()
        candidate = self.project.clone()
        ids = set()
        for item in items:
            clone = deepcopy(item)
            clone.id = candidate.next_id(item.kind)
            if clone.kind == "RadioButton":
                if clone.props["value"] == item.id:
                    clone.props["value"] = clone.id
                clone.props["selected"] = False
            clone.x, clone.y = item.x+dx, item.y+dy
            candidate.widgets.append(clone)
            ids.add(clone.id)
        self.project = Project.from_dict(candidate.to_dict())
        self.selected_ids = ids
        self.selected_id = candidate.widgets[-1].id
        self._commit(before)

    def delete_selected(self):
        if not self.selected_ids:
            return
        before = self.project.to_dict()
        self.project.widgets = [item for item in self.project.widgets if item.id not in self.selected_ids]
        self.selected_id = None
        self.selected_ids.clear()
        self._commit(before)

    def nudge(self, dx, dy):
        items = self.selected_items
        if not items:
            return
        before = self.project.to_dict()
        step = 8 if self.snap_action.isChecked() else 1
        self.move_selection(dx*step, dy*step)
        self._commit(before)

    def move_selection(self, dx, dy, originals=None):
        items = self.selected_items
        if not items:
            return
        originals = originals or {item.id: item.to_dict() for item in items}
        left = min(originals[item.id]["x"] for item in items)
        top = min(originals[item.id]["y"] for item in items)
        right = max(originals[item.id]["x"]+item.width for item in items)
        bottom = max(originals[item.id]["y"]+item.height for item in items)
        dx = max(-left, min(round(dx), self.project.width-right))
        dy = max(-top, min(round(dy), self.project.height-bottom))
        for item in items:
            item.x, item.y = originals[item.id]["x"]+dx, originals[item.id]["y"]+dy
            self.views[item.id].setPos(item.x, item.y)
            self.views[item.id].update()
        self.update_geometry_fields()

    def arrange(self, operation):
        items = self.selected_items
        if len(items) < 2:
            return
        before = self.project.to_dict()
        reference = self.selected or items[0]
        left, top = min(item.x for item in items), min(item.y for item in items)
        right, bottom = max(item.x+item.width for item in items), max(item.y+item.height for item in items)
        if operation in ("horizontal", "vertical"):
            if len(items) < 3:
                self.statusBar().showMessage("Для распределения выделите минимум три элемента")
                return
            horizontal = operation == "horizontal"
            ordered = sorted(items, key=lambda item: item.x if horizontal else item.y)
            span = right-left if horizontal else bottom-top
            occupied = sum(item.width if horizontal else item.height for item in ordered)
            gap = (span-occupied)/(len(items)-1)
            if gap < 0:
                self.statusBar().showMessage("Увеличьте расстояние между крайними элементами")
                return
            position = left if horizontal else top
            for item in ordered:
                setattr(item, "x" if horizontal else "y", round(position))
                position += (item.width if horizontal else item.height)+gap
        else:
            # All dimensions are derived before modifying the active reference.
            width, height = reference.width, reference.height
            if (operation == "width" and any(item.x+width > self.project.width for item in items)) or (
                    operation == "height" and any(item.y+height > self.project.height for item in items)):
                self._error("Размер активного элемента не помещается в текущих позициях группы.")
                return
            for item in items:
                if operation == "left": item.x = left
                elif operation == "right": item.x = right-item.width
                elif operation == "top": item.y = top
                elif operation == "bottom": item.y = bottom-item.height
                elif operation == "hcenter": item.x = round((left+right-item.width)/2)
                elif operation == "vcenter": item.y = round((top+bottom-item.height)/2)
                elif operation == "width": item.width = min(width, self.project.width-item.x)
                elif operation == "height": item.height = min(height, self.project.height-item.y)
                else: return
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
        menu.addActions([self.copy_action, self.cut_action, self.paste_action, self.duplicate_action, self.delete_action])
        menu.addSeparator()
        menu.addAction("На слой выше", lambda: self.reorder(1))
        menu.addAction("На слой ниже", lambda: self.reorder(-1))
        menu.exec(position)

    def _update_title(self):
        name = self.path.name if self.path else "Без названия.tpp"
        self.setWindowTitle(f"{name}{' *' if self.dirty else ''} — Tkinter++")
        self.document_label.setText(f"  {name}")
        self.dimensions_label.setText(f"{self.project.width} × {self.project.height}   |   {len(self.project.widgets)} элементов   |   Tkinter")

    def _replace_project(self, project, path=None, saved=True):
        self.project = project
        self.selected_ids.clear()
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
        path, _ = QFileDialog.getOpenFileName(self, "Открыть проект", "", "Проект Tkinter++ (*.tpp *.json)")
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
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить проект", str(self.path or "project.tpp"), "Проект Tkinter++ (*.tpp)")
        if path and not Path(path).suffix:
            path += ".tpp"
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
        project_file = QTemporaryFile(QDir.tempPath() + "/tkinterplus-preview-XXXXXX.json", process)
        payload = self.project.dumps().encode("utf-8")
        if not project_file.open() or project_file.write(payload) != len(payload) or not project_file.flush():
            self._error(f"Не удалось подготовить предпросмотр: {project_file.errorString()}")
            project_file.remove()
            process.deleteLater()
            return None
        project_path = project_file.fileName()
        project_file.close()
        process.project_file = project_file
        process.setProgram(sys.executable)
        if getattr(sys, "frozen", False):
            process.setArguments(["--preview", project_path])
        else:
            process.setArguments(["-m", "tkinterplus.preview", project_path])
        environment = QProcessEnvironment.systemEnvironment()
        package_root = str(Path(__file__).resolve().parent.parent)
        environment.insert("PYTHONPATH", package_root + os.pathsep + environment.value("PYTHONPATH", ""))
        process.setProcessEnvironment(environment)
        def started():
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
            process.project_file.remove()
            if process in self.previews:
                self.previews.remove(process)
            process.deleteLater()

    def _preview_finished(self, process, code):
        process.project_file.remove()
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
        self.view.shutdown()
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
