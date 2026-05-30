from __future__ import annotations

import re
from dataclasses import dataclass

from app.domain.schemas import ChatMessage


@dataclass(frozen=True)
class CompactionResult:
    messages: list[ChatMessage]
    compacted: bool
    dropped_messages: int
    total_chars: int


class ContextCompactor:
    def __init__(
        self,
        max_messages: int = 20,
        max_chars: int = 12000,
        summary_max_chars: int = 2000,
    ) -> None:
        self.max_messages = max(1, max_messages)
        self.max_chars = max(64, max_chars)
        self.summary_max_chars = max(64, summary_max_chars)

    def compact(self, messages: list[ChatMessage]) -> CompactionResult:
        if not messages:
            return CompactionResult(messages=[], compacted=False, dropped_messages=0, total_chars=0)

        working = list(messages)
        dropped: list[ChatMessage] = []

        if len(working) > self.max_messages:
            drop_count = len(working) - self.max_messages
            dropped.extend(working[:drop_count])
            working = working[drop_count:]

        total_chars = sum(len(item.content) for item in working)
        while working and total_chars > self.max_chars:
            removed = working.pop(0)
            dropped.append(removed)
            total_chars -= len(removed.content)

        compacted = len(dropped) > 0
        if dropped:
            summary = self._summarize_dropped(dropped)
            working = [
                ChatMessage(
                    role="system",
                    content=(
                        "[Context compaction] Older messages were summarized to stay within "
                        f"the context budget ({self.max_messages} messages / {self.max_chars} chars).\n"
                        f"{summary}"
                    ),
                ),
                *working,
            ]
            total_chars = sum(len(item.content) for item in working)

        return CompactionResult(
            messages=working,
            compacted=compacted,
            dropped_messages=len(dropped),
            total_chars=total_chars,
        )

    def _summarize_dropped(self, dropped: list[ChatMessage]) -> str:
        lines: list[str] = []
        for message in dropped[-12:]:
            snippet = re.sub(r"\s+", " ", message.content).strip()
            if len(snippet) > 180:
                snippet = snippet[:177] + "..."
            lines.append(f"- {message.role}: {snippet}")
        summary = "\n".join(lines)
        if len(summary) > self.summary_max_chars:
            summary = summary[: self.summary_max_chars - 3] + "..."
        return summary

    @staticmethod
    def format_retrieval_context(chunks: list[tuple[str, str, float]]) -> str:
        if not chunks:
            return ""
        lines = [
            "[Retrieved codebase context] Relevant snippets from the workspace:",
            "",
        ]
        for path, excerpt, score in chunks:
            lines.append(f"### {path} (score={score:.2f})")
            lines.append(excerpt.strip())
            lines.append("")
        return "\n".join(lines).strip()
