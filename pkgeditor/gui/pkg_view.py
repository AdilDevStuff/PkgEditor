"""
PlayStation PKG View.
Full inspection of PKG headers, metadata, PARAM.SFO, entry tables, and file tree.
Supports file extraction, passcode/key unlocking, and digest verification.
"""
import os
from .qt_compat import QtWidgets, QtCore, QtGui, Signal, Slot, QThread
from ..core.pkg import Pkg, EntryId, MetaEntry
from ..core.pfs import PfsDir, PfsFile, PfsNode
from .sfo_view import SfoView
from .icons import get_icon
from ..core.keydb import get_keydb


class ExtractionWorker(QThread):
    progress = Signal(str, int, int)  # current_item, current_idx, total
    finished = Signal(bool, str)

    def __init__(self, pkg: Pkg, dest_dir: str):
        super().__init__()
        self.pkg = pkg
        self.dest_dir = dest_dir

    def run(self):
        try:
            self.pkg.extract_all(self.dest_dir, callback=self.on_progress)
            self.finished.emit(True, f"Successfully extracted all contents to:\n{self.dest_dir}")
        except Exception as e:
            self.finished.emit(False, str(e))

    def on_progress(self, item_name: str, cur: int, total: int):
        self.progress.emit(item_name, cur, total)


class PkgView(QtWidgets.QWidget):
    open_sfo_requested = Signal(object, str)  # ParamSfo, title

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.pkg = Pkg(file_path)
        self.worker: Optional[ExtractionWorker] = None

        self._init_ui()
        self.load_pkg_data()

    def close(self):
        if self.pkg:
            self.pkg.close()

    def _init_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        # --- Top Banner: Icon & Metadata Summary ---
        banner = QtWidgets.QFrame()
        banner.setStyleSheet("background-color: #15161c; border: 1px solid #2d2f3d; border-radius: 6px; padding: 6px;")
        banner_layout = QtWidgets.QHBoxLayout(banner)

        # Icon
        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setFixedSize(96, 96)
        self.icon_label.setScaledContents(True)
        self.icon_label.setStyleSheet("border: 1px solid #333649; border-radius: 4px; background-color: #1e1f29;")
        banner_layout.addWidget(self.icon_label)

        # Metadata text
        meta_layout = QtWidgets.QVBoxLayout()
        meta_layout.setSpacing(2)

        self.title_label = QtWidgets.QLabel("<b>Title:</b> Loading...")
        self.title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #ffffff;")
        meta_layout.addWidget(self.title_label)

        self.cid_label = QtWidgets.QLabel("<b>Content ID:</b> -")
        self.cid_label.setStyleSheet("color: #0084ff; font-family: monospace;")
        meta_layout.addWidget(self.cid_label)

        meta_row = QtWidgets.QHBoxLayout()
        self.tid_label = QtWidgets.QLabel("<b>Title ID:</b> -")
        meta_row.addWidget(self.tid_label)

        self.cat_label = QtWidgets.QLabel("<b>Category:</b> -")
        meta_row.addWidget(self.cat_label)

        self.ver_label = QtWidgets.QLabel("<b>Version:</b> -")
        meta_row.addWidget(self.ver_label)

        self.size_label = QtWidgets.QLabel("<b>Size:</b> -")
        meta_row.addWidget(self.size_label)

        meta_layout.addLayout(meta_row)

        self.status_pill = QtWidgets.QLabel("Checking encryption...")
        self.status_pill.setStyleSheet("color: #ff9500; font-weight: bold;")
        meta_layout.addWidget(self.status_pill)

        banner_layout.addLayout(meta_layout)
        banner_layout.addStretch()

        # Extract All Action button in banner
        extract_box = QtWidgets.QVBoxLayout()
        extract_box.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.extract_all_btn = QtWidgets.QPushButton("Extract All Files...")
        self.extract_all_btn.setIcon(get_icon("download", normal_color="#ffffff"))
        self.extract_all_btn.setObjectName("primaryButton")
        self.extract_all_btn.setMinimumHeight(38)
        self.extract_all_btn.clicked.connect(self._on_extract_all)
        extract_box.addWidget(self.extract_all_btn)
        banner_layout.addLayout(extract_box)

        main_layout.addWidget(banner)

        # --- Tabs ---
        self.tabs = QtWidgets.QTabWidget()

        # Tab 1: File Browser
        self.files_tab = QtWidgets.QWidget()
        self._init_files_tab()
        self.tabs.addTab(self.files_tab, get_icon("folder"), "File Browser")

        # Tab 2: PKG Entries Table
        self.entries_tab = QtWidgets.QWidget()
        self._init_entries_tab()
        self.tabs.addTab(self.entries_tab, get_icon("table"), "Raw Entries")

        # Tab 3: PARAM.SFO
        self.sfo_tab = QtWidgets.QWidget()
        self.sfo_layout = QtWidgets.QVBoxLayout(self.sfo_tab)
        self.sfo_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs.addTab(self.sfo_tab, get_icon("file-text"), "PARAM.SFO")

        # Tab 4: Header Inspector
        self.header_tab = QtWidgets.QWidget()
        self._init_header_tab()
        self.tabs.addTab(self.header_tab, get_icon("settings"), "Header Details")

        # Tab 5: Digest Validation
        self.digest_tab = QtWidgets.QWidget()
        self._init_digest_tab()
        self.tabs.addTab(self.digest_tab, get_icon("shield"), "Digest Validation")

        # Tab 6: Keys & Decryption
        self.keys_tab = QtWidgets.QWidget()
        self._init_keys_tab()
        self.tabs.addTab(self.keys_tab, get_icon("key"), "Passcode & Keys")

        main_layout.addWidget(self.tabs)

    def _init_files_tab(self):
        layout = QtWidgets.QVBoxLayout(self.files_tab)
        layout.setContentsMargins(4, 4, 4, 4)

        # Toolbar
        tb = QtWidgets.QHBoxLayout()
        self.extract_file_btn = QtWidgets.QPushButton("Extract Selected...")
        self.extract_file_btn.setIcon(get_icon("download"))
        self.extract_file_btn.clicked.connect(self._on_extract_selected_file)
        tb.addWidget(self.extract_file_btn)

        self.extract_pfs_btn = QtWidgets.QPushButton("Extract Outer PFS Image...")
        self.extract_pfs_btn.setIcon(get_icon("package"))
        self.extract_pfs_btn.clicked.connect(self._on_extract_outer_pfs)
        tb.addWidget(self.extract_pfs_btn)

        tb.addStretch()
        layout.addLayout(tb)

        # Splitter: Tree (left), List/Details (right)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        self.dir_tree = QtWidgets.QTreeWidget()
        self.dir_tree.setHeaderLabel("Directory Structure")
        self.dir_tree.itemClicked.connect(self._on_tree_item_clicked)
        splitter.addWidget(self.dir_tree)

        self.files_list = QtWidgets.QTableWidget()
        self.files_list.setColumnCount(3)
        self.files_list.setHorizontalHeaderLabels(["Name", "Size", "Compressed Size"])
        self.files_list.horizontalHeader().setStretchLastSection(True)
        self.files_list.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.files_list.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.files_list.itemDoubleClicked.connect(self._on_file_double_clicked)
        splitter.addWidget(self.files_list)

        splitter.setSizes([260, 540])
        layout.addWidget(splitter)

    def _init_entries_tab(self):
        layout = QtWidgets.QVBoxLayout(self.entries_tab)
        layout.setContentsMargins(4, 4, 4, 4)

        tb = QtWidgets.QHBoxLayout()
        self.extract_entry_btn = QtWidgets.QPushButton("Extract Selected Entry...")
        self.extract_entry_btn.setIcon(get_icon("download"))
        self.extract_entry_btn.clicked.connect(self._on_extract_selected_entry)
        tb.addWidget(self.extract_entry_btn)
        tb.addStretch()
        layout.addLayout(tb)

        self.entries_table = QtWidgets.QTableWidget()
        self.entries_table.setColumnCount(6)
        self.entries_table.setHorizontalHeaderLabels(["Entry ID", "Name", "Size", "Offset", "Encrypted", "Key Index"])
        self.entries_table.horizontalHeader().setStretchLastSection(True)
        self.entries_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.entries_table.itemDoubleClicked.connect(self._on_entry_double_clicked)
        layout.addWidget(self.entries_table)

    def _init_header_tab(self):
        layout = QtWidgets.QVBoxLayout(self.header_tab)
        layout.setContentsMargins(4, 4, 4, 4)

        self.header_tree = QtWidgets.QTreeWidget()
        self.header_tree.setHeaderLabels(["Field", "Value"])
        self.header_tree.header().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.header_tree)

    def _init_digest_tab(self):
        layout = QtWidgets.QVBoxLayout(self.digest_tab)
        layout.setContentsMargins(8, 8, 8, 8)

        tb = QtWidgets.QHBoxLayout()
        self.check_digests_btn = QtWidgets.QPushButton("Verify All Hashes / Digests")
        self.check_digests_btn.setIcon(get_icon("shield"))
        self.check_digests_btn.clicked.connect(self._on_check_digests)
        tb.addWidget(self.check_digests_btn)
        tb.addStretch()
        layout.addLayout(tb)

        self.digest_table = QtWidgets.QTableWidget()
        self.digest_table.setColumnCount(3)
        self.digest_table.setHorizontalHeaderLabels(["Digest Target", "Status", "Details"])
        self.digest_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.digest_table)

    def _init_keys_tab(self):
        layout = QtWidgets.QVBoxLayout(self.keys_tab)
        layout.setContentsMargins(8, 8, 8, 8)

        # Passcode Group
        pass_group = QtWidgets.QGroupBox("Passcode (32 characters)")
        pass_layout = QtWidgets.QHBoxLayout(pass_group)
        self.passcode_input = QtWidgets.QLineEdit()
        self.passcode_input.setPlaceholderText("00000000000000000000000000000000")
        pass_layout.addWidget(self.passcode_input)
        self.apply_passcode_btn = QtWidgets.QPushButton("Unlock with Passcode")
        self.apply_passcode_btn.setIcon(get_icon("unlock"))
        self.apply_passcode_btn.clicked.connect(self._on_apply_passcode)
        pass_layout.addWidget(self.apply_passcode_btn)
        layout.addWidget(pass_group)

        # EKPFS Group
        ekpfs_group = QtWidgets.QGroupBox("EKPFS Key (Hex string, 32 bytes)")
        ekpfs_layout = QtWidgets.QHBoxLayout(ekpfs_group)
        self.ekpfs_input = QtWidgets.QLineEdit()
        self.ekpfs_input.setPlaceholderText("Compact Hexadecimal Key (64 characters)")
        ekpfs_layout.addWidget(self.ekpfs_input)
        self.apply_ekpfs_btn = QtWidgets.QPushButton("Unlock with EKPFS")
        self.apply_ekpfs_btn.setIcon(get_icon("unlock"))
        self.apply_ekpfs_btn.clicked.connect(self._on_apply_ekpfs)
        pass_layout.addWidget(self.apply_ekpfs_btn)
        layout.addWidget(ekpfs_group)

        # XTS Keys Group
        xts_group = QtWidgets.QGroupBox("XTS Keys (Data + Tweak, 16 bytes each)")
        xts_form = QtWidgets.QFormLayout(xts_group)
        self.xts_data_input = QtWidgets.QLineEdit()
        self.xts_data_input.setPlaceholderText("Data Key (32 hex characters)")
        xts_form.addRow("Data Key:", self.xts_data_input)
        self.xts_tweak_input = QtWidgets.QLineEdit()
        self.xts_tweak_input.setPlaceholderText("Tweak Key (32 hex characters)")
        xts_form.addRow("Tweak Key:", self.xts_tweak_input)

        self.apply_xts_btn = QtWidgets.QPushButton("Unlock with XTS Keys")
        self.apply_xts_btn.setIcon(get_icon("unlock"))
        self.apply_xts_btn.clicked.connect(self._on_apply_xts)
        xts_form.addRow("", self.apply_xts_btn)
        layout.addWidget(xts_group)

        layout.addStretch()

    def load_pkg_data(self):
        # Icon
        if self.pkg.icon_bytes:
            pix = QtGui.QPixmap()
            pix.loadFromData(self.pkg.icon_bytes)
            self.icon_label.setPixmap(pix)

        # Content ID & Header
        self.cid_label.setText(f"<b>Content ID:</b> {self.pkg.header.content_id or 'Unknown'}")
        sz = self.pkg.header.package_size
        sz_str = f"{sz / (1024*1024*1024):.2f} GiB" if sz > 1024*1024*1024 else f"{sz / (1024*1024):.2f} MiB"
        self.size_label.setText(f"<b>Size:</b> {sz_str}")

        # SFO data
        if self.pkg.sfo:
            title = self.pkg.sfo["TITLE"] or "No Title"
            self.title_label.setText(f"<b>{title}</b>")
            self.tid_label.setText(f"<b>Title ID:</b> {self.pkg.sfo['TITLE_ID'] or '-'}")
            self.cat_label.setText(f"<b>Category:</b> {self.pkg.sfo['CATEGORY'] or '-'}")
            self.ver_label.setText(f"<b>Version:</b> {self.pkg.sfo['VERSION'] or self.pkg.sfo['APP_VER'] or '-'}")

            # Populate SFO tab
            sfo_widget = SfoView(self.pkg.sfo, read_only=True)
            self.sfo_layout.addWidget(sfo_widget)
        else:
            self.title_label.setText(f"<b>{os.path.basename(self.file_path)}</b>")

        # Decryption Status
        if self.pkg.inner_pfs or self.pkg.outer_pfs or self.pkg.header.is_ps3:
            self.status_pill.setText("Decrypted & Unlocked")
            self.status_pill.setStyleSheet("color: #4cd964; font-weight: bold;")
        else:
            self.status_pill.setText("Encrypted (Passcode / Keys required)")
            self.status_pill.setStyleSheet("color: #ff3b30; font-weight: bold;")

        # Populate Entries
        self._populate_entries_table()

        # Populate Header Details
        self._populate_header_tree()

        # Populate File Tree
        self._populate_file_tree()

    def _populate_entries_table(self):
        if self.pkg.header.is_ps4:
            self.entries_table.setRowCount(len(self.pkg.entries))
            for row, e in enumerate(self.pkg.entries):
                self.entries_table.setItem(row, 0, QtWidgets.QTableWidgetItem(f"0x{e.entry_id:08X}"))
                name_item = QtWidgets.QTableWidgetItem(e.name)
                name_item.setIcon(get_icon("file"))
                self.entries_table.setItem(row, 1, name_item)
                self.entries_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{e.data_size:,} B"))
                self.entries_table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"0x{e.data_offset:X}"))
                self.entries_table.setItem(row, 4, QtWidgets.QTableWidgetItem("Yes" if e.is_encrypted else "No"))
                self.entries_table.setItem(row, 5, QtWidgets.QTableWidgetItem(str(e.key_index)))
        elif self.pkg.header.is_ps3:
            self.entries_table.setRowCount(len(self.pkg.ps3_entries))
            for row, e in enumerate(self.pkg.ps3_entries):
                self.entries_table.setItem(row, 0, QtWidgets.QTableWidgetItem(f"{row}"))
                name_item = QtWidgets.QTableWidgetItem(e.name)
                name_item.setIcon(get_icon("file"))
                self.entries_table.setItem(row, 1, name_item)
                self.entries_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{e.data_size:,} B"))
                self.entries_table.setItem(row, 3, QtWidgets.QTableWidgetItem(f"0x{e.data_offset:X}"))
                self.entries_table.setItem(row, 4, QtWidgets.QTableWidgetItem("No"))
                self.entries_table.setItem(row, 5, QtWidgets.QTableWidgetItem("0"))

    def _populate_header_tree(self):
        self.header_tree.clear()
        h = self.pkg.header

        def add_item(k, v):
            item = QtWidgets.QTreeWidgetItem([str(k), str(v)])
            self.header_tree.addTopLevelItem(item)

        add_item("Magic", h.magic.decode('ascii', errors='replace'))
        add_item("Type", f"0x{h.pkg_type:X}")
        add_item("Flags", f"0x{h.pkg_flags:08X}")
        add_item("File Count", str(h.file_count))
        add_item("Entry Count", str(h.entry_count))
        add_item("Entry Table Offset", f"0x{h.entry_table_offset:X}")
        add_item("Body Offset", f"0x{h.body_offset:X}")
        add_item("Body Size", f"0x{h.body_size:X} ({h.body_size:,} B)")
        add_item("Content ID", h.content_id)
        if h.is_ps4:
            add_item("DRM Type", f"0x{h.drm_type:X}")
            add_item("Content Type", f"0x{h.content_type:X}")
            add_item("PFS Image Offset", f"0x{h.pfs_image_offset:X}")
            add_item("PFS Image Size", f"0x{h.pfs_image_size:X} ({h.pfs_image_size:,} B)")
            add_item("PFS Flags", f"0x{h.pfs_flags:X}")
            add_item("PFS Image Digest", h.pfs_image_digest.hex())

    def _populate_file_tree(self):
        self.dir_tree.clear()

        # If PS3 PKG
        if self.pkg.header.is_ps3:
            root_item = QtWidgets.QTreeWidgetItem(["PS3 Files"])
            root_item.setIcon(0, get_icon("folder"))
            root_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, "ps3_root")
            self.dir_tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)
            self._load_ps3_files()
            return

        # PS4: Outer and Inner PFS
        if self.pkg.inner_pfs:
            inner_root_item = QtWidgets.QTreeWidgetItem(["Game Image (Inner PFS)"])
            inner_root_item.setIcon(0, get_icon("folder"))
            inner_root_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, self.pkg.inner_pfs.get_uroot())
            self._add_pfs_tree_nodes(inner_root_item, self.pkg.inner_pfs.get_uroot())
            self.dir_tree.addTopLevelItem(inner_root_item)
            inner_root_item.setExpanded(True)

        if self.pkg.outer_pfs:
            outer_root_item = QtWidgets.QTreeWidgetItem(["System Container (Outer PFS)"])
            outer_root_item.setIcon(0, get_icon("folder"))
            outer_root_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, self.pkg.outer_pfs.get_super_root())
            self._add_pfs_tree_nodes(outer_root_item, self.pkg.outer_pfs.get_super_root())
            self.dir_tree.addTopLevelItem(outer_root_item)

        # Also add raw PKG Entries
        raw_root = QtWidgets.QTreeWidgetItem(["Raw Package Entries"])
        raw_root.setIcon(0, get_icon("package"))
        raw_root.setData(0, QtCore.Qt.ItemDataRole.UserRole, "raw_entries")
        self.dir_tree.addTopLevelItem(raw_root)

        # Select first item
        if self.dir_tree.topLevelItemCount() > 0:
            first = self.dir_tree.topLevelItem(0)
            self.dir_tree.setCurrentItem(first)
            self._on_tree_item_clicked(first, 0)

    def _add_pfs_tree_nodes(self, parent_item: QtWidgets.QTreeWidgetItem, dir_node: PfsDir):
        for child in dir_node.children:
            if isinstance(child, PfsDir):
                item = QtWidgets.QTreeWidgetItem([child.name])
                item.setIcon(0, get_icon("folder"))
                item.setData(0, QtCore.Qt.ItemDataRole.UserRole, child)
                parent_item.addChild(item)
                self._add_pfs_tree_nodes(item, child)

    def _on_tree_item_clicked(self, item: QtWidgets.QTreeWidgetItem, col: int):
        data = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        self.files_list.setRowCount(0)

        if data == "raw_entries":
            self.files_list.setRowCount(len(self.pkg.entries))
            for row, e in enumerate(self.pkg.entries):
                name_item = QtWidgets.QTableWidgetItem(e.name)
                name_item.setIcon(get_icon("file"))
                name_item.setData(QtCore.Qt.ItemDataRole.UserRole, e)
                self.files_list.setItem(row, 0, name_item)
                self.files_list.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{e.data_size:,} B"))
                self.files_list.setItem(row, 2, QtWidgets.QTableWidgetItem("Raw Entry"))
        elif data == "ps3_root":
            self._load_ps3_files()
        elif isinstance(data, PfsDir):
            self.files_list.setRowCount(len(data.children))
            for row, child in enumerate(data.children):
                name_item = QtWidgets.QTableWidgetItem(child.name)
                name_item.setIcon(get_icon("file") if isinstance(child, PfsFile) else get_icon("folder"))
                name_item.setData(QtCore.Qt.ItemDataRole.UserRole, child)

                if isinstance(child, PfsFile):
                    sz_str = f"{child.size:,} B"
                    comp_str = f"{child.compressed_size:,} B"
                else:
                    sz_str = "<DIR>"
                    comp_str = ""

                self.files_list.setItem(row, 0, name_item)
                self.files_list.setItem(row, 1, QtWidgets.QTableWidgetItem(sz_str))
                self.files_list.setItem(row, 2, QtWidgets.QTableWidgetItem(comp_str))

    def _load_ps3_files(self):
        self.files_list.setRowCount(len(self.pkg.ps3_entries))
        for row, e in enumerate(self.pkg.ps3_entries):
            item = QtWidgets.QTableWidgetItem(e.name)
            item.setIcon(get_icon("file"))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, e)
            self.files_list.setItem(row, 0, item)
            self.files_list.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{e.data_size:,} B"))
            self.files_list.setItem(row, 2, QtWidgets.QTableWidgetItem("Uncompressed"))

    def _on_file_double_clicked(self, item: QtWidgets.QTableWidgetItem):
        data = self.files_list.item(item.row(), 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(data, PfsFile) or isinstance(data, MetaEntry):
            self._on_extract_selected_file()

    def _on_entry_double_clicked(self, item: QtWidgets.QTableWidgetItem):
        row = item.row()
        if self.pkg.header.is_ps4 and row < len(self.pkg.entries):
            e = self.pkg.entries[row]
            if e.entry_id == EntryId.PARAM_SFO and self.pkg.sfo:
                self.open_sfo_requested.emit(self.pkg.sfo, "PARAM.SFO")
            else:
                self._on_extract_selected_entry()

    def _on_extract_selected_file(self):
        row = self.files_list.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.information(self, "Select File", "Please select a file to extract.")
            return

        node = self.files_list.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(node, PfsFile):
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Extract File", node.name)
            if save_path:
                try:
                    node.save(save_path, decompress=True)
                    QtWidgets.QMessageBox.information(self, "Extracted", f"Saved to:\n{save_path}")
                except Exception as ex:
                    QtWidgets.QMessageBox.critical(self, "Extraction Error", str(ex))
        elif isinstance(node, MetaEntry):
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Extract Entry", node.name)
            if save_path:
                try:
                    self.pkg.extract_entry(node, save_path)
                    QtWidgets.QMessageBox.information(self, "Extracted", f"Saved to:\n{save_path}")
                except Exception as ex:
                    QtWidgets.QMessageBox.critical(self, "Extraction Error", str(ex))
        elif hasattr(node, 'data_offset'):  # PS3 file
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Extract PS3 File", node.name)
            if save_path:
                try:
                    self.pkg.file.seek(node.data_offset)
                    with open(save_path, 'wb') as f:
                        rem = node.data_size
                        while rem > 0:
                            chunk = min(rem, 0x10000)
                            f.write(self.pkg.file.read(chunk))
                            rem -= chunk
                    QtWidgets.QMessageBox.information(self, "Extracted", f"Saved to:\n{save_path}")
                except Exception as ex:
                    QtWidgets.QMessageBox.critical(self, "Extraction Error", str(ex))

    def _on_extract_selected_entry(self):
        row = self.entries_table.currentRow()
        if row < 0:
            return
        if self.pkg.header.is_ps4:
            e = self.pkg.entries[row]
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Extract Raw Entry", e.name)
            if save_path:
                try:
                    self.pkg.extract_entry(e, save_path)
                    QtWidgets.QMessageBox.information(self, "Extracted", f"Saved to:\n{save_path}")
                except Exception as ex:
                    QtWidgets.QMessageBox.critical(self, "Extraction Error", str(ex))

    def _on_extract_outer_pfs(self):
        if self.pkg.header.pfs_image_size == 0:
            QtWidgets.QMessageBox.warning(self, "No PFS", "This package does not contain an outer PFS image.")
            return

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Extract Outer PFS Image", "outer_pfs.dat", "PFS Images (*.dat *.pfs)")
        if save_path:
            try:
                self.pkg.file.seek(self.pkg.header.pfs_image_offset)
                with open(save_path, 'wb') as out_f:
                    rem = self.pkg.header.pfs_image_size
                    while rem > 0:
                        chunk = min(rem, 1024*1024*4)
                        out_f.write(self.pkg.file.read(chunk))
                        rem -= chunk
                QtWidgets.QMessageBox.information(self, "Extracted", f"Saved outer PFS image to:\n{save_path}")
            except Exception as ex:
                QtWidgets.QMessageBox.critical(self, "Error", str(ex))

    def _on_extract_all(self):
        dest_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory to Extract All Contents")
        if not dest_dir:
            return

        # Progress Dialog
        self.progress_dialog = QtWidgets.QProgressDialog("Extracting package contents...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowTitle("Extracting PKG")
        self.progress_dialog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)

        self.worker = ExtractionWorker(self.pkg, dest_dir)
        self.worker.progress.connect(self._on_worker_progress)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_progress(self, item_name: str, cur: int, total: int):
        self.progress_dialog.setLabelText(f"{item_name}\n({cur} of {total})")
        if total > 0:
            percent = int((cur / total) * 100)
            self.progress_dialog.setValue(percent)

    def _on_worker_finished(self, success: bool, message: str):
        self.progress_dialog.close()
        if success:
            QtWidgets.QMessageBox.information(self, "Extraction Complete", message)
        else:
            QtWidgets.QMessageBox.critical(self, "Extraction Failed", message)

    def _on_check_digests(self):
        results = self.pkg.validate_digests()
        self.digest_table.setRowCount(len(results))
        for row, (name, passed, detail) in enumerate(results):
            self.digest_table.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
            status_item = QtWidgets.QTableWidgetItem("VALID" if passed else "FAILED")
            status_item.setForeground(QtGui.QColor("#4cd964") if passed else QtGui.QColor("#ff3b30"))
            self.digest_table.setItem(row, 1, status_item)
            self.digest_table.setItem(row, 2, QtWidgets.QTableWidgetItem(detail))

    def _on_apply_passcode(self):
        code = self.passcode_input.text().strip()
        if len(code) != 32:
            QtWidgets.QMessageBox.warning(self, "Invalid Passcode", "Passcode must be exactly 32 characters.")
            return

        if self.pkg.unlock_with_passcode(code):
            QtWidgets.QMessageBox.information(self, "Unlocked!", "Passcode accepted! Decrypted package file system.")
            self.load_pkg_data()
        else:
            QtWidgets.QMessageBox.critical(self, "Failed", "Invalid passcode for this package.")

    def _on_apply_ekpfs(self):
        raw_hex = self.ekpfs_input.text().strip().replace(" ", "").replace(":", "")
        try:
            b = bytes.fromhex(raw_hex)
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Invalid Hex", "Please enter a valid 32-byte hexadecimal string.")
            return

        if self.pkg.unlock_with_ekpfs(b):
            QtWidgets.QMessageBox.information(self, "Unlocked!", "EKPFS accepted! Decrypted package file system.")
            self.load_pkg_data()
        else:
            QtWidgets.QMessageBox.critical(self, "Failed", "Invalid EKPFS for this package.")

    def _on_apply_xts(self):
        data_hex = self.xts_data_input.text().strip().replace(" ", "")
        tweak_hex = self.xts_tweak_input.text().strip().replace(" ", "")
        try:
            d = bytes.fromhex(data_hex)
            t = bytes.fromhex(tweak_hex)
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Invalid Hex", "Both Data and Tweak keys must be 16-byte hex strings.")
            return

        if self.pkg.unlock_with_xts(d, t):
            QtWidgets.QMessageBox.information(self, "Unlocked!", "XTS Keys accepted! Decrypted package file system.")
            self.load_pkg_data()
        else:
            QtWidgets.QMessageBox.critical(self, "Failed", "Failed to unlock with provided XTS keys.")
