"""
PkgEditor Test Suite
Tests SFO, GP4, KeyDB, Crypto, and PKG operations.
"""
import os
import tempfile
import struct
import unittest

from pkgeditor.core.sfo import ParamSfo, SfoEntryType
from pkgeditor.core.gp4 import Gp4Project
from pkgeditor.core.keydb import KeyDB
from pkgeditor.core import crypto
from pkgeditor.core.merger import PkgMerger
from pkgeditor.core.pkg import Pkg, PkgHeader, MetaEntry, PkgMagic, EntryId


class TestPkgEditor(unittest.TestCase):
    def test_sfo_roundtrip(self):
        sfo = ParamSfo.create_template_gd(title="Test Adventure", title_id="CUSA99999", content_id="UP0001-CUSA99999_00-0000000000000000")
        sfo["CUSTOM_INT"] = 1337
        sfo["CUSTOM_STR"] = "Hello World"
        
        raw = sfo.to_bytes()
        self.assertTrue(raw.startswith(b'\x00PSF'))

        loaded = ParamSfo.from_bytes(raw)
        self.assertEqual(loaded["TITLE"], "Test Adventure")
        self.assertEqual(loaded["TITLE_ID"], "CUSA99999")
        self.assertEqual(loaded["CUSTOM_INT"], 1337)
        self.assertEqual(loaded["CUSTOM_STR"], "Hello World")
        self.assertEqual(loaded["CATEGORY"], "gd")

    def test_gp4_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            proj = Gp4Project.create(content_id="UP0001-CUSA11111_00-0000000000000000")
            
            # Missing files should give errors
            results = proj.validate(tmpdir)
            has_error = any(lvl == "Error" for lvl, _ in results)
            self.assertTrue(has_error)

            # Create sce_sys/param.sfo
            sce_sys = os.path.join(tmpdir, "sce_sys")
            os.makedirs(sce_sys, exist_ok=True)
            sfo_path = os.path.join(sce_sys, "param.sfo")
            with open(sfo_path, "wb") as f:
                f.write(ParamSfo.create_template_gd().to_bytes())

            proj.add_file("sce_sys/param.sfo", "sce_sys/param.sfo")
            gp4_file = os.path.join(tmpdir, "test.gp4")
            proj.write_to(gp4_file)

            loaded = Gp4Project.read_from(gp4_file)
            self.assertEqual(loaded.content_id, "UP0001-CUSA11111_00-0000000000000000")
            self.assertEqual(len(loaded.files), 1)

    def test_crypto_functions(self):
        cid = "UP0001-CUSA00001_00-0000000000000000"
        passcode = "00000000000000000000000000000000"
        dk0 = crypto.compute_keys(cid, passcode, 0)
        self.assertEqual(len(dk0), 32)

        dk1 = crypto.compute_keys(cid, passcode, 1)
        self.assertEqual(len(dk1), 32)
        self.assertNotEqual(dk0, dk1)

        keystone = crypto.create_keystone(passcode)
        self.assertTrue(keystone.startswith(b'keystone'))
        self.assertEqual(len(keystone), 96)

    def test_keydb(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_keydb.json")
            db = KeyDB()
            db.set_passcode("TEST-CONTENT-ID-01234567890123456789", "12345678901234567890123456789012")
            db.set_ekpfs("TEST-CONTENT-ID-01234567890123456789", b"\xAA" * 32)
            db.set_xts("TEST-KEY", b"\x11" * 16, b"\x22" * 16)
            db.save(db_path)

            loaded = KeyDB.load(db_path)
            self.assertEqual(loaded.get_passcode("TEST-CONTENT-ID-01234567890123456789"), "12345678901234567890123456789012")
            self.assertEqual(loaded.get_ekpfs("TEST-CONTENT-ID-01234567890123456789"), b"\xAA" * 32)
            xts = loaded.get_xts("TEST-KEY")
            self.assertIsNotNone(xts)
            self.assertEqual(xts[0], b"\x11" * 16)
            self.assertEqual(xts[1], b"\x22" * 16)

    def test_merger(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p0 = os.path.join(tmpdir, "game_0.pkg")
            p1 = os.path.join(tmpdir, "game_1.pkg")
            out = os.path.join(tmpdir, "game.pkg")

            with open(p0, "wb") as f:
                f.write(b"PART0_DATA" * 100)
            with open(p1, "wb") as f:
                f.write(b"PART1_DATA" * 100)

            parts = PkgMerger.get_parts(p0)
            self.assertEqual(len(parts), 2)
            PkgMerger.merge(parts, out)
            self.assertEqual(os.path.getsize(out), os.path.getsize(p0) + os.path.getsize(p1))

    def test_pkg_read_and_extract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_path = os.path.join(tmpdir, "test.pkg")
            sfo_data = ParamSfo.create_template_gd(title="Synthetic Game", title_id="CUSA12345").to_bytes()
            icon_data = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
            
            table_offset = 0x2000
            sfo_offset = 0x3000
            icon_offset = sfo_offset + len(sfo_data)
            entry_count = 2

            with open(pkg_path, "wb") as f:
                hdr = bytearray(0x2000)
                hdr[0:4] = PkgMagic.PS4_CNT
                struct.pack_into(">I", hdr, 0x04, 0x80000000)
                struct.pack_into(">I", hdr, 0x10, entry_count)
                struct.pack_into(">H", hdr, 0x14, 0)
                struct.pack_into(">H", hdr, 0x16, entry_count)
                struct.pack_into(">I", hdr, 0x18, table_offset)
                struct.pack_into(">I", hdr, 0x1C, entry_count * 32)
                struct.pack_into(">Q", hdr, 0x20, 0x3000)
                struct.pack_into(">Q", hdr, 0x28, len(sfo_data) + len(icon_data))
                
                cid = b"UP0001-CUSA12345_00-0000000000000000"
                hdr[0x40:0x40+len(cid)] = cid
                
                hdr_digest = crypto.sha256(bytes(hdr[:0xFE0]))
                hdr[0xFE0:0xFE0+32] = hdr_digest
                f.write(hdr)

                e0 = struct.pack(">IIIIII8x", EntryId.PARAM_SFO, 0, 0, 0, sfo_offset, len(sfo_data))
                e1 = struct.pack(">IIIIII8x", EntryId.ICON0_PNG, 0, 0, 0, icon_offset, len(icon_data))
                f.write(e0 + e1)

                f.write(b"\x00" * (sfo_offset - f.tell()))
                f.write(sfo_data)
                f.write(icon_data)

            with Pkg(pkg_path) as p:
                self.assertTrue(p.header.is_ps4)
                self.assertEqual(p.header.content_id, "UP0001-CUSA12345_00-0000000000000000")
                self.assertIsNotNone(p.sfo)
                self.assertEqual(p.sfo["TITLE"], "Synthetic Game")
                self.assertEqual(p.icon_bytes, icon_data)

                extract_dir = os.path.join(tmpdir, "extracted")
                p.extract_all(extract_dir)

                sfo_out = os.path.join(extract_dir, "sce_sys", "param.sfo")
                self.assertTrue(os.path.exists(sfo_out))
                loaded_sfo = ParamSfo.from_file(sfo_out)
                self.assertEqual(loaded_sfo["TITLE"], "Synthetic Game")

                v = p.validate_digests()
                self.assertTrue(v[0][1])


if __name__ == "__main__":
    unittest.main()

