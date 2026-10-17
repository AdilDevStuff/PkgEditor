"""
Modern Styling and Themes for PkgEditor
Features PlayStation Blue accents with Dark and Light mode support.
"""

DARK_THEME = """
QWidget {
    background-color: #1e1f29;
    color: #e0e0e0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #181920;
}

QMenuBar {
    background-color: #181920;
    color: #e0e0e0;
    border-bottom: 1px solid #2d2f3d;
    padding: 2px;
}

QMenuBar::item {
    background: transparent;
    padding: 6px 10px;
    border-radius: 4px;
}

QMenuBar::item:selected {
    background-color: #2b2d3c;
    color: #ffffff;
}

QMenu {
    background-color: #1e1f29;
    color: #e0e0e0;
    border: 1px solid #333649;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #0070d1;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #2e3144;
    margin: 4px 8px;
}

QToolBar {
    background-color: #181920;
    border-bottom: 1px solid #2d2f3d;
    spacing: 6px;
    padding: 4px;
}

QToolButton {
    background-color: transparent;
    color: #e0e0e0;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 6px;
}

QToolButton:hover {
    background-color: #2b2d3c;
    border-color: #3b3e52;
}

QToolButton:pressed {
    background-color: #0070d1;
    color: #ffffff;
}

QTabWidget::pane {
    border: 1px solid #2d2f3d;
    background-color: #1e1f29;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #181920;
    color: #a0a4b8;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    border: 1px solid #2d2f3d;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #1e1f29;
    color: #0084ff;
    font-weight: bold;
    border-top: 2px solid #0070d1;
}

QTabBar::tab:hover:!selected {
    background-color: #232532;
    color: #ffffff;
}

QPushButton {
    background-color: #2a2d3e;
    color: #ffffff;
    border: 1px solid #3d425a;
    border-radius: 5px;
    padding: 6px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #35394f;
    border-color: #0070d1;
}

QPushButton:pressed {
    background-color: #0070d1;
}

QPushButton:disabled {
    background-color: #1a1b24;
    color: #5d6175;
    border-color: #252735;
}

QPushButton#primaryButton {
    background-color: #0070d1;
    border: 1px solid #0084ff;
}

QPushButton#primaryButton:hover {
    background-color: #0084ff;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #15161c;
    color: #ffffff;
    border: 1px solid #333649;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #0070d1;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #0084ff;
}

QTreeWidget, QTreeView, QTableWidget, QTableView, QListWidget {
    background-color: #15161c;
    alternate-background-color: #1a1b23;
    color: #e0e0e0;
    border: 1px solid #2d2f3d;
    border-radius: 4px;
    gridline-color: #252735;
    selection-background-color: #0070d1;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #1e1f29;
    color: #8c92a4;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #2d2f3d;
    border-bottom: 1px solid #2d2f3d;
    font-weight: 600;
}

QGroupBox {
    border: 1px solid #2d2f3d;
    border-radius: 6px;
    margin-top: 18px;
    padding-top: 12px;
    font-weight: bold;
    color: #0084ff;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 4px;
    background-color: #1e1f29;
}

QProgressBar {
    background-color: #15161c;
    border: 1px solid #2d2f3d;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #005bb5, stop:1 #0084ff);
    border-radius: 3px;
}

QStatusBar {
    background-color: #181920;
    color: #8c92a4;
    border-top: 1px solid #2d2f3d;
}

QScrollBar:vertical {
    background: #181920;
    width: 10px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #333649;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #0070d1;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #181920;
    height: 10px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #333649;
    min-width: 20px;
    border-radius: 5px;
}

QScrollBar::handle:horizontal:hover {
    background: #0070d1;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
"""

LIGHT_THEME = """
QWidget {
    background-color: #f7f9fc;
    color: #2b2e3a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #edf2f7;
}

QMenuBar {
    background-color: #edf2f7;
    color: #2b2e3a;
    border-bottom: 1px solid #d2d8e4;
    padding: 2px;
}

QMenuBar::item:selected {
    background-color: #e2e8f0;
}

QMenu {
    background-color: #ffffff;
    color: #2b2e3a;
    border: 1px solid #cbd5e0;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item:selected {
    background-color: #0070d1;
    color: #ffffff;
}

QTabWidget::pane {
    border: 1px solid #cbd5e0;
    background-color: #ffffff;
}

QTabBar::tab {
    background-color: #e2e8f0;
    color: #4a5568;
    padding: 8px 16px;
    border: 1px solid #cbd5e0;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background-color: #ffffff;
    color: #0070d1;
    font-weight: bold;
    border-top: 2px solid #0070d1;
}

QPushButton {
    background-color: #ffffff;
    color: #2d3748;
    border: 1px solid #cbd5e0;
    border-radius: 5px;
    padding: 6px 14px;
}

QPushButton:hover {
    background-color: #edf2f7;
    border-color: #0070d1;
}

QPushButton:pressed {
    background-color: #0070d1;
    color: #ffffff;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #ffffff;
    color: #2d3748;
    border: 1px solid #cbd5e0;
    border-radius: 4px;
    padding: 6px;
}

QTreeWidget, QTreeView, QTableWidget, QTableView, QListWidget {
    background-color: #ffffff;
    alternate-background-color: #f7fafc;
    color: #2d3748;
    border: 1px solid #cbd5e0;
}

QHeaderView::section {
    background-color: #edf2f7;
    color: #4a5568;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #cbd5e0;
    border-bottom: 1px solid #cbd5e0;
    font-weight: 600;
}
"""
