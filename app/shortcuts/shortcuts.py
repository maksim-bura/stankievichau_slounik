from PySide6.QtWidgets import QApplication, QTextEdit
from PySide6.QtGui import QShortcut, QKeySequence


def install_global_copy(parent):
    shortcut = QShortcut(QKeySequence.Copy, parent)
    shortcut.activated.connect(_copy_selection)


def _copy_selection():
    for widget in QApplication.allWidgets():
        if isinstance(widget, QTextEdit) and widget.textCursor().hasSelection():
            widget.copy()
            return
