"""Brand kit persistence under data/media/brand_kits/."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class BrandKitRecord:
    brand_kit_id: str
    name: str
    colors: list[str]
    fonts: list[str]
    logo_paths: list[str]
    voice_id: str
    music_mood: str
    style_prompt_suffix: str

    def to_dict(self) -> dict[str, object]:
        return {
            "brand_kit_id": self.brand_kit_id,
            "name": self.name,
            "colors": self.colors,
            "fonts": self.fonts,
            "logo_paths": self.logo_paths,
            "voice_id": self.voice_id,
            "music_mood": self.music_mood,
            "style_prompt_suffix": self.style_prompt_suffix,
        }


class BrandKitStore:
    def __init__(self, root_dir: str) -> None:
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, kit: BrandKitRecord) -> BrandKitRecord:
        slug = _slug(kit.brand_kit_id)
        path = self._root / f"{slug}.json"
        path.write_text(json.dumps(kit.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return kit

    def get(self, brand_kit_id: str) -> Optional[BrandKitRecord]:
        path = self._root / f"{_slug(brand_kit_id)}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return _from_dict(data)

    def list_kits(self) -> list[BrandKitRecord]:
        items: list[BrandKitRecord] = []
        for path in sorted(self._root.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                items.append(_from_dict(data))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue
        return items


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "default"


def _from_dict(data: dict[str, object]) -> BrandKitRecord:
    return BrandKitRecord(
        brand_kit_id=str(data["brand_kit_id"]),
        name=str(data.get("name", "")),
        colors=[str(c) for c in data.get("colors", []) if str(c)],
        fonts=[str(f) for f in data.get("fonts", []) if str(f)],
        logo_paths=[str(p) for p in data.get("logo_paths", []) if str(p)],
        voice_id=str(data.get("voice_id", "")),
        music_mood=str(data.get("music_mood", "")),
        style_prompt_suffix=str(data.get("style_prompt_suffix", "")),
    )
