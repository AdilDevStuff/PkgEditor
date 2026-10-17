"""
Standalone PFS / DAT File System Viewer.
Allows opening and extracting files directly from .pfs / .dat PlayStation file system images.
"""
import os
from .qt_compat import QtWidgets, QtCore, QtGui, Signal, Slot
from .icons import get_icon
from ..core.pfs import PfsReader, StreamMemoryReader, PfsDir, PfsFile


class PfsView(QtWidgets.QWidget):
    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.file = open(file_path, 'rb')
        self.pfs: Optional[PfsReader] = None

        self._init_ui()
        self.load_image()

    def close(self):
        if self.file and not self.file.closed:
            self.file.close()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header Info Banner
        self.info_banner = QtWidgets.QLabel("Loading PFS image...")
        self.info_banner.setStyleSheet("background-color: #15161c; padding: 8px; border-radius: 4px; border: 1px solid #2d2f3d;")
        layout.addWidget(self.info_banner)

        # Toolbar
        tb = QtWidgets.QHBoxLayout()
        self.extract_btn = QtWidgets.QPushButton("Extract Selected...")
        self.extract_btn.setIcon(get_icon("download"))
        self.extract_btn.clicked.connect(self._on_extract_selected)
        tb.addWidget(self.extract_btn)

        self.extract_all_btn = QtWidgets.QPushButton("Extract All to Folder...")
        self.extract_all_btn.setIcon(get_icon("download"))
        self.extract_all_btn.clicked.connect(self._on_extract_all)
        tb.addWidget(self.extract_all_btn)

        tb.addStretch()
        layout.addLayout(tb)

        # Splitter: Tree (left), Files Table (right)
        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)

        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabel("Directory Structure")
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        splitter.addWidget(self.tree)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Name", "Size", "Compressed Size"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemDoubleClicked.connect(self._on_file_double_clicked)
        splitter.addWidget(self.table)

        splitter.setSizes([260, 540])
        layout.addWidget(splitter)

    def load_image(self):
        sz = os.path.getsize(self.file_path)
        try:
            reader = StreamMemoryReader(self.file, 0, sz)
            self.pfs = PfsReader(reader)
            h = self.pfs.header
            self.info_banner.setText(
                f"<b>PFS Block Size:</b> {h.block_size:,} B | "
                f"<b>Inodes:</b> {h.dinode_count:,} | "
                f"<b>Mode:</b> {h.mode.name} | "
                f"<b>Size:</b> {sz / (1024*1024):.2f} MB"
            )
            self._populate_tree()
        except Exception as e:
            self.info_banner.setText(f"<b style='color:#ff3b30;'>Failed to load PFS:</b> {e}")

    def _populate_tree(self):
        self.tree.clear()
        if not self.pfs:
            return

        root_node = self.pfs.get_super_root()
        root_item = QtWidgets.QTreeWidgetItem([root_node.name or "Root"])
        root_item.setIcon(0, get_icon("folder"))
        root_item.setData(0, QtCore.Qt.ItemDataRole.UserRole, root_node)
        self.tree.addTopLevelItem(root_item)

        self._add_dir_nodes(root_item, root_node)
        root_item.setExpanded(True)

        if self.tree.topLevelItemCount() > 0:
            self.tree.setCurrentItem(root_item)
            self._on_tree_item_clicked(root_item, 0)

    def _add_dir_nodes(self, parent_item: QtWidgets.QTreeWidgetItem, dir_node: PfsDir):
        for child in dir_node.children:
            if isinstance(child, PfsDir):
                item = QtWidgets.QTreeWidgetItem([child.name])
                item.setIcon(0, get_icon("folder"))
                item.setData(0, QtCore.Qt.ItemDataRole.UserRole, child)
                parent_item.addChild(item)
                self._add_dir_nodes(item, child)

    def _on_tree_item_clicked(self, item: QtWidgets.QTreeWidgetItem, col: int):
        node = item.data(0, QtCore.Qt.ItemDataRole.UserRole)
        self.table.setRowCount(0)
        if isinstance(node, PfsDir):
            self.table.setRowCount(len(node.children))
            for row, c in enumerate(node.children):
                name_item = QtWidgets.QTableWidgetItem(c.name)
                name_item.setIcon(get_icon("file") if isinstance(c, PfsFile) else get_icon("folder"))
                name_item.setData(QtCore.Qt.ItemDataRole.UserRole, c)
                if isinstance(c, PfsFile):
                    sz_str = f"{c.size:,} B"
                    comp_str = f"{c.compressed_size:,} B"
                else:
                    sz_str = "<DIR>"
                    comp_str = ""
                self.table.setItem(row, 0, name_item)
                self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(sz_str))
                self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(comp_str))

    def _on_file_double_clicked(self, item: QtWidgets.QTableWidgetItem):
        self._on_extract_selected()

    def _on_extract_selected(self):
        row = self.table.currentRow()
        if row < 0:
            return
        node = self.table.item(row, 0).data(QtCore.Qt.ItemDataRole.UserRole)
        if isinstance(node, PfsFile):
            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Extract File", node.name)
            if save_path:
                try:
                    node.save(save_path, decompress=True)
                    QtWidgets.QMessageBox.information(self, "Extracted", f"Saved to:\n{save_path}")
                except Exception as ex:
                    QtWidgets.QMessageBox.critical(self, "Error", str(ex))

    def _on_extract_all(self):
        if not self.pfs:
            return
        dest_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory to Extract All Contents")
        if not dest_dir:
            return

        all_files = list(self.pfs.get_all_files())
        prog = QtWidgets.QProgressDialog("Extracting files...", "Cancel", 0, len(all_files), self)
        prog.setWindowModality(QtCore.Qt.WindowModality.WindowModal)

        for i, f in enumerate(all_files):
            prog.setLabelText(f"Extracting {f.name}...")
            prog.setValue(i)
            if prog.wasCanceled():
                break
            out_p = os.path.join(dest_dir, f.full_name.lstrip('/'))
            f.save(out_p, decompress=True)

        prog.setValue(len(all_files))
        QtWidgets.QMessageBox.information(self, "Done", f"Extracted files to:\n{dest_dir}")
