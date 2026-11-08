"""Compact, neutral IDE styling for the PyQt editor."""
from PyQt6.QtGui import QColor, QPalette

COLORS = {
    "dark": {"window": "#1e1e1e", "panel": "#252526", "input": "#333337",
             "border": "#3f3f46", "text": "#d4d4d4", "muted": "#969696",
             "accent": "#007acc", "selection": "#094771", "hover": "#37373d", "on_accent": "#ffffff"},
    "light": {"window": "#f5f5f5", "panel": "#eeeeF2", "input": "#ffffff",
              "border": "#ccccd1", "text": "#202020", "muted": "#666666",
              "accent": "#007acc", "selection": "#cce8ff", "hover": "#e0e0e5", "on_accent": "#ffffff"},
}


def apply_theme(window, name, overrides=None):
    c = {**COLORS[name], **(overrides or {})}
    palette = QPalette()
    for role, value in {
        QPalette.ColorRole.Window: c["window"], QPalette.ColorRole.WindowText: c["text"],
        QPalette.ColorRole.Base: c["input"], QPalette.ColorRole.AlternateBase: c["panel"],
        QPalette.ColorRole.Text: c["text"], QPalette.ColorRole.Button: c["panel"],
        QPalette.ColorRole.ButtonText: c["text"], QPalette.ColorRole.Highlight: c["selection"],
        QPalette.ColorRole.HighlightedText: c["text"], QPalette.ColorRole.ToolTipBase: c["panel"],
        QPalette.ColorRole.ToolTipText: c["text"], QPalette.ColorRole.PlaceholderText: c["muted"],
    }.items():
        palette.setColor(role, QColor(value))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c["muted"]))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(c["muted"]))
    window.setPalette(palette)
    window.setStyleSheet("""
        QMainWindow, QDialog { background: %(window)s; color: %(text)s; }
        QWidget { font-family: 'Segoe UI'; font-size: 12px; }
        QLabel { color: %(text)s; background: transparent; }
        QMenuBar, QToolBar, QDockWidget, QTabWidget::pane { background: %(panel)s; color: %(text)s; }
        QMenuBar { padding: 2px; border-bottom: 1px solid %(border)s; }
        QMenuBar::item { padding: 4px 10px; }
        QMenuBar::item:selected, QMenu::item:selected { background: %(selection)s; }
        QMenu { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; }
        QMenu::item { padding: 5px 28px 5px 20px; }
        QToolBar { border: 0; border-bottom: 1px solid %(border)s; spacing: 4px; padding: 3px; }
        QToolButton { border: 1px solid transparent; padding: 3px 6px; color: %(text)s; }
        QToolButton:hover { background: %(hover)s; border-color: %(border)s; }
        QToolButton:checked { background: %(selection)s; }
        QToolButton:disabled { color: %(muted)s; }
        QToolBar::separator { background: %(border)s; width: 1px; margin: 4px; }
        QDockWidget { font-weight: 600; }
        QDockWidget::title { text-align: left; padding: 5px 8px; background: %(panel)s; border-bottom: 1px solid %(border)s; }
        QMainWindow::separator { background: %(border)s; width: 3px; height: 3px; }
        QListWidget, QTreeWidget, QPlainTextEdit, QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background: %(input)s; color: %(text)s; border: 1px solid %(border)s; selection-background-color: %(selection)s;
        }
        QListWidget, QTreeWidget { background: %(panel)s; outline: none; }
        QListWidget::item { padding: 4px 6px; min-height: 18px; }
        QTreeWidget::item { min-height: 23px; }
        QListWidget::item:selected, QTreeWidget::item:selected { background: %(selection)s; color: %(text)s; }
        QHeaderView::section { background: %(panel)s; color: %(text)s; padding: 4px 6px; border: 0; border-bottom: 1px solid %(border)s; }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { padding: 3px 5px; min-height: 19px; }
        QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border-color: %(accent)s; }
        QComboBox QAbstractItemView { background: %(input)s; color: %(text)s; selection-background-color: %(selection)s; }
        QPushButton { background: %(input)s; color: %(text)s; border: 1px solid %(border)s; padding: 5px 14px; min-height: 20px; }
        QPushButton:hover { border-color: %(accent)s; background: %(hover)s; }
        QPushButton:pressed { background: %(selection)s; }
        QTabWidget::pane { border: 1px solid %(border)s; }
        QTabBar::tab { background: %(panel)s; color: %(muted)s; border: 1px solid %(border)s; padding: 6px 18px; }
        QTabBar::tab:selected { background: %(window)s; color: %(text)s; border-top: 2px solid %(accent)s; }
        QStatusBar { background: %(accent)s; color: %(on_accent)s; }
        QStatusBar QLabel { color: %(on_accent)s; padding: 0 5px; }
        QCheckBox { color: %(text)s; spacing: 6px; }
        QScrollBar:vertical { background: %(panel)s; width: 11px; margin: 0; }
        QScrollBar:horizontal { background: %(panel)s; height: 11px; margin: 0; }
        QScrollBar::handle { background: %(border)s; min-width: 20px; min-height: 20px; }
        QScrollBar::handle:hover { background: %(muted)s; }
        QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
        QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
        QToolTip { background: %(panel)s; color: %(text)s; border: 1px solid %(border)s; }
        QPlainTextEdit#codeEditor { font-family: Consolas, monospace; font-size: 13px; }
        QPlainTextEdit#outputLog { font-family: Consolas, monospace; font-size: 12px; }
    """ % c)
