"""
Crypto Debugger and KeyDB Manager Dialog.
Allows managing stored Passcodes, EKPFS, and XTS keys, and calculating derived keys/hashes.
"""
from .qt_compat import QtWidgets, QtCore, QtGui
from .icons import get_icon
from ..core.keydb import get_keydb
from ..core import crypto


class CryptoDebugDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crypto Debugger & KeyDB Manager")
        self.resize(700, 500)
        self.keydb = get_keydb()

        self._init_ui()
        self.reload_tables()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        tabs = QtWidgets.QTabWidget()

        # Tab 1: Passcodes
        self.pass_tab = QtWidgets.QWidget()
        pass_layout = QtWidgets.QVBoxLayout(self.pass_tab)
        self.pass_table = QtWidgets.QTableWidget()
        self.pass_table.setColumnCount(2)
        self.pass_table.setHorizontalHeaderLabels(["Content ID", "Passcode"])
        self.pass_table.horizontalHeader().setStretchLastSection(True)
        pass_layout.addWidget(self.pass_table)

        pass_tb = QtWidgets.QHBoxLayout()
        add_pass_btn = QtWidgets.QPushButton("Add Passcode")
        add_pass_btn.setIcon(get_icon("plus"))
        add_pass_btn.clicked.connect(self._add_passcode)
        pass_tb.addWidget(add_pass_btn)
        del_pass_btn = QtWidgets.QPushButton("Delete Selected")
        del_pass_btn.setIcon(get_icon("delete"))
        del_pass_btn.clicked.connect(self._del_passcode)
        pass_tb.addWidget(del_pass_btn)
        pass_tb.addStretch()
        pass_layout.addLayout(pass_tb)
        tabs.addTab(self.pass_tab, get_icon("key"), "Passcodes")

        # Tab 2: EKPFS
        self.ekpfs_tab = QtWidgets.QWidget()
        ekpfs_layout = QtWidgets.QVBoxLayout(self.ekpfs_tab)
        self.ekpfs_table = QtWidgets.QTableWidget()
        self.ekpfs_table.setColumnCount(2)
        self.ekpfs_table.setHorizontalHeaderLabels(["Content ID", "EKPFS (Hex)"])
        self.ekpfs_table.horizontalHeader().setStretchLastSection(True)
        ekpfs_layout.addWidget(self.ekpfs_table)

        ekpfs_tb = QtWidgets.QHBoxLayout()
        add_ekpfs_btn = QtWidgets.QPushButton("Add EKPFS")
        add_ekpfs_btn.setIcon(get_icon("plus"))
        add_ekpfs_btn.clicked.connect(self._add_ekpfs)
        ekpfs_tb.addWidget(add_ekpfs_btn)
        del_ekpfs_btn = QtWidgets.QPushButton("Delete Selected")
        del_ekpfs_btn.setIcon(get_icon("delete"))
        del_ekpfs_btn.clicked.connect(self._del_ekpfs)
        ekpfs_tb.addWidget(del_ekpfs_btn)
        ekpfs_tb.addStretch()
        ekpfs_layout.addLayout(ekpfs_tb)
        tabs.addTab(self.ekpfs_tab, get_icon("lock"), "EKPFS Keys")

        # Tab 3: Key Derivation Tool
        self.calc_tab = QtWidgets.QWidget()
        calc_layout = QtWidgets.QVBoxLayout(self.calc_tab)

        form = QtWidgets.QFormLayout()
        self.calc_cid = QtWidgets.QLineEdit("UP0001-CUSA00001_00-0000000000000000")
        form.addRow("Content ID (36 chars):", self.calc_cid)
        self.calc_pass = QtWidgets.QLineEdit("00000000000000000000000000000000")
        form.addRow("Passcode (32 chars):", self.calc_pass)

        calc_btn = QtWidgets.QPushButton("Compute Derived Keys")
        calc_btn.setIcon(get_icon("calculator"))
        calc_btn.clicked.connect(self._on_compute_keys)
        form.addRow("", calc_btn)

        calc_layout.addLayout(form)

        self.calc_output = QtWidgets.QPlainTextEdit()
        self.calc_output.setReadOnly(True)
        self.calc_output.setFont(QtGui.QFont("Monospace", 9))
        calc_layout.addWidget(self.calc_output)

        tabs.addTab(self.calc_tab, get_icon("calculator"), "Key Derivation Calculator")

        layout.addWidget(tabs)

        # Bottom buttons
        btn_box = QtWidgets.QHBoxLayout()
        save_db_btn = QtWidgets.QPushButton("Save KeyDB")
        save_db_btn.setIcon(get_icon("save"))
        save_db_btn.clicked.connect(self._save_db)
        btn_box.addWidget(save_db_btn)
        btn_box.addStretch()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

    def reload_tables(self):
        # Passcodes
        self.pass_table.setRowCount(len(self.keydb.passcodes))
        for row, (cid, code) in enumerate(self.keydb.passcodes.items()):
            self.pass_table.setItem(row, 0, QtWidgets.QTableWidgetItem(cid))
            self.pass_table.setItem(row, 1, QtWidgets.QTableWidgetItem(code))

        # EKPFS
        self.ekpfs_table.setRowCount(len(self.keydb.ekpfs))
        for row, (cid, key_hex) in enumerate(self.keydb.ekpfs.items()):
            self.ekpfs_table.setItem(row, 0, QtWidgets.QTableWidgetItem(cid))
            self.ekpfs_table.setItem(row, 1, QtWidgets.QTableWidgetItem(key_hex))

    def _add_passcode(self):
        cid, ok1 = QtWidgets.QInputDialog.getText(self, "Add Passcode", "Enter Content ID (36 characters):")
        if not ok1 or len(cid.strip()) != 36:
            return
        code, ok2 = QtWidgets.QInputDialog.getText(self, "Add Passcode", "Enter Passcode (32 characters):")
        if not ok2 or len(code.strip()) != 32:
            return
        self.keydb.set_passcode(cid.strip(), code.strip())
        self.reload_tables()

    def _del_passcode(self):
        row = self.pass_table.currentRow()
        if row >= 0:
            cid = self.pass_table.item(row, 0).text()
            if cid in self.keydb.passcodes:
                del self.keydb.passcodes[cid]
                self.reload_tables()

    def _add_ekpfs(self):
        cid, ok1 = QtWidgets.QInputDialog.getText(self, "Add EKPFS", "Enter Content ID (36 characters):")
        if not ok1 or len(cid.strip()) != 36:
            return
        raw_hex, ok2 = QtWidgets.QInputDialog.getText(self, "Add EKPFS", "Enter EKPFS (64 hex characters):")
        if not ok2:
            return
        try:
            b = bytes.fromhex(raw_hex.strip().replace(" ", ""))
            self.keydb.set_ekpfs(cid.strip(), b)
            self.reload_tables()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Invalid Hex", str(e))

    def _del_ekpfs(self):
        row = self.ekpfs_table.currentRow()
        if row >= 0:
            cid = self.ekpfs_table.item(row, 0).text()
            if cid in self.keydb.ekpfs:
                del self.keydb.ekpfs[cid]
                self.reload_tables()

    def _save_db(self):
        try:
            self.keydb.save()
            QtWidgets.QMessageBox.information(self, "Saved", f"KeyDB saved to {self.keydb.default_file_path()}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", str(e))

    def _on_compute_keys(self):
        cid = self.calc_cid.text().strip()
        code = self.calc_pass.text().strip()
        if len(cid) != 36 or len(code) != 32:
            QtWidgets.QMessageBox.warning(self, "Error", "Content ID must be 36 characters and Passcode must be 32 characters.")
            return

        out_lines = [f"=== Key Derivation for Content ID: {cid} ==="]
        for i in range(7):
            dk = crypto.compute_keys(cid, code, i)
            digest = crypto.xor_bytes(crypto.sha256(dk), dk)
            name = "Passcode Key" if i == 0 else f"EKPFS Key" if i == 1 else f"Key {i}"
            out_lines.append(f"DK[{i}] ({name}): {dk.hex().upper()}")
            out_lines.append(f"Digest[{i}]:          {digest.hex().upper()}")
            out_lines.append("")

        keystone = crypto.create_keystone(code)
        out_lines.append(f"Keystone (Hex): {keystone.hex().upper()}")
        self.calc_output.setPlainText("\n".join(out_lines))
