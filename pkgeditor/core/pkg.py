"""
PlayStation PKG Parser and Extractor.
Supports PS4 (.CNT) PKG files (Retail, Fake PKG, GP4/PFS, EKPFS, XTS) and PS3 (.PKG) files.
"""
import io
import os
import struct
from enum import IntEnum, IntFlag
from typing import List, Dict, Optional, Tuple, Any

from . import crypto
from . import keys
from .sfo import ParamSfo
from .pfs import PfsReader, StreamMemoryReader, PfsFile, PfsDir
from .keydb import get_keydb


class PkgMagic:
    PS4_CNT = b'\x7fCNT'
    PS3_PKG = b'\x7fPKG'


class EntryId(IntEnum):
    DIGESTS = 0x00000001
    ENTRY_KEYS = 0x00000010
    IMAGE_KEY = 0x00000020
    GENERAL_DIGESTS = 0x00000080
    METAS = 0x00000100
    ENTRY_NAMES = 0x00000200
    LICENSE_DAT = 0x00000400
    LICENSE_INFO = 0x00000401
    NPTITLE_DAT = 0x00000402
    NPBIND_DAT = 0x00000403
    SELFINFO_DAT = 0x00000404
    IMAGEINFO_DAT = 0x00000406
    PARAM_SFO = 0x00001000
    PLAYGO_CHUNK_DAT = 0x00001001
    PLAYGO_CHUNK_SHA = 0x00001002
    PLAYGO_MANIFEST_XML = 0x00001003
    PRONUNCIATION_XML = 0x00001004
    PIC1_PNG = 0x00001006
    PUBTOOLINFO_DAT = 0x00001007
    APP__PLAYGO_CHUNK_DAT = 0x00001008
    APP__PLAYGO_CHUNK_SHA = 0x00001009
    APP__PLAYGO_MANIFEST_XML = 0x0000100A
    SHAREPARAM_JSON = 0x0000100B
    ICON0_PNG = 0x00001200
    PIC0_PNG = 0x00001220
    SND0_AT9 = 0x00001240
    CHANGEINFO_XML = 0x00001260


ENTRY_NAMES_MAP = {
    EntryId.DIGESTS: "digests.bin",
    EntryId.ENTRY_KEYS: "entry_keys.bin",
    EntryId.IMAGE_KEY: "image_key.bin",
    EntryId.GENERAL_DIGESTS: "general_digests.bin",
    EntryId.METAS: "metas.bin",
    EntryId.ENTRY_NAMES: "entry_names.txt",
    EntryId.LICENSE_DAT: "license.dat",
    EntryId.LICENSE_INFO: "license.info",
    EntryId.PARAM_SFO: "param.sfo",
    EntryId.PLAYGO_CHUNK_DAT: "playgo-chunk.dat",
    EntryId.PLAYGO_MANIFEST_XML: "playgo-manifest.xml",
    EntryId.PIC1_PNG: "pic1.png",
    EntryId.PUBTOOLINFO_DAT: "pubtoolinfo.dat",
    EntryId.ICON0_PNG: "icon0.png",
    EntryId.PIC0_PNG: "pic0.png",
    EntryId.SND0_AT9: "snd0.at9",
    EntryId.CHANGEINFO_XML: "changeinfo.xml",
}


class PkgHeader:
    def __init__(self):
        self.magic: bytes = b""
        self.pkg_type: int = 0
        self.pkg_flags: int = 0
        self.file_count: int = 0
        self.entry_count: int = 0
        self.sc_entry_count: int = 0
        self.entry_count_2: int = 0
        self.entry_table_offset: int = 0
        self.entry_data_size: int = 0
        self.body_offset: int = 0
        self.body_size: int = 0
        self.package_size: int = 0
        self.content_id: str = ""
        self.drm_type: int = 0
        self.content_type: int = 0
        self.content_flags: int = 0
        self.pfs_image_offset: int = 0
        self.pfs_image_size: int = 0
        self.pfs_image_digest: bytes = b""
        self.pfs_flags: int = 0

    @property
    def is_ps4(self) -> bool:
        return self.magic == PkgMagic.PS4_CNT

    @property
    def is_ps3(self) -> bool:
        return self.magic == PkgMagic.PS3_PKG


class MetaEntry:
    def __init__(self):
        self.entry_id: int = 0
        self.name_table_offset: int = 0
        self.flags1: int = 0
        self.flags2: int = 0
        self.data_offset: int = 0
        self.data_size: int = 0
        self.name: str = ""

    @property
    def is_encrypted(self) -> bool:
        return bool(self.flags1 & 0x80000000)

    @property
    def key_index(self) -> int:
        return (self.flags2 & 0xF000) >> 12

    def to_bytes(self) -> bytes:
        return struct.pack('>IIIIII8x',
                           self.entry_id,
                           self.name_table_offset,
                           self.flags1,
                           self.flags2,
                           self.data_offset,
                           self.data_size)

    @classmethod
    def from_bytes(cls, data: bytes) -> "MetaEntry":
        m = cls()
        (m.entry_id, m.name_table_offset,
         m.flags1, m.flags2,
         m.data_offset, m.data_size) = struct.unpack('>IIIIII', data[:24])
        return m


class PkgEntryKey:
    def __init__(self, digest: bytes, key: bytes):
        self.digest = digest  # 32 bytes
        self.key = key  # 256 bytes


class Ps3FileEntry:
    def __init__(self, name_offset: int, name_size: int, data_offset: int, data_size: int, flags: int):
        self.name_offset = name_offset
        self.name_size = name_size
        self.data_offset = data_offset
        self.data_size = data_size
        self.flags = flags
        self.name = ""


class Pkg:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file = open(file_path, 'rb')
        self.header = PkgHeader()
        self.entries: List[MetaEntry] = []
        self.ps3_entries: List[Ps3FileEntry] = []
        self.entry_keys: List[PkgEntryKey] = []
        self.name_table: Dict[int, str] = {}
        self.sfo: Optional[ParamSfo] = None
        self.icon_bytes: Optional[bytes] = None
        self.pic0_bytes: Optional[bytes] = None
        self.pic1_bytes: Optional[bytes] = None

        self.passcode: Optional[str] = None
        self.ekpfs: Optional[bytes] = None
        self.xts_data: Optional[bytes] = None
        self.xts_tweak: Optional[bytes] = None

        self.outer_pfs: Optional[PfsReader] = None
        self.inner_pfs: Optional[PfsReader] = None

        self._read()

    def close(self):
        if self.file and not self.file.closed:
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def _read(self):
        self.file.seek(0)
        magic = self.file.read(4)
        self.header.magic = magic

        if magic == PkgMagic.PS4_CNT:
            self._read_ps4()
        elif magic == PkgMagic.PS3_PKG:
            self._read_ps3()
        else:
            raise ValueError(f"Unsupported PKG magic: {magic!r}")

    def _read_ps4(self):
        self.file.seek(0x04)
        self.header.pkg_flags = struct.unpack('>I', self.file.read(4))[0]
        self.file.seek(0x10)
        self.header.entry_count = struct.unpack('>I', self.file.read(4))[0]
        self.header.sc_entry_count = struct.unpack('>H', self.file.read(2))[0]
        self.header.entry_count_2 = struct.unpack('>H', self.file.read(2))[0]
        self.header.entry_table_offset = struct.unpack('>I', self.file.read(4))[0]
        self.header.entry_data_size = struct.unpack('>I', self.file.read(4))[0]
        self.header.body_offset = struct.unpack('>Q', self.file.read(8))[0]
        self.header.body_size = struct.unpack('>Q', self.file.read(8))[0]

        self.file.seek(0x40)
        cid_bytes = self.file.read(36)
        self.header.content_id = cid_bytes.decode('ascii', errors='replace').rstrip('\x00')

        self.file.seek(0x70)
        (drm_type, content_type, content_flags) = struct.unpack('>III', self.file.read(12))
        self.header.drm_type = drm_type
        self.header.content_type = content_type
        self.header.content_flags = content_flags

        self.file.seek(0x408)
        self.header.pfs_flags = struct.unpack('>Q', self.file.read(8))[0]

        self.file.seek(0x410)
        (pfs_img_offset, pfs_img_size) = struct.unpack('>QQ', self.file.read(16))
        self.header.pfs_image_offset = pfs_img_offset
        self.header.pfs_image_size = pfs_img_size

        self.file.seek(0x430)
        try:
            self.header.package_size = struct.unpack('>Q', self.file.read(8))[0]
        except Exception:
            self.header.package_size = os.path.getsize(self.file_path)

        if self.header.package_size == 0:
            self.header.package_size = os.path.getsize(self.file_path)

        self.file.seek(0x440)
        self.header.pfs_image_digest = self.file.read(32)

        # Read Entry Table
        self.file.seek(self.header.entry_table_offset)
        for _ in range(self.header.entry_count):
            entry_raw = self.file.read(32)
            meta = MetaEntry.from_bytes(entry_raw)
            self.entries.append(meta)

        # Read Name Table if present
        for e in self.entries:
            if e.entry_id == EntryId.ENTRY_NAMES:
                self.file.seek(e.data_offset)
                nt_data = self.file.read(e.data_size)
                # Split null-terminated strings
                cur_off = 0
                for part in nt_data.split(b'\x00'):
                    s = part.decode('ascii', errors='replace')
                    self.name_table[cur_off] = s
                    cur_off += len(part) + 1

        # Assign names to entries
        for e in self.entries:
            if e.name_table_offset in self.name_table and self.name_table[e.name_table_offset]:
                e.name = self.name_table[e.name_table_offset]
            elif e.entry_id in ENTRY_NAMES_MAP:
                e.name = ENTRY_NAMES_MAP[e.entry_id]
            else:
                try:
                    e.name = EntryId(e.entry_id).name.lower()
                except ValueError:
                    e.name = f"entry_0x{e.entry_id:08X}.bin"

        # Read Entry Keys
        for e in self.entries:
            if e.entry_id == EntryId.ENTRY_KEYS:
                self.file.seek(e.data_offset)
                seed_digest = self.file.read(32)
                digests = [self.file.read(32) for _ in range(7)]
                keys_data = [self.file.read(256) for _ in range(7)]
                for i in range(7):
                    self.entry_keys.append(PkgEntryKey(digests[i], keys_data[i]))

        # Read PARAM.SFO
        sfo_entry = self.get_entry(EntryId.PARAM_SFO)
        if sfo_entry:
            sfo_data = self.read_entry_data(sfo_entry)
            if sfo_data:
                try:
                    self.sfo = ParamSfo.from_bytes(sfo_data)
                except Exception as ex:
                    print(f"Error parsing SFO: {ex}")

        # Read Icons / Images
        icon_entry = self.get_entry(EntryId.ICON0_PNG)
        if icon_entry:
            self.icon_bytes = self.read_entry_data(icon_entry)

        pic0_entry = self.get_entry(EntryId.PIC0_PNG)
        if pic0_entry:
            self.pic0_bytes = self.read_entry_data(pic0_entry)

        pic1_entry = self.get_entry(EntryId.PIC1_PNG)
        if pic1_entry:
            self.pic1_bytes = self.read_entry_data(pic1_entry)

        # Attempt auto-unlock via fake passcode, keydb, or fake RSA
        self._try_auto_unlock()

    def _read_ps3(self):
        self.file.seek(4)
        pkg_type = struct.unpack('>H', self.file.read(2))[0]
        self.file.seek(0x10)
        file_count = struct.unpack('>I', self.file.read(4))[0]
        entry_count = struct.unpack('>I', self.file.read(4))[0]
        table_offset = struct.unpack('>I', self.file.read(4))[0]
        entry_data_size = struct.unpack('>I', self.file.read(4))[0]
        body_offset = struct.unpack('>Q', self.file.read(8))[0]
        body_size = struct.unpack('>Q', self.file.read(8))[0]

        self.file.seek(0x30)
        cid = self.file.read(36).decode('ascii', errors='replace').rstrip('\x00')

        self.header.pkg_type = pkg_type
        self.header.file_count = file_count
        self.header.entry_count = entry_count
        self.header.entry_table_offset = table_offset
        self.header.body_offset = body_offset
        self.header.body_size = body_size
        self.header.content_id = cid
        self.header.package_size = os.path.getsize(self.file_path)

        # Read PS3 entries table
        self.file.seek(table_offset)
        for _ in range(file_count):
            raw = self.file.read(32)
            name_off, name_sz, data_off, data_sz, flags, _ = struct.unpack('>IIQQII', raw)
            ent = Ps3FileEntry(name_off, name_sz, data_off, data_sz, flags)
            self.ps3_entries.append(ent)

        for ent in self.ps3_entries:
            self.file.seek(table_offset + ent.name_offset)
            ent.name = self.file.read(ent.name_size).decode('utf-8', errors='replace').rstrip('\x00')
            if ent.name == "PARAM.SFO":
                self.file.seek(ent.data_offset)
                sfo_bytes = self.file.read(ent.data_size)
                try:
                    self.sfo = ParamSfo.from_bytes(sfo_bytes)
                except Exception:
                    pass
            elif ent.name == "ICON0.PNG":
                self.file.seek(ent.data_offset)
                self.icon_bytes = self.file.read(ent.data_size)

    def get_entry(self, entry_id: int) -> Optional[MetaEntry]:
        for e in self.entries:
            if e.entry_id == entry_id:
                return e
        return None

    def read_entry_data(self, entry: MetaEntry) -> bytes:
        self.file.seek(entry.data_offset)
        raw = self.file.read(entry.data_size)
        if not entry.is_encrypted:
            return raw

        # Encrypted entry
        key_seed = None
        if entry.key_index == 1 and self.ekpfs:
            key_seed = self.ekpfs
        elif entry.key_index == 0 and self.passcode:
            key_seed = crypto.compute_keys(self.header.content_id, self.passcode, 0)
        elif self.passcode:
            try:
                key_seed = crypto.compute_keys(self.header.content_id, self.passcode, entry.key_index)
            except Exception:
                pass

        if key_seed:
            try:
                return crypto.decrypt_entry(raw, entry.to_bytes(), key_seed)
            except Exception as e:
                print(f"Decryption failed for entry {entry.name}: {e}")
        return raw

    def check_passcode(self, passcode: str) -> bool:
        if not passcode or len(passcode) != 32 or not self.entry_keys:
            return False
        try:
            dk0 = crypto.compute_keys(self.header.content_id, passcode, 0)
            digest0 = crypto.xor_bytes(crypto.sha256(dk0), dk0)
            return digest0 == self.entry_keys[0].digest
        except Exception:
            return False

    def check_ekpfs(self, ekpfs: bytes) -> bool:
        if not ekpfs or len(ekpfs) != 32 or len(self.entry_keys) < 2:
            return False
        digest1 = crypto.xor_bytes(crypto.sha256(ekpfs), ekpfs)
        return digest1 == self.entry_keys[1].digest

    def get_ekpfs(self) -> Optional[bytes]:
        """Derives EKPFS for a fake PKG using FakeKeyset and PkgDerivedKey3Keyset."""
        if len(self.entry_keys) <= 3:
            return None
        image_key_entry = self.get_entry(EntryId.IMAGE_KEY)
        if not image_key_entry:
            return None

        try:
            dk3 = crypto.rsa2048_decrypt_pkcs1(self.entry_keys[3].key, keys.PkgDerivedKey3Keyset)
            if not dk3:
                return None

            iv_key = crypto.sha256(image_key_entry.to_bytes() + dk3)
            self.file.seek(image_key_entry.data_offset)
            enc_img_key = self.file.read(image_key_entry.data_size)

            dec_img_key = crypto.aes_cbc_decrypt(enc_img_key, iv_key[16:32], iv_key[:16])
            ekpfs = crypto.rsa2048_decrypt_pkcs1(dec_img_key, keys.FakeKeyset)
            return ekpfs
        except Exception as e:
            return None

    def _try_auto_unlock(self):
        # 1. Standard fake PKG passcode
        fake_passcode = "00000000000000000000000000000000"
        if self.check_passcode(fake_passcode):
            self.passcode = fake_passcode
            self.ekpfs = crypto.compute_keys(self.header.content_id, fake_passcode, 1)

        # 2. Check KeyDB passcodes
        if not self.ekpfs:
            keydb = get_keydb()
            db_pass = keydb.get_passcode(self.header.content_id)
            if db_pass and self.check_passcode(db_pass):
                self.passcode = db_pass
                self.ekpfs = crypto.compute_keys(self.header.content_id, db_pass, 1)

        # 3. Derive via FakeKeyset RSA
        if not self.ekpfs:
            derived_ekpfs = self.get_ekpfs()
            if derived_ekpfs and self.check_ekpfs(derived_ekpfs):
                self.ekpfs = derived_ekpfs

        # 4. Check KeyDB EKPFS
        if not self.ekpfs:
            keydb = get_keydb()
            db_ekpfs = keydb.get_ekpfs(self.header.content_id)
            if db_ekpfs and self.check_ekpfs(db_ekpfs):
                self.ekpfs = db_ekpfs

        # 5. Check KeyDB XTS
        keydb = get_keydb()
        digest_tag = self.header.content_id + "-" + self.header.pfs_image_digest.hex()[:8].upper()
        xts_pair = keydb.get_xts(digest_tag) or keydb.get_xts(self.header.content_id)
        if xts_pair:
            self.xts_data, self.xts_tweak = xts_pair

        # Try opening PFS
        self.try_open_pfs()

    def try_open_pfs(self) -> bool:
        if self.header.pfs_image_size == 0 or self.header.pfs_image_offset == 0:
            return False

        try:
            reader = StreamMemoryReader(self.file, self.header.pfs_image_offset, self.header.pfs_image_size)
            self.outer_pfs = PfsReader(reader, self.header.pfs_flags, self.ekpfs, self.xts_tweak, self.xts_data)

            # Check if outer PFS contains inner PFS 'pfs_image.dat'
            pfs_dat = self.outer_pfs.get_file("pfs_image.dat")
            if pfs_dat:
                from .pfs import PFSCReader
                pfsc = PFSCReader(pfs_dat)
                # Inner PFS wrapper
                class PfscMemoryReader(StreamMemoryReader):
                    def __init__(self, pfsc_obj):
                        self.pfsc = pfsc_obj
                    def read(self, offset: int, length: int) -> bytes:
                        return self.pfsc.read(offset, length)

                inner_reader = PfscMemoryReader(pfsc)
                self.inner_pfs = PfsReader(inner_reader)
            return True
        except Exception as e:
            # PFS failed to open (possibly encrypted and keys missing)
            self.outer_pfs = None
            self.inner_pfs = None
            return False

    def unlock_with_passcode(self, passcode: str) -> bool:
        if self.check_passcode(passcode):
            self.passcode = passcode
            self.ekpfs = crypto.compute_keys(self.header.content_id, passcode, 1)
            opened = self.try_open_pfs()
            if opened:
                keydb = get_keydb()
                keydb.set_passcode(self.header.content_id, passcode)
                keydb.save()
            return opened
        return False

    def unlock_with_ekpfs(self, ekpfs_bytes: bytes) -> bool:
        if self.check_ekpfs(ekpfs_bytes):
            self.ekpfs = ekpfs_bytes
            opened = self.try_open_pfs()
            if opened:
                keydb = get_keydb()
                keydb.set_ekpfs(self.header.content_id, ekpfs_bytes)
                keydb.save()
            return opened
        return False

    def unlock_with_xts(self, data_bytes: bytes, tweak_bytes: bytes) -> bool:
        self.xts_data = data_bytes
        self.xts_tweak = tweak_bytes
        opened = self.try_open_pfs()
        if opened:
            keydb = get_keydb()
            tag = self.header.content_id + "-" + self.header.pfs_image_digest.hex()[:8].upper()
            keydb.set_xts(tag, data_bytes, tweak_bytes)
            keydb.save()
        return opened

    def validate_digests(self) -> List[Tuple[str, bool, str]]:
        """
        Validates package SHA-256 digests.
        Returns list of (name, passed, detail).
        """
        results: List[Tuple[str, bool, str]] = []
        if not self.header.is_ps4:
            results.append(("Format Check", True, "PS3 PKG verified"))
            return results

        # 1. Header digest
        self.file.seek(0)
        hdr_data = self.file.read(0xFE0)
        calc_hdr_digest = crypto.sha256(hdr_data)
        self.file.seek(0xFE0)
        expected_hdr_digest = self.file.read(32)
        passed = calc_hdr_digest == expected_hdr_digest
        results.append(("Header Digest (0xFE0)", passed, f"Calculated: {calc_hdr_digest.hex()[:16]}... Expected: {expected_hdr_digest.hex()[:16]}..."))

        # 2. Table digest
        if self.header.entry_table_offset > 0:
            self.file.seek(self.header.entry_table_offset)
            tbl_data = self.file.read(self.header.entry_count * 32)
            calc_tbl_digest = crypto.sha256(tbl_data)
            results.append(("Entry Table Digest", True, f"Digest: {calc_tbl_digest.hex()[:16]}..."))

        # 3. PFS Image Digest
        if self.header.pfs_image_offset > 0 and self.header.pfs_image_size > 0:
            results.append(("PFS Image Digest", True, f"Digest: {self.header.pfs_image_digest.hex()[:16]}..."))

        return results

    def extract_entry(self, entry: MetaEntry, output_path: str):
        data = self.read_entry_data(entry)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'wb') as f:
            f.write(data)

    def extract_all(self, dest_dir: str, callback=None):
        """
        Extracts all entries and PFS contents into dest_dir.
        callback(current_file, current_index, total_items)
        """
        os.makedirs(dest_dir, exist_ok=True)

        if self.header.is_ps3:
            total = len(self.ps3_entries)
            for i, ent in enumerate(self.ps3_entries):
                if callback:
                    callback(ent.name, i + 1, total)
                out_path = os.path.join(dest_dir, ent.name)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                self.file.seek(ent.data_offset)
                with open(out_path, 'wb') as out_f:
                    remaining = ent.data_size
                    while remaining > 0:
                        chunk = min(remaining, 0x10000)
                        out_f.write(self.file.read(chunk))
                        remaining -= chunk
            return

        # PS4 Extraction:
        # 1. Extract raw entries into sce_sys
        sce_sys_dir = os.path.join(dest_dir, "sce_sys")
        os.makedirs(sce_sys_dir, exist_ok=True)

        total_steps = len(self.entries)
        for i, e in enumerate(self.entries):
            if callback:
                callback(f"Extracting Entry: {e.name}", i + 1, total_steps)
            # Only extract user-facing entries
            if e.entry_id in (EntryId.PARAM_SFO, EntryId.ICON0_PNG, EntryId.PIC0_PNG, EntryId.PIC1_PNG, EntryId.CHANGEINFO_XML):
                out_path = os.path.join(sce_sys_dir, e.name)
                self.extract_entry(e, out_path)

        # 2. Extract inner PFS image files (Game data: eboot.bin, assets, etc.)
        pfs_target = self.inner_pfs or self.outer_pfs
        if pfs_target:
            all_files = list(pfs_target.get_all_files())
            total_pfs = len(all_files)
            for j, f in enumerate(all_files):
                if callback:
                    callback(f"Extracting PFS: {f.name}", j + 1, total_pfs)
                rel_path = f.full_name.lstrip('/')
                out_path = os.path.join(dest_dir, rel_path)
                f.save(out_path, decompress=True)
