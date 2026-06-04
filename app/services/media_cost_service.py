"""Pre-flight cost estimation for storyboards (Phase 1 heuristic tariffs)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class MediaCostLine:
    scene_id: str
    item: str
    usd: float


@dataclass(frozen=True)
class MediaCostEstimate:
    total_usd: float
    lines: list[MediaCostLine]
    scene_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "total_usd": round(self.total_usd, 4),
            "scene_count": self.scene_count,
            "lines": [
                {"scene_id": line.scene_id, "item": line.item, "usd": round(line.usd, 4)}
                for line in self.lines
            ],
        }


# Tariffs aligned with ADR order-of-magnitude (USD).
_TARIFF_IMAGE = 0.08
_TARIFF_I2V_PER_SEC = 0.10
_TARIFF_TTS_PER_100_CHARS = 0.015


def estimate_from_storyboard(
    storyboard: dict[str, object],
    *,
    image_tariff: float = _TARIFF_IMAGE,
    i2v_tariff_per_sec: float = _TARIFF_I2V_PER_SEC,
) -> MediaCostEstimate:
    scenes = storyboard.get("scenes", [])
    if not isinstance(scenes, list):
        raise ValueError("storyboard.scenes must be a list")
    lines: list[MediaCostLine] = []
    for raw in scenes:
        if not isinstance(raw, dict):
            continue
        scene_id = str(raw.get("scene_id", "scene"))
        mode = str(raw.get("render_mode", "image_to_video"))
        duration = float(raw.get("duration_sec", 5))
        if mode in {"image_only", "ken_burns", "remotion_template"}:
            lines.append(MediaCostLine(scene_id, "image", image_tariff))
        elif mode == "image_to_video":
            lines.append(MediaCostLine(scene_id, "image", image_tariff))
            lines.append(
                MediaCostLine(scene_id, "i2v", max(1.0, duration) * i2v_tariff_per_sec)
            )
        elif mode == "text_to_video":
            lines.append(
                MediaCostLine(scene_id, "t2v", max(2.0, duration) * i2v_tariff_per_sec * 1.2)
            )
        vo = str(raw.get("voiceover", ""))
        if vo.strip():
            chars = len(vo)
            lines.append(
                MediaCostLine(
                    scene_id,
                    "tts",
                    max(0.01, (chars / 100.0) * _TARIFF_TTS_PER_100_CHARS),
                )
            )
    total = sum(line.usd for line in lines)
    return MediaCostEstimate(total_usd=total, lines=lines, scene_count=len(scenes))


def estimate_storyboard_path(path: str | Path) -> MediaCostEstimate:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Storyboard JSON must be an object")
    return estimate_from_storyboard(data)
