"""Automatic skill selection for agent runs based on task text and context."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.schemas import TaskType
from app.services.skill_store import SkillRecord, SkillStore


@dataclass(frozen=True)
class SkillSelectionItem:
    skill_id: str
    name: str
    score: float
    matched_terms: tuple[str, ...]
    source: str  # pinned | auto


@dataclass(frozen=True)
class SkillSelectionResult:
    selected_skill_ids: list[str]
    selections: list[SkillSelectionItem]
    auto_select_enabled: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "selected_skill_ids": list(self.selected_skill_ids),
            "selections": [
                {
                    "skill_id": item.skill_id,
                    "name": item.name,
                    "score": round(item.score, 3),
                    "matched_terms": list(item.matched_terms),
                    "source": item.source,
                }
                for item in self.selections
            ],
            "auto_select_enabled": self.auto_select_enabled,
        }


_STOPWORDS: frozenset[str] = frozenset(
    {
        "and",
        "the",
        "for",
        "with",
        "add",
        "fix",
        "run",
        "use",
        "from",
        "that",
        "this",
        "have",
        "has",
        "are",
        "was",
        "were",
        "will",
        "can",
        "not",
        "you",
        "your",
        "when",
        "what",
        "how",
        "all",
        "any",
        "new",
        "get",
        "set",
        "one",
        "two",
        "via",
        "per",
        "out",
        "into",
        "over",
        "after",
        "before",
        "about",
        "just",
        "also",
        "only",
        "then",
        "than",
        "them",
        "they",
        "our",
        "its",
        "but",
        "or",
    }
)

_SHORT_ALLOWLIST: frozenset[str] = frozenset(
    {
        "ci",
        "api",
        "ssh",
        "jsx",
        "vue",
        "ios",
        "rbac",
        "xss",
        "csrf",
        "mcp",
        "sse",
        "sql",
        "npm",
        "git",
        "app",
        "web",
        "kpi",
        "dlq",
        "sft",
        "dpo",
        "ui",
        "ux",
    }
)

_SKILL_HINTS: dict[str, tuple[str, ...]] = {
    "fix-ci": (
        "github actions",
        "build failed",
        "failed check",
        "workflow",
        "pipeline",
        "actions",
        "lint",
        "ci",
    ),
    "write-tests": (
        "integration test",
        "unit test",
        "unittest",
        "pytest",
        "coverage",
        "write test",
        "add test",
        "tests",
        "test",
        "spec",
        "tdd",
    ),
    "security-review": (
        "security review",
        "vulnerability",
        "injection",
        "security",
        "secret",
        "auth",
        "xss",
        "csrf",
        "rbac",
    ),
    "cross-platform-atomic": (
        "cross-platform",
        "cross platform",
        "swiftui",
        "flutter",
        "android",
        "macos",
        "windows",
        "kotlin",
        "maui",
        "unity",
        "godot",
        "xcode",
        "ios",
    ),
    "online-project": (
        "online project",
        "assignment",
        "deliverable",
        "brief.md",
        "journal",
    ),
    "online-research": (
        "web search",
        "online_research",
        "compare sources",
        "citations",
        "perplexity",
        "research",
        "@web",
    ),
    "web-app": (
        "web app",
        "frontend",
        "next.js",
        "react",
        "tailwind",
        "spa",
        "vue",
    ),
    "termit-desktop": (
        "termit desktop",
        "termit.app",
        "desktop app",
        "monaco",
        "electron",
    ),
    "agent-autopilot": (
        "auto confirm",
        "without confirm",
        "autonomous",
        "autopilot",
    ),
    "agent-guided": (
        "human confirm",
        "step by step",
        "guided agent",
        "awaiting_confirmation",
        "approve",
        "guided",
    ),
}

_FILE_HINTS: tuple[tuple[tuple[str, ...], str, float], ...] = (
    ((".github/workflows", ".gitlab-ci", "Jenkinsfile", "azure-pipelines"), "fix-ci", 4.0),
    (("test_", "_test.", "/tests/", "spec.", ".spec."), "write-tests", 3.5),
    (("auth", "security", "secret", "rbac"), "security-review", 3.0),
    (("clients/termit-desktop", "termit-desktop"), "termit-desktop", 3.0),
)

_TASK_TYPE_BOOSTS: dict[str, dict[str, float]] = {
    "review": {"security-review": 3.0},
    "debug": {"fix-ci": 2.0, "write-tests": 1.5},
    "coding": {"write-tests": 1.0, "fix-ci": 1.0},
    "creative_media": {"media-studio": 4.0},
}


class SkillSelectorService:
    def __init__(
        self,
        skill_store: SkillStore,
        *,
        max_skills: int = 3,
        min_score: float = 3.0,
        enabled: bool = True,
    ) -> None:
        self._skill_store = skill_store
        self._max_skills = max(1, max_skills)
        self._min_score = max(0.0, min_score)
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def select_skills(
        self,
        *,
        instruction: str,
        task_type: TaskType | str = TaskType.general,
        pinned_skill_ids: list[str] | None = None,
        changed_files: list[str] | None = None,
        max_skills: int | None = None,
        auto_select_enabled: bool | None = None,
        min_score: float | None = None,
    ) -> SkillSelectionResult:
        limit = max(1, max_skills or self._max_skills)
        use_auto = self._enabled if auto_select_enabled is None else auto_select_enabled
        threshold = self._min_score if min_score is None else min_score
        pinned = _dedupe_pinned(pinned_skill_ids or [])
        selections: list[SkillSelectionItem] = []

        for skill_id in pinned:
            skill = self._skill_store.get_skill(skill_id)
            if skill is None:
                continue
            selections.append(
                SkillSelectionItem(
                    skill_id=skill.skill_id,
                    name=skill.name,
                    score=100.0,
                    matched_terms=("pinned",),
                    source="pinned",
                )
            )

        selected_ids = [item.skill_id for item in selections]
        if not use_auto:
            return SkillSelectionResult(
                selected_skill_ids=selected_ids[:limit],
                selections=selections[:limit],
                auto_select_enabled=False,
            )

        remaining = max(0, limit - len(selected_ids))
        if remaining <= 0:
            return SkillSelectionResult(
                selected_skill_ids=selected_ids[:limit],
                selections=selections[:limit],
                auto_select_enabled=True,
            )

        task_key = task_type.value if isinstance(task_type, TaskType) else str(task_type)
        query = _build_query(instruction, changed_files or [])
        scored: list[tuple[float, SkillRecord, tuple[str, ...], bool]] = []
        for skill in self._skill_store.list_skills():
            if skill.skill_id in selected_ids:
                continue
            score, matched, has_strong_signal = self._score_skill(skill, query, task_key)
            if score + 1e-9 >= threshold and has_strong_signal:
                scored.append((score, skill, matched, has_strong_signal))

        scored.sort(key=lambda item: (-item[0], item[1].skill_id))
        if scored:
            top_score = scored[0][0]
            cutoff = max(threshold, top_score * 0.55)
            scored = [item for item in scored if item[0] + 1e-9 >= cutoff]

        for score, skill, matched, _strong in scored[:remaining]:
            selected_ids.append(skill.skill_id)
            selections.append(
                SkillSelectionItem(
                    skill_id=skill.skill_id,
                    name=skill.name,
                    score=score,
                    matched_terms=matched,
                    source="auto",
                )
            )

        return SkillSelectionResult(
            selected_skill_ids=selected_ids[:limit],
            selections=selections[:limit],
            auto_select_enabled=True,
        )

    def _score_skill(
        self,
        skill: SkillRecord,
        query: str,
        task_type: str,
    ) -> tuple[float, tuple[str, ...], bool]:
        text = query.lower()
        instruction_tokens = _meaningful_tokens(query)
        matched: list[str] = []
        score = 0.0
        strong_signals = 0

        skill_slug = skill.skill_id.replace("-", " ")
        if skill.skill_id in text or skill_slug in text:
            score += 8.0
            strong_signals += 1
            matched.append(skill.skill_id)

        for hint, hint_score in _match_hints(text, _SKILL_HINTS.get(skill.skill_id, ())):
            score += hint_score
            strong_signals += 1
            matched.append(hint)

        metadata_tokens = _meaningful_tokens(f"{skill.name} {skill.description}")
        overlap = instruction_tokens & metadata_tokens
        if overlap:
            overlap_score = min(4.0, len(overlap) * 1.5)
            score += overlap_score
            matched.extend(sorted(overlap))
            if len(overlap) >= 2 or any(len(token) >= 5 for token in overlap):
                strong_signals += 1

        for patterns, target_skill, boost in _FILE_HINTS:
            if target_skill != skill.skill_id:
                continue
            for pattern in patterns:
                if pattern.lower() in text:
                    score += boost
                    strong_signals += 1
                    matched.append(f"file:{pattern}")

        if skill.skill_id == "cross-platform-atomic":
            from app.services.cross_platform_dev_service import CrossPlatformDevService

            if CrossPlatformDevService.is_cross_platform_task(query):
                score += 10.0
                strong_signals += 1
                matched.append("cross_platform_task")

        task_boost = _TASK_TYPE_BOOSTS.get(task_type, {}).get(skill.skill_id, 0.0)
        if task_boost > 0.0:
            if strong_signals > 0 or (task_type == "review" and skill.skill_id == "security-review"):
                score += task_boost
                matched.append(f"task_type:{task_type}")

        has_strong_signal = strong_signals > 0
        return score, tuple(dict.fromkeys(matched)), has_strong_signal


def _build_query(instruction: str, changed_files: list[str]) -> str:
    parts = [instruction.strip()]
    for path in changed_files:
        cleaned = str(path).strip()
        if cleaned:
            parts.append(cleaned)
    return "\n".join(parts)


def _dedupe_pinned(skill_ids: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in skill_ids:
        skill_id = str(raw).strip()
        if not skill_id or skill_id in seen:
            continue
        seen.add(skill_id)
        ordered.append(skill_id)
    return ordered


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _meaningful_tokens(text: str) -> set[str]:
    tokens: set[str] = set()
    for token in _tokenize(text):
        if token in _STOPWORDS:
            continue
        if token in _SHORT_ALLOWLIST or len(token) >= 4:
            tokens.add(token)
    return tokens


def _match_hints(text: str, hints: tuple[str, ...]) -> list[tuple[str, float]]:
    matches: list[tuple[str, float]] = []
    consumed: list[tuple[int, int]] = []

    for hint in sorted(hints, key=len, reverse=True):
        normalized = hint.lower().strip()
        if not normalized:
            continue
        if " " in normalized:
            start = text.find(normalized)
            if start < 0:
                continue
            end = start + len(normalized)
        else:
            pattern = rf"\b{re.escape(normalized)}\b"
            found = re.search(pattern, text)
            if not found:
                continue
            start, end = found.start(), found.end()

        if any(start < used_end and end > used_start for used_start, used_end in consumed):
            continue

        consumed.append((start, end))
        if len(normalized) >= 10:
            weight = 4.5
        elif len(normalized) >= 5:
            weight = 3.5
        else:
            weight = 2.5
        matches.append((normalized, weight))

    return matches
