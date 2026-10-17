"""
PARAM.SFO Editor View.
Interactive table for viewing, editing, adding, and deleting SFO entries.
Includes template loaders (Application GD, Addon AC, PS3) and JSON import/export.
"""
import json
import os
from .qt_compat import QtWidgets, QtCore, QtGui, Signal, Slot, align_center, align_left
from .icons import get_icon
from ..core.sfo import ParamSfo, SfoValue, SfoEntryType


class SfoEditDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, entry_name="", entry_type=SfoEntryType.Utf8, entry_val="", max_len=4):
        super().__init__(parent)
        self.setWindowTitle("Edit SFO Entry" if entry_name else "Add SFO Entry")
        self.resize(420, 240)

        layout = QtWidgets.QVBoxLayout(self)

        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit(entry_name)
        if entry_name:
            self.name_edit.setEnabled(False)  # Key name shouldn't change when editing
        form.addRow("Key Name:", self.name_edit)

        self.type_combo = QtWidgets.QComboBox()
        self.type_combo.addItem("UTF-8 String (0x204)", SfoEntryType.Utf8)
        self.type_combo.addItem("32-bit Integer (0x404)", SfoEntryType.Integer)
        self.type_combo.addItem("UTF-8 Special (0x004)", SfoEntryType.Utf8Special)

        # Set selection
        for i in range(self.type_combo.count()):
            if self.type_combo.itemData(i) == entry_type:
                self.type_combo.setCurrentIndex(i)
                break
        form.addRow("Format:", self.type_combo)

        self.val_edit = QtWidgets.QLineEdit(str(entry_val))
        form.addRow("Value:", self.val_edit)

        self.maxlen_spin = QtWidgets.QSpinBox()
        self.maxlen_spin.setRange(4, 65536)
        self.maxlen_spin.setValue(max(max_len, 4))
        form.addRow("Max Length:", self.maxlen_spin)

        layout.addLayout(form)

        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_data(self):
        name = self.name_edit.text().strip().upper()
        entry_type = self.type_combo.currentData()
        raw_val = self.val_edit.text().strip()
        max_len = self.maxlen_spin.value()

        if entry_type == SfoEntryType.Integer:
            try:
                if raw_val.lower().startswith("0x"):
                    val = int(raw_val, 16)
                else:
                    val = int(raw_val)
            except ValueError:
                val = 0
        else:
            val = raw_val

        return name, entry_type, val, max_len


class SfoView(QtWidgets.QWidget):
    modified_changed = Signal(bool)

    def __init__(self, sfo: Optional[ParamSfo] = None, read_only: bool = False, file_path: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.sfo = sfo or ParamSfo()
        self.read_only = read_only
        self.file_path = file_path
        self._modified = False

        self._init_ui()
        self.reload_data()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top toolbar
        if not self.read_only:
            toolbar = QtWidgets.QHBoxLayout()

            self.add_btn = QtWidgets.QPushButton("Add Entry")
            self.add_btn.setIcon(get_icon("plus"))
            self.add_btn.clicked.connect(self._on_add)
            toolbar.addWidget(self.add_btn)

            self.edit_btn = QtWidgets.QPushButton("Edit Entry")
            self.edit_btn.setIcon(get_icon("edit"))
            self.edit_btn.clicked.connect(self._on_edit)
            toolbar.addWidget(self.edit_btn)

            self.del_btn = QtWidgets.QPushButton("Delete Entry")
            self.del_btn.setIcon(get_icon("delete"))
            self.del_btn.clicked.connect(self._on_delete)
            toolbar.addWidget(self.del_btn)

            toolbar.addSpacing(12)

            self.tpl_btn = QtWidgets.QPushButton("Load Template...")
            self.tpl_btn.setIcon(get_icon("package"))
            tpl_menu = QtWidgets.QMenu(self)
            tpl_gd = tpl_menu.addAction("Application / Game (gd)")
            tpl_gd.triggered.connect(lambda: self.load_template("gd"))
            tpl_ac = tpl_menu.addAction("Add-on Content (ac)")
            tpl_ac.triggered.connect(lambda: self.load_template("ac"))
            tpl_ps3 = tpl_menu.addAction("PS3 Game (HG)")
            tpl_ps3.triggered.connect(lambda: self.load_template("ps3"))
            self.tpl_btn.setMenu(tpl_menu)
            toolbar.addWidget(self.tpl_btn)

            toolbar.addStretch()

            self.export_json_btn = QtWidgets.QPushButton("Export JSON")
            self.export_json_btn.setIcon(get_icon("download"))
            self.export_json_btn.clicked.connect(self._on_export_json)
            toolbar.addWidget(self.export_json_btn)

            self.import_json_btn = QtWidgets.QPushButton("Import JSON")
            self.import_json_btn.setIcon(get_icon("folder_open"))
            self.import_json_btn.clicked.connect(self._on_import_json)
            toolbar.addWidget(self.import_json_btn)

            layout.addLayout(toolbar)

        # Table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Key Name", "Type", "Length", "Max Length", "Value"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers if self.read_only else QtWidgets.QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        layout.addWidget(self.table)

    def reload_data(self):
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.sfo.values))

        for row, entry in enumerate(self.sfo.values):
            item_name = QtWidgets.QTableWidgetItem(entry.name)
            item_name.setFlags(item_name.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            type_name = "Integer" if entry.entry_type == SfoEntryType.Integer else "UTF-8"
            item_type = QtWidgets.QTableWidgetItem(type_name)
            item_type.setFlags(item_type.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            item_len = QtWidgets.QTableWidgetItem(str(entry.length))
            item_len.setFlags(item_len.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            item_maxlen = QtWidgets.QTableWidgetItem(str(entry.max_length))
            item_maxlen.setFlags(item_maxlen.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            # Display value
            if entry.entry_type == SfoEntryType.Integer:
                val_str = f"{entry.value} (0x{entry.value:X})"
            else:
                val_str = str(entry.value)
            item_val = QtWidgets.QTableWidgetItem(val_str)
            if self.read_only:
                item_val.setFlags(item_val.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_type)
            self.table.setItem(row, 2, item_len)
            self.table.setItem(row, 3, item_maxlen)
            self.table.setItem(row, 4, item_val)

    def _mark_modified(self):
        self._modified = True
        self.modified_changed.emit(True)

    def _on_cell_double_clicked(self, row, col):
        if not self.read_only:
            self._on_edit()

    def _on_add(self):
        dlg = SfoEditDialog(self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            name, entry_type, val, max_len = dlg.get_data()
            if not name:
                QtWidgets.QMessageBox.warning(self, "Invalid Name", "Key name cannot be empty.")
                return
            self.sfo.add_value(name, entry_type, val, max_len)
            self.reload_data()
            self._mark_modified()

    def _on_edit(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.sfo.values):
            return
        entry = self.sfo.values[row]
        dlg = SfoEditDialog(self, entry.name, entry.entry_type, entry.value, entry.max_length)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            _, entry_type, val, max_len = dlg.get_data()
            entry.entry_type = entry_type
            entry.value = val
            entry.max_length = max_len
            self.reload_data()
            self._mark_modified()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0 or row >= len(self.sfo.values):
            return
        entry = self.sfo.values[row]
        confirm = QtWidgets.QMessageBox.question(
            self, "Confirm Delete", f"Are you sure you want to delete entry '{entry.name}'?",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No
        )
        if confirm == QtWidgets.QMessageBox.StandardButton.Yes:
            self.sfo.remove_value(entry.name)
            self.reload_data()
            self._mark_modified()

    def load_template(self, tpl_type: str):
        if tpl_type == "gd":
            self.sfo = ParamSfo.create_template_gd()
        elif tpl_type == "ac":
            self.sfo = ParamSfo.create_template_ac()
        elif tpl_type == "ps3":
            self.sfo = ParamSfo.create_template_ps3_game()
        self.reload_data()
        self._mark_modified()

    def _on_export_json(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export SFO to JSON", "", "JSON Files (*.json)")
        if path:
            data = self.sfo.to_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            QtWidgets.QMessageBox.information(self, "Exported", f"Successfully exported to {path}")

    def _on_import_json(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Import SFO from JSON", "", "JSON Files (*.json)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in data.items():
                self.sfo[k] = v
            self.reload_data()
            self._mark_modified()

    def save(self) -> bool:
        if not self.file_path:
            return self.save_as()
        try:
            self.sfo.save(self.file_path)
            self._modified = False
            self.modified_changed.emit(False)
            return True
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Failed to save SFO: {e}")
            return False

    def save_as(self) -> bool:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save SFO File", self.file_path or "PARAM.SFO", "SFO Files (*.sfo)")
        if path:
            self.file_path = path
            return self.save()
        return False
