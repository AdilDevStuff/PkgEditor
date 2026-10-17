"""
PlayStation 4 GP4 Project Parser, Generator and Validator.
Handles Sony-compatible .gp4 project XML files.
"""
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional, Tuple


class Gp4File:
    def __init__(self, targpath: str, origpath: str):
        self.targpath = targpath.replace('\\', '/')
        self.origpath = origpath

    @property
    def filename(self) -> str:
        return self.targpath.split('/')[-1]

    def __repr__(self):
        return f"Gp4File({self.targpath!r}, {self.origpath!r})"


class Gp4Dir:
    def __init__(self, target_name: str, parent: Optional["Gp4Dir"] = None):
        self.target_name = target_name
        self.parent = parent
        self.children: List["Gp4Dir"] = []

    @property
    def full_path(self) -> str:
        if self.parent and self.parent.full_path:
            return f"{self.parent.full_path}/{self.target_name}"
        return self.target_name

    def find_child(self, name: str) -> Optional["Gp4Dir"]:
        for c in self.children:
            if c.target_name == name:
                return c
        return None

    def add_child(self, name: str) -> "Gp4Dir":
        existing = self.find_child(name)
        if existing:
            return existing
        child = Gp4Dir(name, self)
        self.children.append(child)
        return child

    def __repr__(self):
        return f"Gp4Dir({self.target_name!r}, children={len(self.children)})"


class Gp4Project:
    def __init__(self):
        self.format: str = "gp4"
        self.version: int = 1000
        self.volume_type: str = "pkg_ps4_app"
        self.volume_ts: str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.content_id: str = "UP0001-CUSA00001_00-0000000000000000"
        self.passcode: str = "00000000000000000000000000000000"
        self.creation_date: str = "actual_datetime"
        self.entitlement_key: Optional[str] = None
        self.files: List[Gp4File] = []
        self.root_dirs: List[Gp4Dir] = []

    @classmethod
    def create(cls, volume_type: str = "pkg_ps4_app", content_id: str = "UP0001-CUSA00001_00-0000000000000000", passcode: str = "00000000000000000000000000000000") -> "Gp4Project":
        proj = cls()
        proj.volume_type = volume_type
        proj.content_id = content_id
        proj.passcode = passcode
        if "ac" in volume_type:
            proj.entitlement_key = "00000000000000000000000000000000"
        return proj

    def add_file(self, origpath: str, targpath: str):
        targ = targpath.replace('\\', '/').lstrip('/')
        # Check if already exists, replace if so
        for f in self.files:
            if f.targpath == targ:
                f.origpath = origpath
                return
        self.files.append(Gp4File(targ, origpath))
        # Ensure directories exist in tree
        parts = targ.split('/')[:-1]
        self._ensure_dir_path(parts)

    def remove_file(self, targpath: str):
        targ = targpath.replace('\\', '/').lstrip('/')
        self.files = [f for f in self.files if f.targpath != targ]

    def _ensure_dir_path(self, parts: List[str]):
        if not parts:
            return
        curr_list = self.root_dirs
        parent = None
        for part in parts:
            found = None
            for d in curr_list:
                if d.target_name == part:
                    found = d
                    break
            if not found:
                found = Gp4Dir(part, parent)
                curr_list.append(found)
            parent = found
            curr_list = found.children

    @classmethod
    def read_from(cls, file_path: str) -> "Gp4Project":
        tree = ET.parse(file_path)
        root = tree.getroot()
        proj = cls()
        proj.format = root.get("fmt", "gp4")
        proj.version = int(root.get("version", "1000"))

        vol = root.find("volume")
        if vol is not None:
            v_type = vol.findtext("volume_type")
            if v_type:
                proj.volume_type = v_type
            v_ts = vol.findtext("volume_ts")
            if v_ts:
                proj.volume_ts = v_ts

            pkg = vol.find("package")
            if pkg is not None:
                proj.content_id = pkg.findtext("content_id", proj.content_id)
                proj.passcode = pkg.findtext("passcode", proj.passcode)
                proj.creation_date = pkg.findtext("creation_date", "actual_datetime")
                proj.entitlement_key = pkg.findtext("entitlement_key", None)

        # Parse files
        files_elem = root.find("files")
        if files_elem is not None:
            for f_elem in files_elem.findall("file"):
                targ = f_elem.get("targpath", "")
                orig = f_elem.get("origpath", "")
                if targ:
                    if not orig:
                        orig = targ
                    proj.files.append(Gp4File(targ, orig))

        # Parse rootdir
        rootdir_elem = root.find("rootdir")
        if rootdir_elem is not None:
            def parse_dir(elem, parent=None):
                d = Gp4Dir(elem.get("targname", ""), parent)
                for child_elem in elem.findall("dir"):
                    d.children.append(parse_dir(child_elem, d))
                return d

            for d_elem in rootdir_elem.findall("dir"):
                proj.root_dirs.append(parse_dir(d_elem, None))

        return proj

    def write_to(self, file_path: str):
        root = ET.Element("psproject", fmt=self.format, version=str(self.version))

        vol = ET.SubElement(root, "volume")
        vol_type = ET.SubElement(vol, "volume_type")
        vol_type.text = self.volume_type
        vol_ts = ET.SubElement(vol, "volume_ts")
        vol_ts.text = self.volume_ts

        pkg = ET.SubElement(vol, "package")
        passcode = ET.SubElement(pkg, "passcode")
        passcode.text = self.passcode
        cid = ET.SubElement(pkg, "content_id")
        cid.text = self.content_id
        cdate = ET.SubElement(pkg, "creation_date")
        cdate.text = self.creation_date
        if self.entitlement_key:
            ekey = ET.SubElement(pkg, "entitlement_key")
            ekey.text = self.entitlement_key

        chunk_info = ET.SubElement(vol, "chunk_info", chunk_count="1", scenario_count="1")
        chunks = ET.SubElement(chunk_info, "chunks")
        ET.SubElement(chunks, "chunk", id="0", layer_no="0", label="chunk0")
        scenarios = ET.SubElement(chunk_info, "scenarios", default_id="0")
        scen = ET.SubElement(scenarios, "scenario", id="0", type="sp", initial_chunk_count="1", label="scenario0")
        ET.SubElement(scen, "chunk_id", id="0")

        # Files
        files_elem = ET.SubElement(root, "files")
        for f in self.files:
            ET.SubElement(files_elem, "file", targpath=f.targpath, origpath=f.origpath)

        # Rootdir
        rootdir_elem = ET.SubElement(root, "rootdir")

        def write_dir(d: Gp4Dir, parent_elem: ET.Element):
            d_elem = ET.SubElement(parent_elem, "dir", targname=d.target_name)
            for c in d.children:
                write_dir(c, d_elem)

        for d in self.root_dirs:
            write_dir(d, rootdir_elem)

        # Pretty print indent
        self._indent_elem(root)
        tree = ET.ElementTree(root)
        with open(file_path, "wb") as f:
            f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
            tree.write(f, encoding="utf-8", xml_declaration=False)

    @staticmethod
    def _indent_elem(elem, level=0):
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for child in elem:
                Gp4Project._indent_elem(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    def validate(self, base_dir: str) -> List[Tuple[str, str]]:
        """
        Validates project files. Returns list of (level, message).
        level: 'Error', 'Warning', 'Info'
        """
        results: List[Tuple[str, str]] = []

        if len(self.content_id) != 36:
            results.append(("Error", f"Content ID must be exactly 36 characters (current: {len(self.content_id)})"))
        if len(self.passcode) != 32:
            results.append(("Error", f"Passcode must be exactly 32 characters (current: {len(self.passcode)})"))

        # Check required files
        targ_paths = {f.targpath for f in self.files}
        if "sce_sys/param.sfo" not in targ_paths:
            results.append(("Error", "Missing required file: sce_sys/param.sfo"))
        if "sce_sys/icon0.png" not in targ_paths:
            results.append(("Warning", "Missing recommended file: sce_sys/icon0.png"))

        # Check file existence
        for f in self.files:
            full_orig = os.path.join(base_dir, f.origpath) if not os.path.isabs(f.origpath) else f.origpath
            if not os.path.exists(full_orig):
                results.append(("Error", f"File does not exist: {f.origpath} -> {full_orig}"))

        if not results:
            results.append(("Info", "Project validated successfully! All files and metadata are valid."))

        return results

    @classmethod
    def generate_from_directory(cls, directory_path: str, volume_type: str = "pkg_ps4_app") -> "Gp4Project":
        """
        Scans an extracted game / application folder and creates a complete GP4 project.
        Reads param.sfo if present to get Content ID.
        """
        from .sfo import ParamSfo

        proj = cls.create(volume_type=volume_type)
        sfo_path = os.path.join(directory_path, "sce_sys", "param.sfo")
        if os.path.exists(sfo_path):
            try:
                sfo = ParamSfo.from_file(sfo_path)
                cid = sfo.get_entry("CONTENT_ID")
                if cid and cid.value:
                    proj.content_id = str(cid.value)
            except Exception:
                pass

        for root, dirs, files in os.walk(directory_path):
            rel_dir = os.path.relpath(root, directory_path).replace('\\', '/')
            if rel_dir == ".":
                rel_dir = ""

            for file in files:
                rel_file = f"{rel_dir}/{file}".lstrip('/')
                abs_orig = os.path.join(root, file)
                # Store relative origpath if possible
                orig = os.path.relpath(abs_orig, directory_path).replace('\\', '/')
                proj.add_file(orig, rel_file)

        return proj
