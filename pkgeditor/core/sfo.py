"""
PlayStation PARAM.SFO Parser and Serializer
Full read/write support for PARAM.SFO files across PS3, PS Vita, PS4, and PS5.
"""
import io
import struct
import json
from enum import IntEnum
from typing import Dict, List, Any, Optional, Union


class SfoEntryType(IntEnum):
    Utf8Special = 0x0004
    Utf8 = 0x0204
    Integer = 0x0404


class SfoValue:
    def __init__(self, name: str, entry_type: SfoEntryType, value: Any, max_length: int = 4):
        self.name = name
        self.entry_type = entry_type
        self.value = value
        self.max_length = max_length

    @property
    def length(self) -> int:
        if self.entry_type == SfoEntryType.Integer:
            return 4
        elif self.entry_type == SfoEntryType.Utf8:
            b = str(self.value).encode('utf-8')
            return len(b) + 1  # null terminated
        else:  # Utf8Special
            b = str(self.value).encode('utf-8')
            return len(b)

    def to_bytes(self) -> bytes:
        if self.entry_type == SfoEntryType.Integer:
            val = int(self.value)
            return struct.pack('<I', val & 0xFFFFFFFF)
        elif self.entry_type == SfoEntryType.Utf8:
            b = str(self.value).encode('utf-8') + b'\x00'
            return b.ljust(self.max_length, b'\x00')
        else:  # Utf8Special
            b = str(self.value).encode('utf-8')
            return b.ljust(self.max_length, b'\x00')

    def __str__(self) -> str:
        if self.entry_type == SfoEntryType.Integer:
            return str(self.value)
        return str(self.value)

    def __repr__(self) -> str:
        return f"SfoValue({self.name!r}, {self.entry_type.name}, {self.value!r}, max_len={self.max_length})"


class ParamSfo:
    MAGIC = b'\x00PSF'
    SCEC_MAGIC = b'SCEC'

    def __init__(self):
        self.values: List[SfoValue] = []

    def __getitem__(self, key: str) -> Optional[Any]:
        v = self.get_entry(key)
        return v.value if v else None

    def __setitem__(self, key: str, value: Any):
        existing = self.get_entry(key)
        if existing is not None:
            existing.value = value
            if existing.entry_type in (SfoEntryType.Utf8, SfoEntryType.Utf8Special):
                needed = len(str(value).encode('utf-8')) + (1 if existing.entry_type == SfoEntryType.Utf8 else 0)
                if needed > existing.max_length:
                    # Align to 4 bytes
                    existing.max_length = (needed + 3) & ~3
        else:
            if isinstance(value, int):
                self.add_value(key, SfoEntryType.Integer, value, 4)
            else:
                str_val = str(value)
                b = str_val.encode('utf-8')
                max_len = max(len(b) + 1, 4)
                max_len = (max_len + 3) & ~3
                self.add_value(key, SfoEntryType.Utf8, str_val, max_len)

    def __contains__(self, key: str) -> bool:
        return self.get_entry(key) is not None

    def get_entry(self, name: str) -> Optional[SfoValue]:
        for v in self.values:
            if v.name == name:
                return v
        return None

    def add_value(self, name: str, entry_type: SfoEntryType, value: Any, max_length: int = 4) -> SfoValue:
        # Remove existing if any
        self.remove_value(name)
        val = SfoValue(name, entry_type, value, max_length)
        self.values.append(val)
        self.values.sort(key=lambda x: x.name)
        return val

    def remove_value(self, name: str) -> bool:
        initial = len(self.values)
        self.values = [v for v in self.values if v.name != name]
        return len(self.values) < initial

    def keys(self) -> List[str]:
        return [v.name for v in self.values]

    def to_dict(self) -> Dict[str, Any]:
        return {v.name: v.value for v in self.values}

    @classmethod
    def from_bytes(cls, data: bytes) -> "ParamSfo":
        return cls.from_stream(io.BytesIO(data))

    @classmethod
    def from_file(cls, path: str) -> "ParamSfo":
        with open(path, 'rb') as f:
            return cls.from_stream(f)

    @classmethod
    def from_stream(cls, stream: io.IOBase) -> "ParamSfo":
        sfo = cls()
        start = stream.tell()
        magic = stream.read(4)
        if magic == cls.SCEC_MAGIC:
            start += 0x800
            stream.seek(start)
            magic = stream.read(4)

        if magic != cls.MAGIC:
            raise ValueError(f"Invalid SFO magic: {magic!r} (expected {cls.MAGIC!r})")

        stream.seek(start + 8)
        header_data = stream.read(12)
        key_table_offset, data_table_offset, num_values = struct.unpack('<III', header_data)

        for i in range(num_values):
            stream.seek(start + 0x14 + (i * 0x10))
            entry_header = stream.read(16)
            key_offset, format_val, length, max_length, data_offset = struct.unpack('<HHIII', entry_header)

            try:
                entry_type = SfoEntryType(format_val)
            except ValueError:
                entry_type = SfoEntryType.Utf8

            # Read Key
            stream.seek(start + key_table_offset + key_offset)
            key_name_bytes = bytearray()
            while True:
                b = stream.read(1)
                if not b or b == b'\x00':
                    break
                key_name_bytes.extend(b)
            key_name = key_name_bytes.decode('ascii', errors='replace')

            # Read Data
            stream.seek(start + data_table_offset + data_offset)
            raw_data = stream.read(length)

            if entry_type == SfoEntryType.Integer:
                val = struct.unpack('<I', raw_data[:4].ljust(4, b'\x00'))[0]
            elif entry_type == SfoEntryType.Utf8:
                if len(raw_data) > 0 and raw_data[-1] == 0:
                    raw_data = raw_data[:-1]
                val = raw_data.decode('utf-8', errors='replace')
            else:  # Utf8Special
                val = raw_data.decode('utf-8', errors='replace')

            sfo.values.append(SfoValue(key_name, entry_type, val, max_length))

        sfo.values.sort(key=lambda x: x.name)
        return sfo

    def to_bytes(self) -> bytes:
        self.values.sort(key=lambda x: x.name)
        key_table_offset = 0x14 + (len(self.values) * 0x10)

        # Calculate table positions
        key_table_bytes = bytearray()
        key_offsets = []
        for v in self.values:
            key_offsets.append(len(key_table_bytes))
            key_table_bytes.extend(v.name.encode('ascii') + b'\x00')

        data_table_offset = key_table_offset + len(key_table_bytes)
        # 4-byte align data table offset
        if data_table_offset % 4 != 0:
            pad = 4 - (data_table_offset % 4)
            key_table_bytes.extend(b'\x00' * pad)
            data_table_offset += pad

        data_table_bytes = bytearray()
        data_offsets = []
        for v in self.values:
            data_offsets.append(len(data_table_bytes))
            data_table_bytes.extend(v.to_bytes())

        # Build output
        out = io.BytesIO()
        out.write(self.MAGIC)
        out.write(struct.pack('<III', 0x101, key_table_offset, data_table_offset))
        out.write(struct.pack('<I', len(self.values)))

        # Write entries table
        for i, v in enumerate(self.values):
            out.write(struct.pack('<HHIII', key_offsets[i], int(v.entry_type), v.length, v.max_length, data_offsets[i]))

        # Write key table
        out.write(key_table_bytes)
        # Write data table
        out.write(data_table_bytes)

        return out.getvalue()

    def save(self, path: str):
        with open(path, 'wb') as f:
            f.write(self.to_bytes())

    @classmethod
    def create_template_gd(cls, title: str = "Title", title_id: str = "CUSA00000", content_id: str = "AA0000-CUSA00000_00-0000000000000000") -> "ParamSfo":
        """Default Game / Application Template."""
        sfo = cls()
        sfo.add_value("APP_TYPE", SfoEntryType.Integer, 4, 4)
        sfo.add_value("APP_VER", SfoEntryType.Utf8, "01.00", 8)
        sfo.add_value("ATTRIBUTE", SfoEntryType.Integer, 0, 4)
        sfo.add_value("CATEGORY", SfoEntryType.Utf8, "gd", 4)
        sfo.add_value("CONTENT_ID", SfoEntryType.Utf8, content_id, 48)
        sfo.add_value("DOWNLOAD_DATA_SIZE", SfoEntryType.Integer, 0, 4)
        sfo.add_value("FORMAT", SfoEntryType.Utf8, "obs", 4)
        sfo.add_value("PARENTAL_LEVEL", SfoEntryType.Integer, 1, 4)
        sfo.add_value("SYSTEM_VER", SfoEntryType.Integer, 0, 4)
        sfo.add_value("TITLE", SfoEntryType.Utf8, title, 128)
        sfo.add_value("TITLE_ID", SfoEntryType.Utf8, title_id, 12)
        sfo.add_value("VERSION", SfoEntryType.Utf8, "01.00", 8)
        return sfo

    @classmethod
    def create_template_ac(cls, title: str = "Addon Title", title_id: str = "CUSA00000", content_id: str = "AA0000-CUSA00000_00-0000000000000000") -> "ParamSfo":
        """Default Add-on Content Template."""
        sfo = cls()
        sfo.add_value("ATTRIBUTE", SfoEntryType.Integer, 0, 4)
        sfo.add_value("CATEGORY", SfoEntryType.Utf8, "ac", 4)
        sfo.add_value("CONTENT_ID", SfoEntryType.Utf8, content_id, 48)
        sfo.add_value("FORMAT", SfoEntryType.Utf8, "obs", 4)
        sfo.add_value("TITLE", SfoEntryType.Utf8, title, 128)
        sfo.add_value("TITLE_ID", SfoEntryType.Utf8, title_id, 12)
        sfo.add_value("VERSION", SfoEntryType.Utf8, "01.00", 8)
        return sfo

    @classmethod
    def create_template_ps3_game(cls, title: str = "PS3 Game", title_id: str = "NPUB00000") -> "ParamSfo":
        """PS3 Game Template."""
        sfo = cls()
        sfo.add_value("APP_VER", SfoEntryType.Utf8, "01.00", 8)
        sfo.add_value("BOOTABLE", SfoEntryType.Integer, 1, 4)
        sfo.add_value("CATEGORY", SfoEntryType.Utf8, "HG", 4)
        sfo.add_value("PARENTAL_LEVEL", SfoEntryType.Integer, 1, 4)
        sfo.add_value("RESOLUTION", SfoEntryType.Integer, 63, 4)
        sfo.add_value("SOUND_FORMAT", SfoEntryType.Integer, 1, 4)
        sfo.add_value("TITLE", SfoEntryType.Utf8, title, 128)
        sfo.add_value("TITLE_ID", SfoEntryType.Utf8, title_id, 12)
        sfo.add_value("VERSION", SfoEntryType.Utf8, "01.00", 8)
        return sfo
