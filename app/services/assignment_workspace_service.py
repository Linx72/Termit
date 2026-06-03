from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.domain.schemas import AssignmentCreateRequest, AssignmentResponse


class AssignmentWorkspaceError(Exception):
    pass


class AssignmentWorkspaceService:
    def __init__(self, base_dir: str) -> None:
        self.base = Path(base_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def create(self, payload: AssignmentCreateRequest) -> AssignmentResponse:
        slug = _slugify(payload.title)
        assignment_id = f"{slug}-{uuid4().hex[:8]}"
        root = self.base / assignment_id
        if root.exists():
            raise AssignmentWorkspaceError(f"Assignment path already exists: {root}")
        deliverables = root / "deliverables"
        journal = root / "journal"
        deliverables.mkdir(parents=True)
        journal.mkdir(parents=True)

        brief_path = root / "brief.md"
        criteria = "\n".join(f"- {item}" for item in payload.success_criteria) or "- (define criteria)"
        urls = "\n".join(f"- {url}" for url in payload.target_urls) or "- (none yet)"
        brief_path.write_text(
            "\n".join(
                [
                    f"# {payload.title}",
                    "",
                    "## Assignment",
                    payload.brief.strip(),
                    "",
                    "## Success criteria",
                    criteria,
                    "",
                    "## Target URLs",
                    urls,
                    "",
                    "## Status",
                    "state: in_progress",
                ]
            ),
            encoding="utf-8",
        )
        (journal / "log.md").write_text(
            f"# Journal — {assignment_id}\n\nCreated {_utc_now()}\n",
            encoding="utf-8",
        )
        (deliverables / "README.md").write_text(
            "# Deliverables\n\nPlace outputs here (drafts, exports, screenshots).\n",
            encoding="utf-8",
        )

        return AssignmentResponse(
            assignment_id=assignment_id,
            root_path=str(root),
            brief_path=str(brief_path),
            deliverables_path=str(deliverables),
            journal_path=str(journal / "log.md"),
            created_at=_utc_now(),
        )

    def list_assignments(self, limit: int = 50) -> list[AssignmentResponse]:
        items: list[AssignmentResponse] = []
        for path in sorted(self.base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if not path.is_dir():
                continue
            brief = path / "brief.md"
            if not brief.is_file():
                continue
            items.append(
                AssignmentResponse(
                    assignment_id=path.name,
                    root_path=str(path),
                    brief_path=str(brief),
                    deliverables_path=str(path / "deliverables"),
                    journal_path=str(path / "journal" / "log.md"),
                    created_at=datetime.fromtimestamp(
                        path.stat().st_mtime, tz=timezone.utc
                    ).isoformat(),
                )
            )
            if len(items) >= limit:
                break
        return items


def _slugify(text: str) -> str:
    lowered = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug[:40] or "assignment"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
