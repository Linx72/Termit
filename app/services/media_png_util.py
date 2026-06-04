"""Minimal PNG writer for stub provider (no Pillow dependency)."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path


def write_solid_png(path: Path, width: int, height: int, rgb: tuple[int, int, int]) -> None:
    width = max(1, min(width, 4096))
    height = max(1, min(height, 4096))
    r, g, b = rgb
    raw_rows = []
    for _ in range(height):
        row = b"\x00" + bytes([r, g, b]) * width
        raw_rows.append(row)
    compressed = zlib.compress(b"".join(raw_rows), 9)

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)
