"""Minimal Lottie JSON export from PNG frame sequences (no Pillow)."""

from __future__ import annotations

import base64
import json
import mimetypes
import struct
from pathlib import Path


class MediaLottieError(Exception):
    pass


def _png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        raise MediaLottieError(f"Not a PNG file: {path.name}")
    width, height = struct.unpack(">II", data[16:24])
    return max(1, width), max(1, height)


def _mime_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


class MediaLottieService:
    def export_lottie(
        self,
        *,
        image_paths: list[Path],
        output_path: Path,
        fps: int = 8,
        width: int | None = None,
    ) -> None:
        if not image_paths:
            raise MediaLottieError("export_lottie requires at least one image")
        fps = max(1, min(fps, 60))
        assets: list[dict[str, object]] = []
        layers: list[dict[str, object]] = []
        comp_w = 0
        comp_h = 0
        for idx, path in enumerate(image_paths):
            img_w, img_h = _png_dimensions(path)
            if width and width > 0 and img_w != width:
                scale = width / img_w
                img_w = width
                img_h = max(1, int(round(img_h * scale)))
            comp_w = max(comp_w, img_w)
            comp_h = max(comp_h, img_h)
            mime = _mime_for_path(path)
            encoded = base64.b64encode(path.read_bytes()).decode("ascii")
            asset_id = f"img_{idx}"
            assets.append(
                {
                    "id": asset_id,
                    "w": img_w,
                    "h": img_h,
                    "u": "",
                    "p": f"data:{mime};base64,{encoded}",
                    "e": 1,
                }
            )
            opacity_keys: list[dict[str, object]] = []
            for frame_idx in range(len(image_paths)):
                opacity_keys.append(
                    {
                        "t": frame_idx,
                        "s": [100 if frame_idx == idx else 0],
                        "h": 1,
                    }
                )
            layers.append(
                {
                    "ddd": 0,
                    "ind": idx + 1,
                    "ty": 2,
                    "nm": f"frame_{idx}",
                    "refId": asset_id,
                    "sr": 1,
                    "ks": {
                        "o": {"a": 1, "k": opacity_keys},
                        "r": {"a": 0, "k": 0},
                        "p": {"a": 0, "k": [comp_w / 2, comp_h / 2, 0]},
                        "a": {"a": 0, "k": [0, 0, 0]},
                        "s": {"a": 0, "k": [100, 100, 100]},
                    },
                    "ao": 0,
                    "ip": 0,
                    "op": len(image_paths),
                    "st": 0,
                    "bm": 0,
                }
            )
        payload = {
            "v": "5.7.4",
            "fr": fps,
            "ip": 0,
            "op": len(image_paths),
            "w": comp_w,
            "h": comp_h,
            "nm": output_path.stem,
            "ddd": 0,
            "assets": assets,
            "layers": layers,
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
