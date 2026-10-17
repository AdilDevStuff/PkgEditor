"""
Qt Compatibility Layer for PyQt5, PyQt6, and PySide6.
Ensures seamless cross-platform execution on Windows, Linux, and macOS.
"""
import sys

QT_API = None

try:
    from PyQt5 import QtCore, QtGui, QtWidgets
    from PyQt5.QtCore import Qt, QThread, pyqtSignal as Signal, pyqtSlot as Slot, QSize, QRect, QPoint
    from PyQt5.QtWidgets import QAction
    QT_API = "PyQt5"
except ImportError:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
        from PyQt6.QtCore import Qt, QThread, pyqtSignal as Signal, pyqtSlot as Slot, QSize, QRect, QPoint
        from PyQt6.QtGui import QAction
        QT_API = "PyQt6"
    except ImportError:
        try:
            from PySide6 import QtCore, QtGui, QtWidgets
            from PySide6.QtCore import Qt, QThread, Signal, Slot, QSize, QRect, QPoint
            from PySide6.QtGui import QAction
            QT_API = "PySide6"
        except ImportError:
            raise ImportError("No supported Qt binding found (PyQt5, PyQt6, or PySide6). Please install PyQt5 or PyQt6.")

# Enum compatibility helpers
def align_center():
    if hasattr(Qt, "AlignmentFlag"):
        return Qt.AlignmentFlag.AlignCenter
    return Qt.AlignCenter

def align_left():
    if hasattr(Qt, "AlignmentFlag"):
        return Qt.AlignmentFlag.AlignLeft
    return Qt.AlignLeft

def align_right():
    if hasattr(Qt, "AlignmentFlag"):
        return Qt.AlignmentFlag.AlignRight
    return Qt.AlignRight

def align_vcenter():
    if hasattr(Qt, "AlignmentFlag"):
        return Qt.AlignmentFlag.AlignVCenter
    return Qt.AlignVCenter

def item_is_selectable():
    if hasattr(Qt, "ItemFlag"):
        return Qt.ItemFlag.ItemIsSelectable
    return Qt.ItemIsSelectable

def item_is_enabled():
    if hasattr(Qt, "ItemFlag"):
        return Qt.ItemFlag.ItemIsEnabled
    return Qt.ItemIsEnabled

def item_is_editable():
    if hasattr(Qt, "ItemFlag"):
        return Qt.ItemFlag.ItemIsEditable
    return Qt.ItemIsEditable
