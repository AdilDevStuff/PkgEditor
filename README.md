# PkgEditor (Cross-Platform)

A modern, native, cross-platform graphical tool and command-line utility for PlayStation packages (`.pkg`), parameter metadata files (`PARAM.SFO`), project authoring files (`.gp4`), and PlayStation file system images (`.pfs`, `.dat`).

Designed as a drop-in, cross-platform replacement for Windows-only tools like `PkgEditor` (from LibOrbisPkg) and `PS4 PKG Tool`, running natively on **Linux**, **Windows**, and **macOS**.

---

## ✨ Features

### 1. **PlayStation PKG Inspection & Extraction**
* **Universal Format Support**:
  * **PS4 Packages** (`\x7FCNT`): Retail, Fake PKG (FPKG), Patches, Add-ons (DLC), and Remasters.
  * **PS3 / PS Vita Packages** (`\x7FPKG`): Debug & Retail PS3 packages.
* **Full File Extraction**:
  * Extract individual files or raw entries (`PARAM.SFO`, `ICON0.PNG`, `PIC1.PNG`, `changeinfo.xml`, etc.).
  * Extract decrypted contents from Outer and Inner PFS images (`pfs_image.dat`).
  * One-click **Extract All Files** with asynchronous background threading and progress reporting.
* **Icon & Metadata Preview**:
  * Live rendering of `ICON0.PNG` / `PIC0.PNG` in the header summary.
  * Instant readout of Title, Title ID, Content ID, Category, App Version, Firmware Version, and Package Size.
* **Header & Entry Table Inspector**:
  * Detailed breakdown of entry tables, offsets, flags, encrypted state, and key indices.
  * SHA-256 digest validation (Header digest, Entry table digest, PFS image digest).

### 2. **Decryption & Key Management (KeyDB)**
* **Fake PKG Auto-Unlock**: Automatically derives EKPFS using built-in RSA keysets (`PkgDerivedKey3Keyset` and `FakeKeyset`) and standard zero passcodes.
* **LibOrbisPkg KeyDB Compatibility**: Loads and saves `keydb.json` in the standard OS configuration folder (`~/.config/LibOrbisPkg/keydb.json` on Linux, `%APPDATA%\LibOrbisPkg\keydb.json` on Windows, `~/Library/Application Support/LibOrbisPkg/keydb.json` on macOS).
* **Custom Unlock**: Interactive prompt for entering custom 32-character Passcodes, 64-character EKPFS hex keys, or AES-XTS (Data + Tweak) key pairs.
* **Crypto Debugger**: Built-in tool to derive DK0..DK6 keys and generate Keystones.

### 3. **Interactive PARAM.SFO Editor**
* **Create & Edit**: Add, edit, or delete keys (Integer `0x404`, UTF-8 `0x204`, UTF-8 Special `0x004`).
* **Presets & Templates**:
  * Game / Application (`gd`)
  * Add-on Content (`ac`)
  * PS3 Game (`HG`)
* **Import / Export**: Full JSON export and import for batch modification or scripting.
* **Save / Save As**: Export byte-exact binary `PARAM.SFO` files with 4-byte alignment.

### 4. **GP4 Project Authoring & Folder Generator**
* **Project Management**: Open, modify, validate, and save `.gp4` project files.
* **One-Click Folder to GP4**: Automatically scan an extracted game or homebrew directory, detect `sce_sys/param.sfo`, and generate a complete GP4 project structure.
* **Validator**: Verify file existence, required metadata files (`sce_sys/param.sfo`, `icon0.png`), Content ID length, and Passcode validity.

### 5. **Split PKG Merger**
* Combine split package files (`game_0.pkg`, `game_1.pkg`, etc.) into a single merged `.pkg` file.
* Multi-threaded chunk merger with real-time transfer progress.

### 6. **Modern Cross-Platform UI**
* Built with PyQt (compatible with PyQt5, PyQt6, and PySide6).
* Dark and Light theme switching with PlayStation Blue accents.
* Multi-tab interface to inspect multiple packages simultaneously.
* Full Drag-and-Drop support for `.pkg`, `.sfo`, `.gp4`, `.pfs`, and `.dat` files.

---

## 🚀 Installation & Getting Started

### Prerequisites
* Python 3.8 or newer
* Linux, Windows, or macOS

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```
*(Or install via `pip install PyQt5 cryptography` / `pip install PyQt6 cryptography`)*

### 2. Launch the Application
```bash
python3 run.py
```
*(On Windows, you can double-click `run.py` or execute `python run.py`)*

### 3. (Optional) Install as CLI Command
```bash
pip install -e .
pkgeditor
```

---

## 💻 Command-Line Interface (CLI)

PkgEditor can also be used directly from the command line for headless extraction or inspection:

### Inspect Package Information
```bash
python3 run.py info /path/to/game.pkg
```

### Extract All Contents
```bash
python3 run.py extract /path/to/game.pkg /path/to/output_directory
```

---

## 📂 Project Structure

```
PkgEditor Linux/
├── run.py                     # Main application launcher
├── requirements.txt           # Python dependencies
├── setup.py                   # Package setup configuration
├── pkgeditor/
│   ├── __init__.py
│   ├── __main__.py            # CLI & GUI entry point
│   ├── core/
│   │   ├── crypto.py          # SHA256, HMAC, AES-CBC, AES-XTS, RSA-2048 PKCS#1 v1.5
│   │   ├── keys.py            # Keyset definitions (FakeKeyset, PkgDerivedKey3Keyset, public keys)
│   │   ├── keydb.py           # Cross-platform keydb.json manager
│   │   ├── sfo.py             # PARAM.SFO parser, writer, templates
│   │   ├── gp4.py             # GP4 XML parser, generator, and validator
│   │   ├── pfs.py             # PFS filesystem reader, PFSC decompressor, XTS decryptor
│   │   ├── pkg.py             # PS4 and PS3 PKG parser and extractor
│   │   └── merger.py          # Split PKG merger (*_0.pkg -> .pkg)
│   └── gui/
│       ├── qt_compat.py       # PyQt5 / PyQt6 / PySide6 abstraction
│       ├── styles.py          # Dark & Light stylesheets
│       ├── main_window.py     # Main application window & tabs
│       ├── pkg_view.py        # PKG inspection and extraction view
│       ├── sfo_view.py        # PARAM.SFO table editor view
│       ├── gp4_view.py        # GP4 project editor view
│       ├── pfs_view.py        # Standalone PFS image viewer
│       ├── crypto_debug.py    # Crypto debugger & KeyDB dialog
│       └── merge_dialog.py    # Split PKG merger dialog
└── tests/
    └── test_pkgeditor.py      # Automated test suite
```

---

## 🧪 Running Tests

Run the complete test suite:
```bash
python3 -m unittest discover -s tests
```
