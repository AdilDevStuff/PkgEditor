"""
KeyDB manager compatible with LibOrbisPkg keydb.json
Cross-platform support for storing Passcodes, EKPFS keys, and XTS keys.
"""
import os
import sys
import json
from pathlib import Path
from typing import Dict, Optional, Any


class KeyDB:
    def __init__(self):
        self.passcodes: Dict[str, str] = {}
        self.ekpfs: Dict[str, str] = {}
        self.xts: Dict[str, Dict[str, str]] = {}

    @classmethod
    def default_file_path(cls) -> Path:
        if sys.platform == "win32":
            appdata = os.environ.get("APPDATA")
            base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            base = Path(xdg_config) if xdg_config else Path.home() / ".config"

        dir_path = base / "LibOrbisPkg"
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / "keydb.json"

    @classmethod
    def load(cls, path: Optional[str] = None) -> "KeyDB":
        db = cls()
        file_path = Path(path) if path else cls.default_file_path()
        if not file_path.exists():
            return db

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            db.passcodes = data.get("Passcodes", {}) or {}
            db.ekpfs = data.get("EKPFS", {}) or {}
            db.xts = data.get("XTS", {}) or {}
        except Exception as e:
            print(f"Warning: failed to load KeyDB from {file_path}: {e}")
        return db

    def save(self, path: Optional[str] = None):
        file_path = Path(path) if path else self.default_file_path()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "Passcodes": self.passcodes,
            "EKPFS": self.ekpfs,
            "XTS": self.xts,
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_passcode(self, content_id: str) -> Optional[str]:
        return self.passcodes.get(content_id)

    def set_passcode(self, content_id: str, passcode: str):
        self.passcodes[content_id] = passcode

    def get_ekpfs(self, content_id: str) -> Optional[bytes]:
        hex_val = self.ekpfs.get(content_id)
        if hex_val:
            try:
                return bytes.fromhex(hex_val.replace(" ", "").replace(":", ""))
            except Exception:
                pass
        return None

    def set_ekpfs(self, content_id: str, ekpfs_bytes: bytes):
        self.ekpfs[content_id] = ekpfs_bytes.hex().upper()

    def get_xts(self, key_id: str) -> Optional[tuple[bytes, bytes]]:
        data = self.xts.get(key_id)
        if data and "Data" in data and "Tweak" in data:
            try:
                d = bytes.fromhex(data["Data"].replace(" ", ""))
                t = bytes.fromhex(data["Tweak"].replace(" ", ""))
                return d, t
            except Exception:
                pass
        return None

    def set_xts(self, key_id: str, data_bytes: bytes, tweak_bytes: bytes):
        self.xts[key_id] = {
            "Data": data_bytes.hex().upper(),
            "Tweak": tweak_bytes.hex().upper(),
        }


# Global instance
_instance: Optional[KeyDB] = None


def get_keydb() -> KeyDB:
    global _instance
    if _instance is None:
        _instance = KeyDB.load()
    return _instance
