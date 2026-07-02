"""Persistent store for generated media assets and metadata."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:80] or "default"


def _png_dimensions(path: Path) -> tuple[int, int]:
    raw = path.read_bytes()
    if len(raw) < 24 or raw[:8] != b"\x89PNG\r\n\x1a\n":
        return 0, 0
    width = int.from_bytes(raw[16:20], "big")
    height = int.from_bytes(raw[20:24], "big")
    return width, height


@dataclass
class MediaAssetRecord:
    asset_id: str
    project_id: str
    rel_path: str
    mime: str
    width: int
    height: int
    provider: str
    cost_usd: float
    prompt: str
    created_at: str
    run_id: Optional[str] = None
    scene_id: Optional[str] = None
    seed: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class MediaAssetStore:
    def __init__(self, storage_root: str) -> None:
        self._root = Path(storage_root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    @property
    def root(self) -> Path:
        return self._root

    def project_dir(self, project_id: str) -> Path:
        path = self._root / _slug(project_id) / "assets"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def register_file(
        self,
        *,
        project_id: str,
        file_path: Path,
        mime: str,
        provider: str,
        cost_usd: float,
        prompt: str,
        run_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        seed: Optional[str] = None,
        asset_id: Optional[str] = None,
    ) -> MediaAssetRecord:
        file_path = file_path.resolve()
        root = self._root.resolve()
        width, height = _png_dimensions(file_path) if mime == "image/png" else (0, 0)
        try:
            rel = file_path.relative_to(root).as_posix()
        except ValueError:
            rel = file_path.as_posix()
        record = MediaAssetRecord(
            asset_id=asset_id or f"asset_{uuid4().hex[:12]}",
            project_id=_slug(project_id),
            rel_path=rel,
            mime=mime,
            width=width,
            height=height,
            provider=provider,
            cost_usd=cost_usd,
            prompt=prompt[:4000],
            created_at=_utc_now(),
            run_id=run_id,
            scene_id=scene_id,
            seed=seed,
        )
        meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")
        with self._lock:
            meta_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return record

    def get_asset(self, asset_id: str) -> Optional[MediaAssetRecord]:
        for meta in self._root.rglob("*.meta.json"):
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if data.get("asset_id") == asset_id:
                return MediaAssetRecord(**{k: data[k] for k in MediaAssetRecord.__dataclass_fields__})
        return None

    def resolve_path(self, record: MediaAssetRecord) -> Path:
        return self._root.resolve() / record.rel_path

    def list_assets(
        self,
        *,
        project_id: Optional[str] = None,
        run_id: Optional[str] = None,
        scene_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[MediaAssetRecord]:
        items: list[MediaAssetRecord] = []
        search_root = self._root / _slug(project_id) if project_id else self._root
        if not search_root.exists():
            return []
        for meta in sorted(search_root.rglob("*.meta.json"), reverse=True):
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                record = MediaAssetRecord(**{k: data[k] for k in MediaAssetRecord.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError, KeyError):
                continue
            if run_id and record.run_id != run_id:
                continue
            if scene_id and record.scene_id != scene_id:
                continue
            items.append(record)
            if len(items) >= limit:
                break
        return items

    def append_audit(self, line: dict[str, object]) -> None:
        audit_path = self._root / "audit.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ts": _utc_now(), **line}
        with self._lock:
            with audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
