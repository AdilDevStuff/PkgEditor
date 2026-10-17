"""
GP4 Project Editor View.
Allows viewing, modifying, adding files/directories to GP4 projects,
and validating projects for packaging.
"""
import os
from .qt_compat import QtWidgets, QtCore, QtGui, Signal, Slot
from .icons import get_icon
from ..core.gp4 import Gp4Project, Gp4File, Gp4Dir


class Gp4View(QtWidgets.QWidget):
    modified_changed = Signal(bool)

    def __init__(self, proj: Optional[Gp4Project] = None, file_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.proj = proj or Gp4Project.create()
        self.file_path = file_path
        self._modified = False
        self._loading = False

        self._init_ui()
        self.reload_data()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # Splitter between Properties (Top) and Files (Bottom)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        # --- Top: Volume & Package Properties ---
        prop_widget = QtWidgets.QWidget()
        prop_layout = QtWidgets.QVBoxLayout(prop_widget)
        prop_layout.setContentsMargins(0, 0, 0, 0)

        group_box = QtWidgets.QGroupBox("Package & Volume Properties")
        form = QtWidgets.QFormLayout(group_box)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItems(["pkg_ps4_app (Application/Game)", "pkg_ps4_ac_data (Add-on Content with Data)", "pkg_ps4_ac_nodata (Add-on Content without Data)"])
        self.type_combo.currentIndexChanged.connect(self._on_prop_changed)
        form.addRow("Package Type:", self.type_combo)

        self.cid_edit = QtWidgets.QLineEdit()
        self.cid_edit.setMaxLength(36)
        self.cid_edit.textChanged.connect(self._on_prop_changed)
        form.addRow("Content ID:", self.cid_edit)

        self.passcode_edit = QtWidgets.QLineEdit()
        self.passcode_edit.setMaxLength(32)
        self.passcode_edit.textChanged.connect(self._on_prop_changed)
        form.addRow("Passcode:", self.passcode_edit)

        self.entitlement_edit = QtWidgets.QLineEdit()
        self.entitlement_edit.setMaxLength(32)
        self.entitlement_edit.textChanged.connect(self._on_prop_changed)
        form.addRow("Entitlement Key:", self.entitlement_edit)

        self.ts_edit = QtWidgets.QLineEdit()
        self.ts_edit.textChanged.connect(self._on_prop_changed)
        form.addRow("Volume Timestamp:", self.ts_edit)

        prop_layout.addWidget(group_box)
        splitter.addWidget(prop_widget)

        # --- Bottom: Files & Directories ---
        files_widget = QtWidgets.QWidget()
        files_layout = QtWidgets.QVBoxLayout(files_widget)
        files_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        tb = QtWidgets.QHBoxLayout()
        self.add_files_btn = QtWidgets.QPushButton("Add Files...")
        self.add_files_btn.setIcon(get_icon("plus"))
        self.add_files_btn.clicked.connect(self._on_add_files)
        tb.addWidget(self.add_files_btn)

        self.add_dir_btn = QtWidgets.QPushButton("Add Folder...")
        self.add_dir_btn.setIcon(get_icon("folder"))
        self.add_dir_btn.clicked.connect(self._on_add_dir)
        tb.addWidget(self.add_dir_btn)

        self.del_btn = QtWidgets.QPushButton("Remove Selected")
        self.del_btn.setIcon(get_icon("delete"))
        self.del_btn.clicked.connect(self._on_remove_selected)
        tb.addWidget(self.del_btn)

        tb.addStretch()

        self.validate_btn = QtWidgets.QPushButton("Validate Project")
        self.validate_btn.setIcon(get_icon("check"))
        self.validate_btn.clicked.connect(self._on_validate)
        tb.addWidget(self.validate_btn)

        files_layout.addLayout(tb)

        # Table of files
        self.files_table = QtWidgets.QTableWidget()
        self.files_table.setColumnCount(3)
        self.files_table.setHorizontalHeaderLabels(["Target Path (in PKG)", "Source / Original Path", "Status / Size"])
        self.files_table.horizontalHeader().setStretchLastSection(True)
        self.files_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        files_layout.addWidget(self.files_table)

        splitter.addWidget(files_widget)
        splitter.setSizes([180, 400])

        main_layout.addWidget(splitter)

    def reload_data(self):
        self._loading = True
        # Type
        if "ac_nodata" in self.proj.volume_type:
            self.type_combo.setCurrentIndex(2)
            self.entitlement_edit.setEnabled(True)
        elif "ac" in self.proj.volume_type:
            self.type_combo.setCurrentIndex(1)
            self.entitlement_edit.setEnabled(True)
        else:
            self.type_combo.setCurrentIndex(0)
            self.entitlement_edit.setEnabled(False)

        self.cid_edit.setText(self.proj.content_id)
        self.passcode_edit.setText(self.proj.passcode)
        self.entitlement_edit.setText(self.proj.entitlement_key or "")
        self.ts_edit.setText(self.proj.volume_ts)

        # Files table
        base_dir = os.path.dirname(os.path.abspath(self.file_path)) if self.file_path else os.getcwd()
        self.files_table.setRowCount(len(self.proj.files))

        for row, f in enumerate(self.proj.files):
            item_targ = QtWidgets.QTableWidgetItem(f.targpath)
            item_targ.setIcon(get_icon("file"))
            item_orig = QtWidgets.QTableWidgetItem(f.origpath)

            # Check status on disk
            full_orig = os.path.join(base_dir, f.origpath) if not os.path.isabs(f.origpath) else f.origpath
            if os.path.exists(full_orig):
                sz = os.path.getsize(full_orig)
                sz_str = f"{sz:,} B" if sz < 1024*1024 else f"{sz/(1024*1024):.2f} MB"
                item_status = QtWidgets.QTableWidgetItem(f"Found ({sz_str})")
                item_status.setForeground(QtGui.QColor("#4cd964"))
            else:
                item_status = QtWidgets.QTableWidgetItem("Missing!")
                item_status.setForeground(QtGui.QColor("#ff3b30"))

            self.files_table.setItem(row, 0, item_targ)
            self.files_table.setItem(row, 1, item_orig)
            self.files_table.setItem(row, 2, item_status)

        self._loading = False

    def _on_prop_changed(self):
        if self._loading:
            return
        idx = self.type_combo.currentIndex()
        if idx == 0:
            self.proj.volume_type = "pkg_ps4_app"
            self.entitlement_edit.setEnabled(False)
        elif idx == 1:
            self.proj.volume_type = "pkg_ps4_ac_data"
            self.entitlement_edit.setEnabled(True)
        else:
            self.proj.volume_type = "pkg_ps4_ac_nodata"
            self.entitlement_edit.setEnabled(True)

        self.proj.content_id = self.cid_edit.text().strip()
        self.proj.passcode = self.passcode_edit.text().strip()
        self.proj.entitlement_key = self.entitlement_edit.text().strip() or None
        self.proj.volume_ts = self.ts_edit.text().strip()

        self._modified = True
        self.modified_changed.emit(True)

    def _on_add_files(self):
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Files to Add to Project")
        if not paths:
            return
        targ_dir, ok = QtWidgets.QInputDialog.getText(
            self, "Target Folder in PKG", "Enter target directory relative to root (e.g., sce_sys or leave empty for root):"
        )
        if not ok:
            return
        targ_dir = targ_dir.strip().replace('\\', '/').strip('/')
        base_dir = os.path.dirname(os.path.abspath(self.file_path)) if self.file_path else os.getcwd()

        for p in paths:
            rel_orig = os.path.relpath(p, base_dir).replace('\\', '/')
            fname = os.path.basename(p)
            targ_path = f"{targ_dir}/{fname}" if targ_dir else fname
            self.proj.add_file(rel_orig, targ_path)

        self.reload_data()
        self._modified = True
        self.modified_changed.emit(True)

    def _on_add_dir(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder to Add to Project")
        if not folder:
            return
        base_dir = os.path.dirname(os.path.abspath(self.file_path)) if self.file_path else os.getcwd()
        for root, dirs, files in os.walk(folder):
            rel_root = os.path.relpath(root, folder).replace('\\', '/')
            if rel_root == ".":
                rel_root = ""
            for f in files:
                abs_p = os.path.join(root, f)
                rel_orig = os.path.relpath(abs_p, base_dir).replace('\\', '/')
                targ_p = f"{rel_root}/{f}".lstrip('/')
                self.proj.add_file(rel_orig, targ_p)

        self.reload_data()
        self._modified = True
        self.modified_changed.emit(True)

    def _on_remove_selected(self):
        rows = sorted({idx.row() for idx in self.files_table.selectedIndexes()}, reverse=True)
        if not rows:
            return
        for r in rows:
            if r < len(self.proj.files):
                del self.proj.files[r]
        self.reload_data()
        self._modified = True
        self.modified_changed.emit(True)

    def _on_validate(self):
        base_dir = os.path.dirname(os.path.abspath(self.file_path)) if self.file_path else os.getcwd()
        results = self.proj.validate(base_dir)

        msg_box = QtWidgets.QMessageBox(self)
        msg_box.setWindowTitle("GP4 Project Validation")

        has_error = any(lvl == "Error" for lvl, _ in results)
        has_warning = any(lvl == "Warning" for lvl, _ in results)

        if has_error:
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
            msg_box.setText("Project validation failed with errors:")
        elif has_warning:
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
            msg_box.setText("Project validated with warnings:")
        else:
            msg_box.setIcon(QtWidgets.QMessageBox.Icon.Information)
            msg_box.setText("Project is 100% valid and ready to build!")

        details = "\n".join(f"[{lvl}] {msg}" for lvl, msg in results)
        msg_box.setDetailedText(details)
        msg_box.exec()

    def save(self) -> bool:
        if not self.file_path:
            return self.save_as()
        try:
            self.proj.write_to(self.file_path)
            self._modified = False
            self.modified_changed.emit(False)
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Failed to save GP4 project: {e}")
            return False

    def save_as(self) -> bool:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save GP4 Project", self.file_path or "project.gp4", "GP4 Projects (*.gp4)")
        if path:
            self.file_path = path
            return self.save()
        return False
