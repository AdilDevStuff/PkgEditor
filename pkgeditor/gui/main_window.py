"""
Main Window for PkgEditor Cross-Platform.
Tabbed interface for opening, inspecting, editing, and extracting PKG, GP4, SFO, and PFS files.
Full drag-and-drop support, dark/light theme switching, and tools integration.
"""
import os
import sys
from .qt_compat import QtWidgets, QtCore, QtGui, Signal, Slot, QAction, align_center
from .styles import DARK_THEME, LIGHT_THEME
from .icons import get_icon, get_pixmap
from .pkg_view import PkgView
from .sfo_view import SfoView
from .gp4_view import Gp4View
from .pfs_view import PfsView
from .crypto_debug import CryptoDebugDialog
from .merge_dialog import MergeDialog
from ..core.sfo import ParamSfo
from ..core.gp4 import Gp4Project


class WelcomeWidget(QtWidgets.QWidget):
    open_file_clicked = Signal()
    new_gp4_clicked = Signal()
    new_sfo_clicked = Signal()
    merge_parts_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        title = QtWidgets.QLabel("PkgEditor")
        title.setStyleSheet("font-size: 32px; font-weight: bold; color: #0084ff;")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        subtitle = QtWidgets.QLabel("Cross-Platform PlayStation Package & Metadata Toolkit\n(Windows, Linux, macOS)")
        subtitle.setStyleSheet("font-size: 14px; color: #8c92a4;")
        subtitle.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        drop_box = QtWidgets.QFrame()
        drop_box.setFixedSize(460, 180)
        drop_box.setStyleSheet(
            "border: 2px dashed #3d425a; border-radius: 12px; background-color: #15161c;"
        )
        drop_layout = QtWidgets.QVBoxLayout(drop_box)
        drop_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        drop_icon = QtWidgets.QLabel()
        drop_icon.setPixmap(get_pixmap("package", color="#0084ff", size=52))
        drop_icon.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_icon)

        drop_text = QtWidgets.QLabel("Drag and drop .pkg, .sfo, .gp4, or .pfs files here\nor choose an action below")
        drop_text.setStyleSheet("color: #a0a4b8; font-size: 13px; margin-top: 6px;")
        drop_text.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(drop_text)

        layout.addWidget(drop_box, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        # Quick action buttons
        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.setSpacing(10)

        open_btn = QtWidgets.QPushButton("Open File...")
        open_btn.setIcon(get_icon("folder-open"))
        open_btn.setObjectName("primaryButton")
        open_btn.setMinimumHeight(36)
        open_btn.clicked.connect(self.open_file_clicked)
        btn_layout.addWidget(open_btn)

        gp4_btn = QtWidgets.QPushButton("New GP4 Project")
        gp4_btn.setIcon(get_icon("file"))
        gp4_btn.setMinimumHeight(36)
        gp4_btn.clicked.connect(self.new_gp4_clicked)
        btn_layout.addWidget(gp4_btn)

        sfo_btn = QtWidgets.QPushButton("New PARAM.SFO")
        sfo_btn.setIcon(get_icon("file-text"))
        sfo_btn.setMinimumHeight(36)
        sfo_btn.clicked.connect(self.new_sfo_clicked)
        btn_layout.addWidget(sfo_btn)

        merge_btn = QtWidgets.QPushButton("Merge PKG Parts")
        merge_btn.setIcon(get_icon("merge"))
        merge_btn.setMinimumHeight(36)
        merge_btn.clicked.connect(self.merge_parts_clicked)
        btn_layout.addWidget(merge_btn)

        layout.addLayout(btn_layout)


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PkgEditor")
        self.resize(1100, 750)
        self.setAcceptDrops(True)
        self.is_dark_mode = True

        self._init_ui()
        self.apply_theme()

    def _init_ui(self):
        # Central stack/tabs
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self._close_tab)
        self.tabs.currentChanged.connect(self._on_tab_changed)

        self.welcome_widget = WelcomeWidget()
        self.welcome_widget.open_file_clicked.connect(self.open_file_dialog)
        self.welcome_widget.new_gp4_clicked.connect(self.new_gp4_project)
        self.welcome_widget.new_sfo_clicked.connect(self.new_sfo_file)
        self.welcome_widget.merge_parts_clicked.connect(self.show_merge_dialog)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.welcome_widget)
        self.stack.addWidget(self.tabs)
        self.setCentralWidget(self.stack)

        self._create_menus()
        self._create_toolbar()
        self.statusBar().showMessage("Ready")

    def _create_menus(self):
        menubar = self.menuBar()

        # File Menu
        file_menu = menubar.addMenu("&File")

        open_act = QAction(get_icon("folder-open"), "&Open File...", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_act)

        open_dir_act = QAction(get_icon("folder"), "Open Folder as GP4...", self)
        open_dir_act.triggered.connect(self.open_folder_as_gp4)
        file_menu.addAction(open_dir_act)

        file_menu.addSeparator()

        new_gp4_act = QAction(get_icon("file"), "New &GP4 Project...", self)
        new_gp4_act.triggered.connect(self.new_gp4_project)
        file_menu.addAction(new_gp4_act)

        new_sfo_act = QAction(get_icon("file-text"), "New &PARAM.SFO...", self)
        new_sfo_act.triggered.connect(self.new_sfo_file)
        file_menu.addAction(new_sfo_act)

        file_menu.addSeparator()

        self.save_act = QAction(get_icon("save"), "&Save", self)
        self.save_act.setShortcut("Ctrl+S")
        self.save_act.setEnabled(False)
        self.save_act.triggered.connect(self._save_current)
        file_menu.addAction(self.save_act)

        self.save_as_act = QAction(get_icon("save"), "Save &As...", self)
        self.save_as_act.setShortcut("Ctrl+Shift+S")
        self.save_as_act.setEnabled(False)
        self.save_as_act.triggered.connect(self._save_as_current)
        file_menu.addAction(self.save_as_act)

        file_menu.addSeparator()

        self.close_tab_act = QAction(get_icon("delete"), "&Close Tab", self)
        self.close_tab_act.setShortcut("Ctrl+W")
        self.close_tab_act.setEnabled(False)
        self.close_tab_act.triggered.connect(lambda: self._close_tab(self.tabs.currentIndex()))
        file_menu.addAction(self.close_tab_act)

        file_menu.addSeparator()

        exit_act = QAction("E&xit", self)
        exit_act.setShortcut("Ctrl+Q")
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        # Tools Menu
        tools_menu = menubar.addMenu("&Tools")

        merge_act = QAction(get_icon("merge"), "Combine Split PKG Parts...", self)
        merge_act.triggered.connect(self.show_merge_dialog)
        tools_menu.addAction(merge_act)

        crypto_act = QAction(get_icon("key"), "Crypto Debugger & KeyDB...", self)
        crypto_act.triggered.connect(self.show_crypto_dialog)
        tools_menu.addAction(crypto_act)

        # View Menu
        view_menu = menubar.addMenu("&View")
        theme_act = QAction(get_icon("theme"), "Toggle Dark/Light Mode", self)
        theme_act.triggered.connect(self.toggle_theme)
        view_menu.addAction(theme_act)

        # Help Menu
        help_menu = menubar.addMenu("&Help")
        about_act = QAction(get_icon("info"), "About PkgEditor", self)
        about_act.triggered.connect(self._show_about)
        help_menu.addAction(about_act)

    def _create_toolbar(self):
        tb = self.addToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QtCore.QSize(20, 20))

        open_act = QAction(get_icon("folder-open"), "Open", self)
        open_act.triggered.connect(self.open_file_dialog)
        tb.addAction(open_act)

        tb.addSeparator()

        gp4_act = QAction(get_icon("file"), "New GP4", self)
        gp4_act.triggered.connect(self.new_gp4_project)
        tb.addAction(gp4_act)

        sfo_act = QAction(get_icon("file-text"), "New SFO", self)
        sfo_act.triggered.connect(self.new_sfo_file)
        tb.addAction(sfo_act)

        tb.addSeparator()

        merge_act = QAction(get_icon("merge"), "Merge Parts", self)
        merge_act.triggered.connect(self.show_merge_dialog)
        tb.addAction(merge_act)

        crypto_act = QAction(get_icon("key"), "KeyDB", self)
        crypto_act.triggered.connect(self.show_crypto_dialog)
        tb.addAction(crypto_act)

        tb.addSeparator()

        theme_act = QAction(get_icon("theme"), "Theme", self)
        theme_act.triggered.connect(self.toggle_theme)
        tb.addAction(theme_act)

    def apply_theme(self):
        stylesheet = DARK_THEME if self.is_dark_mode else LIGHT_THEME
        self.setStyleSheet(stylesheet)

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def open_file(self, file_path: str):
        if not os.path.exists(file_path):
            QtWidgets.QMessageBox.critical(self, "Error", f"File not found: {file_path}")
            return

        ext = file_path.split('.')[-1].lower()
        title = os.path.basename(file_path)

        try:
            if ext == "pkg":
                view = PkgView(file_path)
                view.open_sfo_requested.connect(self._open_sfo_subview)
                self.add_tab(view, title)
            elif ext == "sfo":
                sfo = ParamSfo.from_file(file_path)
                view = SfoView(sfo, read_only=False, file_path=file_path)
                view.modified_changed.connect(lambda m: self._on_view_modified(view, m))
                self.add_tab(view, title)
            elif ext == "gp4":
                proj = Gp4Project.read_from(file_path)
                view = Gp4View(proj, file_path=file_path)
                view.modified_changed.connect(lambda m: self._on_view_modified(view, m))
                self.add_tab(view, title)
            elif ext in ("pfs", "dat"):
                view = PfsView(file_path)
                self.add_tab(view, title)
            else:
                QtWidgets.QMessageBox.warning(self, "Unsupported File", f"Unsupported file type: .{ext}")
                return

            self.statusBar().showMessage(f"Loaded: {file_path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Failed to Open File", f"Error opening {title}:\n{e}")

    def _open_sfo_subview(self, sfo: ParamSfo, title: str):
        view = SfoView(sfo, read_only=False)
        self.add_tab(view, f"{title} [Editor]")

    def add_tab(self, widget: QtWidgets.QWidget, title: str):
        idx = self.tabs.addTab(widget, title)
        self.tabs.setCurrentIndex(idx)
        self._update_ui_state()

    def _close_tab(self, index: int):
        if index < 0 or index >= self.tabs.count():
            return
        w = self.tabs.widget(index)
        if hasattr(w, 'close'):
            w.close()
        self.tabs.removeTab(index)
        self._update_ui_state()

    def _update_ui_state(self):
        count = self.tabs.count()
        if count == 0:
            self.stack.setCurrentWidget(self.welcome_widget)
            self.save_act.setEnabled(False)
            self.save_as_act.setEnabled(False)
            self.close_tab_act.setEnabled(False)
        else:
            self.stack.setCurrentWidget(self.tabs)
            self.close_tab_act.setEnabled(True)
            self._on_tab_changed(self.tabs.currentIndex())

    def _on_tab_changed(self, index: int):
        w = self.tabs.widget(index) if index >= 0 else None
        can_save = isinstance(w, (SfoView, Gp4View))
        self.save_act.setEnabled(can_save)
        self.save_as_act.setEnabled(can_save)

    def _on_view_modified(self, widget: QtWidgets.QWidget, modified: bool):
        for i in range(self.tabs.count()):
            if self.tabs.widget(i) == widget:
                title = self.tabs.tabText(i).lstrip('*')
                if modified:
                    self.tabs.setTabText(i, f"*{title}")
                else:
                    self.tabs.setTabText(i, title)
                break

    def _save_current(self):
        w = self.tabs.currentWidget()
        if hasattr(w, 'save'):
            w.save()

    def _save_as_current(self):
        w = self.tabs.currentWidget()
        if hasattr(w, 'save_as'):
            w.save_as()

    def open_file_dialog(self):
        filt = (
            "All Supported (*.pkg *.sfo *.gp4 *.pfs *.dat);;"
            "PKG Files (*.pkg);;"
            "SFO Files (*.sfo);;"
            "GP4 Projects (*.gp4);;"
            "PFS Images (*.pfs *.dat);;"
            "All Files (*.*)"
        )
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open PlayStation File", "", filt)
        if path:
            self.open_file(path)

    def open_folder_as_gp4(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Game/App Folder to Open as GP4")
        if folder:
            proj = Gp4Project.generate_from_directory(folder)
            gp4_name = f"{os.path.basename(folder)}.gp4"
            out_gp4 = os.path.join(folder, gp4_name)
            view = Gp4View(proj, file_path=out_gp4)
            view.modified_changed.connect(lambda m: self._on_view_modified(view, m))
            self.add_tab(view, f"*{gp4_name}")

    def new_gp4_project(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Choose New GP4 Location", "project.gp4", "GP4 Projects (*.gp4)")
        if path:
            proj = Gp4Project.create()
            view = Gp4View(proj, file_path=path)
            view.modified_changed.connect(lambda m: self._on_view_modified(view, m))
            self.add_tab(view, f"*{os.path.basename(path)}")

    def new_sfo_file(self):
        sfo = ParamSfo.create_template_gd()
        view = SfoView(sfo, read_only=False)
        view.modified_changed.connect(lambda m: self._on_view_modified(view, m))
        self.add_tab(view, "*New SFO")

    def show_merge_dialog(self):
        dlg = MergeDialog(self)
        dlg.exec()

    def show_crypto_dialog(self):
        dlg = CryptoDebugDialog(self)
        dlg.exec()

    def _show_about(self):
        QtWidgets.QMessageBox.about(
            self,
            "About PkgEditor",
            "<b>PkgEditor (Cross-Platform)</b><br><br>"
            "A modern, cross-platform graphical tool for inspecting, modifying, and extracting PlayStation package files (.pkg), "
            "parameter files (.sfo), GP4 authoring projects (.gp4), and file system images (.pfs, .dat).<br><br>"
            "Designed to run natively across Linux, Windows, and macOS with high performance and full compatibility with LibOrbisPkg."
        )

    # --- Drag & Drop ---
    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent):
        for url in event.mimeData().urls():
            f = url.toLocalFile()
            if os.path.exists(f):
                self.open_file(f)
