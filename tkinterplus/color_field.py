"""Color property editor with explicit HEX / RGB representation."""
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QColorDialog, QComboBox, QHBoxLayout, QLineEdit, QPushButton, QWidget
from .theme import normalize_color


class ColorField(QWidget):
    def __init__(self, value=None, inherited="#ffffff", parent=None):
        super().__init__(parent)
        self.inherited = inherited
        self._mode = "HEX"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        self.mode = QComboBox()
        self.mode.addItems(["HEX", "RGB"])
        self.mode.setFixedWidth(65)
        self.edit = QLineEdit(value or "")
        self.edit.setMinimumWidth(65)
        self.swatch = QPushButton()
        self.swatch.setFixedWidth(25)
        self.swatch.setToolTip("Выбрать цвет")
        self.reset = QPushButton("↺")
        self.reset.setFixedWidth(25)
        self.reset.setStyleSheet("QPushButton { padding: 0; }")
        self.reset.setToolTip("Сбросить: наследовать цвет темы")
        layout.addWidget(self.mode)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.swatch)
        layout.addWidget(self.reset)
        self.mode.currentTextChanged.connect(self._change_mode)
        self.edit.textChanged.connect(self._update_swatch)
        self.swatch.clicked.connect(self.choose)
        self.reset.clicked.connect(self.edit.clear)
        self._update_swatch()

    def value(self):
        value = self.edit.text().strip()
        if not value:
            return None
        if self._mode == "HEX":
            return normalize_color(value)
        try:
            return normalize_color(tuple(int(channel.strip()) for channel in value.split(",")))
        except ValueError as error:
            raise ValueError("RGB: введите три целых числа от 0 до 255 через запятую.") from error

    def set_value(self, value):
        if not value:
            self.edit.clear()
        elif self._mode == "RGB":
            value = normalize_color(value)
            self.edit.setText(", ".join(str(int(value[i:i+2], 16)) for i in (1, 3, 5)))
        else:
            self.edit.setText(normalize_color(value))

    def _change_mode(self, mode):
        try:
            value = self.value()
        except ValueError:
            self.mode.blockSignals(True)
            self.mode.setCurrentText(self._mode)
            self.mode.blockSignals(False)
            self.edit.setFocus()
            return
        self._mode = mode
        self.set_value(value)
        self._update_swatch()

    def _update_swatch(self):
        self.edit.setPlaceholderText("#RRGGBB" if self._mode == "HEX" else "R, G, B")
        self.edit.setToolTip("Пустое поле — наследовать цвет темы. " +
                             ("HEX: #RRGGBB" if self._mode == "HEX" else "RGB: 0–255, 0–255, 0–255"))
        try:
            value = self.value() or self.inherited
            self.swatch.setStyleSheet(f"QPushButton {{ background: {value}; padding: 0; border: 1px solid #808080; }}")
        except ValueError:
            self.swatch.setStyleSheet("QPushButton { border: 2px solid #d63f51; padding: 0; }")

    def choose(self):
        try:
            initial = self.value() or self.inherited
        except ValueError:
            initial = self.inherited
        color = QColorDialog.getColor(QColor(initial), self, "Цвет", QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if color.isValid():
            self.set_value(color.name())
