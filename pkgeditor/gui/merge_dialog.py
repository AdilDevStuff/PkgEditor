"""
Split PKG Merger Dialog.
Merges split chunks (*_0.pkg, *_1.pkg, ...) into a single merged .pkg file.
"""
import os
from .qt_compat import QtWidgets, QtCore, QtGui, Signal, Slot, QThread
from ..core.merger import PkgMerger


class MergeWorker(QThread):
    progress = Signal(str, int, int)
    finished = Signal(bool, str)

    def __init__(self, parts, out_path):
        super().__init__()
        self.parts = parts
        self.out_path = out_path

    def run(self):
        try:
            PkgMerger.merge(self.parts, self.out_path, self.on_progress)
            self.finished.emit(True, f"Successfully merged to:\n{self.out_path}")
        except Exception as e:
            self.finished.emit(False, str(e))

    def on_progress(self, part_name, cur, total):
        self.progress.emit(part_name, cur, total)


class MergeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Combine Split PKG Parts")
        self.resize(580, 360)
        self.parts = []
        self.worker = None

        self._init_ui()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # File selection
        top_layout = QtWidgets.QHBoxLayout()
        self.part0_edit = QtWidgets.QLineEdit()
        self.part0_edit.setPlaceholderText("Select part 0 file (*_0.pkg)...")
        top_layout.addWidget(self.part0_edit)

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_part0)
        top_layout.addWidget(browse_btn)
        layout.addLayout(top_layout)

        # Parts list
        self.parts_list = QtWidgets.QListWidget()
        layout.addWidget(self.parts_list)

        # Total size label
        self.size_label = QtWidgets.QLabel("Total Size: 0 B")
        self.size_label.setStyleSheet("font-weight: bold; color: #0084ff;")
        layout.addWidget(self.size_label)

        # Output file
        out_layout = QtWidgets.QHBoxLayout()
        self.out_edit = QtWidgets.QLineEdit()
        self.out_edit.setPlaceholderText("Output merged .pkg file...")
        out_layout.addWidget(self.out_edit)

        out_browse = QtWidgets.QPushButton("Choose Output...")
        out_browse.clicked.connect(self._browse_out)
        out_layout.addWidget(out_browse)
        layout.addLayout(out_layout)

        # Progress bar
        self.prog_bar = QtWidgets.QProgressBar()
        self.prog_bar.setValue(0)
        layout.addWidget(self.prog_bar)

        self.status_lbl = QtWidgets.QLabel("Ready")
        layout.addWidget(self.status_lbl)

        # Actions
        btn_box = QtWidgets.QHBoxLayout()
        self.merge_btn = QtWidgets.QPushButton("Merge PKG Parts")
        self.merge_btn.setObjectName("primaryButton")
        self.merge_btn.clicked.connect(self._on_merge)
        btn_box.addWidget(self.merge_btn)

        btn_box.addStretch()
        cancel_btn = QtWidgets.QPushButton("Close")
        cancel_btn.clicked.connect(self.accept)
        btn_box.addWidget(cancel_btn)
        layout.addLayout(btn_box)

    def _browse_part0(self):
        f, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select Part 0 PKG", "", "PKG Parts (*_0.pkg);;All PKGs (*.pkg)")
        if f:
            self.part0_edit.setText(f)
            try:
                self.parts = PkgMerger.get_parts(f)
                self.parts_list.clear()
                total_sz = 0
                for p in self.parts:
                    sz = os.path.getsize(p)
                    total_sz += sz
                    self.parts_list.addItem(f"{os.path.basename(p)}  ({sz / (1024*1024):.2f} MB)")

                self.size_label.setText(f"Found {len(self.parts)} parts | Total Size: {total_sz / (1024*1024*1024):.2f} GiB")

                # Suggest output
                base = f[:-6] if f.endswith("_0.pkg") else f
                self.out_edit.setText(f"{base}.pkg")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Error", str(e))

    def _browse_out(self):
        f, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Output Merged PKG", self.out_edit.text() or "merged.pkg", "PKG Files (*.pkg)")
        if f:
            self.out_edit.setText(f)

    def _on_merge(self):
        if not self.parts:
            QtWidgets.QMessageBox.warning(self, "Error", "No parts selected.")
            return
        out_path = self.out_edit.text().strip()
        if not out_path:
            QtWidgets.QMessageBox.warning(self, "Error", "Please select an output file path.")
            return

        self.merge_btn.setEnabled(False)
        self.prog_bar.setValue(0)
        self.worker = MergeWorker(self.parts, out_path)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, part_name, cur, total):
        self.status_lbl.setText(f"Writing {part_name}...")
        if total > 0:
            self.prog_bar.setValue(int((cur / total) * 100))

    def _on_finished(self, success, msg):
        self.merge_btn.setEnabled(True)
        if success:
            self.status_lbl.setText("Merge completed!")
            self.prog_bar.setValue(100)
            QtWidgets.QMessageBox.information(self, "Merge Complete", msg)
        else:
            self.status_lbl.setText("Merge failed.")
            QtWidgets.QMessageBox.critical(self, "Error", msg)
