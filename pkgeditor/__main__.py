"""
PkgEditor Entry Point.
Launches the GUI application or runs CLI operations if specified.
"""
import sys
import os
from .gui.qt_compat import QtWidgets, QtCore
from .gui.main_window import MainWindow
from .core.pkg import Pkg


def run_cli():
    cmd = sys.argv[1].lower()
    if cmd in ("info", "inspect") and len(sys.argv) > 2:
        pkg_path = sys.argv[2]
        with Pkg(pkg_path) as p:
            print("=" * 60)
            print("Package Information")
            print("=" * 60)
            print(f"File:         {pkg_path}")
            print(f"Content ID:   {p.header.content_id}")
            print(f"Size:         {p.header.package_size:,} bytes")
            if p.sfo:
                print(f"Title:        {p.sfo['TITLE']}")
                print(f"Title ID:     {p.sfo['TITLE_ID']}")
                print(f"Category:     {p.sfo['CATEGORY']}")
                print(f"App Version:  {p.sfo['APP_VER']}")
                print(f"Version:      {p.sfo['VERSION']}")
            print(f"Entries:      {len(p.entries) or len(p.ps3_entries)}")
            print(f"Inner PFS:    {'Available' if p.inner_pfs else 'Encrypted/None'}")
            print("=" * 60)
        sys.exit(0)

    elif cmd == "extract" and len(sys.argv) > 2:
        pkg_path = sys.argv[2]
        out_dir = sys.argv[3] if len(sys.argv) > 3 else os.path.splitext(pkg_path)[0] + "_extracted"
        print(f"Extracting '{pkg_path}' to '{out_dir}'...")
        with Pkg(pkg_path) as p:
            p.extract_all(out_dir, callback=lambda item, cur, total: print(f"[{cur}/{total}] {item}"))
        print(f"Extraction completed to {out_dir}!")
        sys.exit(0)


def main():
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("info", "inspect", "extract"):
        run_cli()

    # Enable High DPI scaling
    if hasattr(QtCore.Qt, "AA_EnableHighDpiScaling"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, "AA_UseHighDpiPixmaps"):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("PkgEditor")
    app.setOrganizationName("PkgEditor")

    win = MainWindow()
    win.show()

    # If opened with a file argument: e.g. pkgeditor mygame.pkg
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        win.open_file(sys.argv[1])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
