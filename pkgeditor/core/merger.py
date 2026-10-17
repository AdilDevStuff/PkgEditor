"""
PlayStation PKG Parts Merger
Combines split PKG chunks (*_0.pkg, *_1.pkg, ...) into a single .pkg file.
"""
import os
import struct
from typing import List, Callable, Optional





class PkgMerger:
    @staticmethod
    def get_parts(part0_path: str) -> List[str]:
        if not part0_path.endswith("_0.pkg"):
            raise ValueError("Part file must end with '_0.pkg'")

        base_name = part0_path[:-6]
        parts = [part0_path]
        idx = 1
        while True:
            next_part = f"{base_name}_{idx}.pkg"
            if os.path.exists(next_part):
                parts.append(next_part)
                idx += 1
            else:
                break
        return parts

    @staticmethod
    def merge(parts: List[str], output_path: str, progress_callback: Optional[Callable[[str, int, int], None]] = None):
        """
        Merges parts into output_path.
        progress_callback(current_part_name, bytes_written, total_bytes)
        """
        total_size = sum(os.path.getsize(p) for p in parts)
        bytes_written = 0

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "wb") as out_f:
            for part in parts:
                part_name = os.path.basename(part)
                part_size = os.path.getsize(part)
                with open(part, "rb") as in_f:
                    while True:
                        chunk = in_f.read(1024 * 1024 * 4)  # 4MB chunks
                        if not chunk:
                            break
                        out_f.write(chunk)
                        bytes_written += len(chunk)
                        if progress_callback:
                            progress_callback(part_name, bytes_written, total_size)
