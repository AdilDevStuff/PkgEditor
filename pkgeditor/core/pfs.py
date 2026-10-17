"""
PlayStation File System (PFS) Parser and Extractor.
Supports Outer PFS, Inner PFS, XTS decryption, PFSC decompressor, and file tree browsing.
"""
import io
import struct
import zlib
from enum import IntEnum, IntFlag
from typing import List, Dict, Optional, Generator, Tuple

from . import crypto


class PfsMode(IntFlag):
    NONE = 0
    SIGNED = 0x1
    IS_64BIT = 0x2
    ENCRYPTED = 0x4
    UNKNOWN_ALWAYS = 0x8


class DirentType(IntEnum):
    FILE = 2
    DIRECTORY = 3
    DOT = 4
    DOT_DOT = 5


class PfsHeader:
    MAGIC = 20130315

    def __init__(self):
        self.version: int = 1
        self.magic: int = self.MAGIC
        self.id: int = 0
        self.fmode: int = 0
        self.clean: int = 0
        self.readonly: int = 0
        self.rsv: int = 0
        self.mode: PfsMode = PfsMode.UNKNOWN_ALWAYS
        self.unk1: int = 0
        self.block_size: int = 0x10000
        self.nbackup: int = 0
        self.nblock: int = 1
        self.dinode_count: int = 0
        self.ndblock: int = 0
        self.dinode_block_count: int = 0
        self.seed: Optional[bytes] = None

    @classmethod
    def read_from_stream(cls, stream: io.IOBase) -> "PfsHeader":
        start = stream.tell()
        data = stream.read(0x48)
        if len(data) < 0x48:
            raise ValueError("Truncated PFS header")

        (version, magic, id_, fmode, clean, readonly, rsv,
         mode_val, unk1, block_size, nbackup,
         nblock, dinode_count, ndblock, dinode_block_count) = struct.unpack('<qqqBBBBHHIIqqqq', data[:0x40])

        if version != 1 or magic != cls.MAGIC:
            raise ValueError(f"Invalid PFS magic: version={version}, magic={magic} (expected 1, {cls.MAGIC})")

        hdr = cls()
        hdr.version = version
        hdr.magic = magic
        hdr.id = id_
        hdr.fmode = fmode
        hdr.clean = clean
        hdr.readonly = readonly
        hdr.rsv = rsv
        hdr.mode = PfsMode(mode_val)
        hdr.unk1 = unk1
        hdr.block_size = block_size
        hdr.nbackup = nbackup
        hdr.nblock = nblock
        hdr.dinode_count = dinode_count
        hdr.ndblock = ndblock
        hdr.dinode_block_count = dinode_block_count

        # Check for seed at 0x370
        try:
            stream.seek(start + 0x370)
            seed = stream.read(16)
            if len(seed) == 16 and any(seed):
                hdr.seed = seed
        except Exception:
            pass

        return hdr


class Inode:
    def __init__(self):
        self.mode: int = 0
        self.nlink: int = 0
        self.flags: int = 0
        self.size: int = 0
        self.size_compressed: int = 0
        self.blocks: int = 0
        self.db: List[int] = []
        self.ib: List[int] = []

    @property
    def start_block(self) -> int:
        return self.db[0] if self.db else 0


def read_dinode_d32(stream: io.IOBase) -> Inode:
    data = stream.read(0xA8)
    if len(data) < 0xA8:
        raise ValueError("Truncated DinodeD32")
    (mode, nlink, flags, size, size_comp,
     t1, t2, t3, t4,
     tn1, tn2, tn3, tn4,
     uid, gid, unk1, unk2, blocks) = struct.unpack('<HHIIqqqqqIIIIIIII', data[:0x64])

    db = list(struct.unpack('<12i', data[0x64:0x94]))
    ib = list(struct.unpack('<5i', data[0x94:0xA8]))

    ino = Inode()
    ino.mode = mode
    ino.nlink = nlink
    ino.flags = flags
    ino.size = size
    ino.size_compressed = size_comp
    ino.blocks = blocks
    ino.db = db
    ino.ib = ib
    return ino


def read_dinode_s32(stream: io.IOBase) -> Inode:
    data = stream.read(0x2C8)
    if len(data) < 0x2C8:
        raise ValueError("Truncated DinodeS32")
    (mode, nlink, flags, size, size_comp,
     t1, t2, t3, t4,
     tn1, tn2, tn3, tn4,
     uid, gid, unk1, unk2, blocks) = struct.unpack('<HHIIqqqqqIIIIIIII', data[:0x64])

    # In DinodeS32, db has 12 block_sig (32 bytes sig + 4 bytes block = 36 bytes each)
    db = []
    pos = 0x64
    for _ in range(12):
        pos += 32
        blk = struct.unpack('<i', data[pos:pos + 4])[0]
        pos += 4
        db.append(blk)

    ib = []
    for _ in range(5):
        pos += 32
        blk = struct.unpack('<i', data[pos:pos + 4])[0]
        pos += 4
        ib.append(blk)

    ino = Inode()
    ino.mode = mode
    ino.nlink = nlink
    ino.flags = flags
    ino.size = size
    ino.size_compressed = size_comp
    ino.blocks = blocks
    ino.db = db
    ino.ib = ib
    return ino


class PfsDirent:
    def __init__(self, inode_num: int, type_: DirentType, name: str, ent_size: int):
        self.inode_number = inode_num
        self.type = type_
        self.name = name
        self.ent_size = ent_size

    @classmethod
    def read_from_stream(cls, stream: io.IOBase) -> Optional["PfsDirent"]:
        pos = stream.tell()
        head = stream.read(16)
        if len(head) < 16:
            return None
        ino_num, dtype_val, name_len, ent_size = struct.unpack('<IIII', head)
        if ent_size == 0 or name_len == 0:
            return None
        name_bytes = stream.read(name_len)
        name = name_bytes.rstrip(b'\x00').decode('ascii', errors='replace')
        stream.seek(pos + ent_size)
        try:
            dtype = DirentType(dtype_val)
        except ValueError:
            dtype = DirentType.FILE
        return cls(ino_num, dtype, name, ent_size)


class PfsNode:
    def __init__(self, name: str, parent: Optional["PfsDir"] = None):
        self.name = name
        self.parent = parent
        self.offset: int = 0
        self.size: int = 0
        self.compressed_size: int = 0
        self.ino: int = 0

    @property
    def full_name(self) -> str:
        if self.parent and self.parent.full_name:
            return f"{self.parent.full_name}/{self.name}"
        return self.name


class PfsDir(PfsNode):
    def __init__(self, name: str, parent: Optional["PfsDir"] = None):
        super().__init__(name, parent)
        self.children: List[PfsNode] = []

    def get(self, name: str) -> Optional[PfsNode]:
        for c in self.children:
            if c.name == name:
                return c
        return None

    def get_path(self, path: str) -> Optional[PfsNode]:
        parts = [p for p in path.split('/') if p]
        curr: Optional[PfsNode] = self
        for part in parts:
            if not isinstance(curr, PfsDir):
                return None
            curr = curr.get(part)
            if curr is None:
                return None
        return curr

    def get_all_files(self) -> Generator["PfsFile", None, None]:
        for c in self.children:
            if isinstance(c, PfsFile):
                yield c
            elif isinstance(c, PfsDir):
                yield from c.get_all_files()


class PfsFile(PfsNode):
    def __init__(self, reader: "BaseMemoryReader", name: str, parent: Optional[PfsDir] = None):
        super().__init__(name, parent)
        self.reader = reader
        self.blocks: Optional[List[int]] = None

    def read_chunk(self, offset: int, length: int) -> bytes:
        if self.blocks is not None:
            # Chunked access
            chunk_size = 0x10000
            buf = bytearray()
            pos = offset
            remaining = length
            while remaining > 0:
                blk_idx = pos // chunk_size
                blk_off = pos % chunk_size
                to_read = min(remaining, chunk_size - blk_off)
                if blk_idx < len(self.blocks):
                    real_blk = self.blocks[blk_idx]
                    chunk_data = self.reader.read(real_blk * chunk_size + blk_off, to_read)
                    buf.extend(chunk_data)
                else:
                    buf.extend(b'\x00' * to_read)
                pos += to_read
                remaining -= to_read
            return bytes(buf)
        return self.reader.read(self.offset + offset, length)

    def save(self, dest_path: str, decompress: bool = True):
        import os
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        # Check if PFSC compressed
        is_compressed = decompress and (self.size != self.compressed_size)
        if is_compressed:
            try:
                # Read header to check PFSC magic
                magic = self.read_chunk(0, 4)
                if magic == b'PFSC':
                    pfsc = PFSCReader(self)
                    with open(dest_path, 'wb') as f:
                        pos = 0
                        remaining = pfsc.data_length
                        while remaining > 0:
                            chunk = min(remaining, 0x10000)
                            data = pfsc.read(pos, chunk)
                            f.write(data)
                            pos += chunk
                            remaining -= chunk
                    return
            except Exception:
                pass

        # Uncompressed or raw save
        with open(dest_path, 'wb') as f:
            pos = 0
            remaining = self.size
            while remaining > 0:
                chunk = min(remaining, 0x10000)
                data = self.read_chunk(pos, chunk)
                f.write(data)
                pos += chunk
                remaining -= chunk


class BaseMemoryReader:
    def read(self, offset: int, length: int) -> bytes:
        raise NotImplementedError


class StreamMemoryReader(BaseMemoryReader):
    def __init__(self, stream: io.IOBase, base_offset: int = 0, size: int = 0):
        self.stream = stream
        self.base_offset = base_offset
        self.size = size

    def read(self, offset: int, length: int) -> bytes:
        self.stream.seek(self.base_offset + offset)
        return self.stream.read(length)


class XtsMemoryReader(BaseMemoryReader):
    def __init__(self, underlying: BaseMemoryReader, data_key: bytes, tweak_key: bytes,
                 start_sector: int = 16, sector_size: int = 0x1000):
        self.underlying = underlying
        self.data_key = data_key
        self.tweak_key = tweak_key
        self.start_sector = start_sector
        self.sector_size = sector_size

    def read(self, offset: int, length: int) -> bytes:
        start_sec = offset // self.sector_size
        end_sec = (offset + length + self.sector_size - 1) // self.sector_size
        buf = bytearray()

        for sec in range(start_sec, end_sec):
            sec_offset = sec * self.sector_size
            raw_sector = self.underlying.read(sec_offset, self.sector_size)
            if len(raw_sector) < self.sector_size:
                raw_sector = raw_sector.ljust(self.sector_size, b'\x00')

            if sec >= self.start_sector:
                decrypted = crypto.decrypt_pfs_sector_xts(raw_sector, sec, self.data_key, self.tweak_key)
            else:
                decrypted = raw_sector

            buf.extend(decrypted)

        rel_start = offset - (start_sec * self.sector_size)
        return bytes(buf[rel_start:rel_start + length])


class PFSCReader:
    MAGIC = 0x43534650  # 'PFSC' in LE

    def __init__(self, file_source: PfsFile):
        self.source = file_source
        hdr_data = file_source.read_chunk(0, 0x30)
        if len(hdr_data) < 0x30:
            raise ValueError("Truncated PFSC header")

        (magic, unk4, unk8, block_sz, block_sz2,
         block_offsets, data_start, data_length) = struct.unpack('<iiiqqqqq', hdr_data[:0x30])

        if magic != self.MAGIC:
            raise ValueError("Missing PFSC magic")

        self.block_sz = block_sz
        self.block_sz2 = block_sz2
        self.block_offsets_pos = block_offsets
        self.data_start = data_start
        self.data_length = data_length

        num_blocks = int(data_length // block_sz2)
        # Read sector map
        map_bytes = file_source.read_chunk(block_offsets, (num_blocks + 1) * 8)
        self.sector_map = list(struct.unpack(f'<{num_blocks + 1}q', map_bytes))

    def read_sector(self, idx: int) -> bytes:
        if idx < 0 or idx >= len(self.sector_map) - 1:
            raise IndexError("Sector index out of range")
        sector_offset = self.sector_map[idx]
        sector_size = self.sector_map[idx + 1] - sector_offset

        if sector_size == self.block_sz:
            return self.source.read_chunk(sector_offset, self.block_sz)
        elif sector_size > self.block_sz:
            return b'\x00' * self.block_sz
        else:
            # Compressed: first 2 bytes are zlib header
            compressed_bytes = self.source.read_chunk(sector_offset, sector_size)
            try:
                # Try raw deflate first (skipping 2-byte header)
                return zlib.decompress(compressed_bytes[2:], -zlib.MAX_WBITS)
            except Exception:
                try:
                    return zlib.decompress(compressed_bytes)
                except Exception:
                    return b'\x00' * self.block_sz

    def read(self, offset: int, length: int) -> bytes:
        if offset + length > self.data_length:
            length = max(0, self.data_length - offset)
        if length == 0:
            return b""

        buf = bytearray()
        cur_offset = offset
        rem = length
        while rem > 0:
            sec_idx = cur_offset // self.block_sz
            sec_off = cur_offset % self.block_sz
            to_read = min(rem, self.block_sz - sec_off)
            sec_data = self.read_sector(sec_idx)
            buf.extend(sec_data[sec_off:sec_off + to_read])
            cur_offset += to_read
            rem -= to_read

        return bytes(buf)


class PfsReader:
    def __init__(self, reader: BaseMemoryReader, pfs_flags: int = 0,
                 ekpfs: Optional[bytes] = None, tweak: Optional[bytes] = None, data: Optional[bytes] = None):
        self.reader = reader
        header_bytes = reader.read(0, 0x400)
        self.header = PfsHeader.read_from_stream(io.BytesIO(header_bytes))

        # Check encryption
        if self.header.mode & PfsMode.ENCRYPTED:
            xts_sector_size = 0x1000
            xts_start_sector = self.header.block_size // xts_sector_size
            if ekpfs is not None and self.header.seed is not None:
                new_crypt = bool(pfs_flags & 0x2000000000000000)
                tweak_key, data_key = crypto.pfs_gen_enc_key(ekpfs, self.header.seed, new_crypt)
                self.reader = XtsMemoryReader(self.reader, data_key, tweak_key, xts_start_sector, xts_sector_size)
            elif tweak is not None and data is not None:
                self.reader = XtsMemoryReader(self.reader, data, tweak, xts_start_sector, xts_sector_size)
            else:
                raise ValueError("PFS image is encrypted, but no valid EKPFS or XTS key was provided.")

        # Read Dinodes
        is_signed = bool(self.header.mode & PfsMode.SIGNED)
        dinode_size = 0x2C8 if is_signed else 0xA8
        dinode_reader = read_dinode_s32 if is_signed else read_dinode_d32

        self.dinodes: List[Inode] = []
        max_per_sector = self.header.block_size // dinode_size
        total = 0

        for i in range(self.header.dinode_block_count):
            pos = self.header.block_size * (1 + i)
            sec_buf = self.reader.read(pos, self.header.block_size)
            sec_stream = io.BytesIO(sec_buf)
            j = 0
            while j < max_per_sector and total < self.header.dinode_count:
                ino = dinode_reader(sec_stream)
                self.dinodes.append(ino)
                total += 1
                j += 1

        # Load root directory
        self.root = self._load_dir(0, None, "")
        uroot = self.root.get("uroot")
        if isinstance(uroot, PfsDir):
            self.uroot = uroot
            self.uroot.name = "uroot"
        else:
            self.uroot = self.root

    def _load_dir(self, dinode_idx: int, parent: Optional[PfsDir], name: str) -> PfsDir:
        ret = PfsDir(name, parent)
        if dinode_idx >= len(self.dinodes):
            return ret

        ino = self.dinodes[dinode_idx]
        blocks = ino.blocks
        if blocks < 1 or ino.start_block < 1 or ino.start_block > 100_000_000 or blocks > 100_000_000:
            return ret

        post_load: List[Tuple[int, str]] = []

        for blk in range(ino.start_block, ino.start_block + blocks):
            pos = self.header.block_size * blk
            sec_buf = self.reader.read(pos, self.header.block_size)
            sec_stream = io.BytesIO(sec_buf)
            cur_pos = 0

            while cur_pos < self.header.block_size:
                dirent = PfsDirent.read_from_stream(sec_stream)
                if dirent is None or dirent.ent_size == 0:
                    break

                if dirent.type == DirentType.FILE:
                    ret.children.append(self._load_file(dirent.inode_number, ret, dirent.name))
                elif dirent.type == DirentType.DIRECTORY:
                    post_load.append((dirent.inode_number, dirent.name))

                cur_pos += dirent.ent_size

        for sub_ino, sub_name in post_load:
            ret.children.append(self._load_dir(sub_ino, ret, sub_name))

        return ret

    def _load_file(self, dinode_idx: int, parent: PfsDir, name: str) -> PfsFile:
        if dinode_idx >= len(self.dinodes):
            f = PfsFile(self.reader, name, parent)
            return f

        ino = self.dinodes[dinode_idx]
        blocks: Optional[List[int]] = None

        if ino.blocks > 1 and len(ino.db) > 1 and ino.db[1] != -1:
            if not (self.header.mode & PfsMode.SIGNED):
                pass
            else:
                blocks = [ino.db[i] for i in range(min(12, ino.blocks))]
                rem_blocks = ino.blocks - 12
                sigs_per_blk = self.header.block_size // 36
                blk_idx_off = 12

                # Indirect blocks
                if rem_blocks > 0 and len(ino.ib) > 0 and ino.ib[0] != -1:
                    ind_off = ino.ib[0] * self.header.block_size
                    for i in range(min(rem_blocks, sigs_per_blk)):
                        raw = self.reader.read(ind_off + (i * 36) + 32, 4)
                        b_val = struct.unpack('<i', raw)[0]
                        blocks.append(b_val)
                    rem_blocks -= sigs_per_blk
                    blk_idx_off += sigs_per_blk

                # Check contiguous
                contiguous = True
                for i in range(1, len(blocks)):
                    if blocks[i - 1] + 1 != blocks[i]:
                        contiguous = False
                        break
                if contiguous:
                    blocks = None

        file_obj = PfsFile(self.reader, name, parent)
        file_obj.offset = ino.start_block * self.header.block_size
        file_obj.size = ino.size
        file_obj.compressed_size = ino.size_compressed
        file_obj.ino = dinode_idx
        file_obj.blocks = blocks
        return file_obj

    def get_file(self, full_path: str) -> Optional[PfsFile]:
        node = self.uroot.get_path(full_path)
        return node if isinstance(node, PfsFile) else None

    def get_all_files(self) -> Generator[PfsFile, None, None]:
        return self.uroot.get_all_files()

    def get_super_root(self) -> PfsDir:
        return self.root

    def get_uroot(self) -> PfsDir:
        return self.uroot
