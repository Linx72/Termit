from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock


@dataclass(frozen=True)
class CodeChunk:
    path: str
    line_start: int
    line_end: int
    content: str
    score: float = 0.0

    @property
    def excerpt(self) -> str:
        return self.content.strip()


class CodeRetrievalService:
    _SKIP_DIRS = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
    }
    _INCLUDE_SUFFIXES = {
        ".py",
        ".md",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".sql",
        ".html",
        ".css",
    }

    def __init__(
        self,
        root_path: str = ".",
        chunk_max_chars: int = 1200,
        max_file_bytes: int = 200_000,
        include_suffixes: set[str] | None = None,
    ) -> None:
        self.root = Path(root_path).resolve()
        self.chunk_max_chars = max(400, chunk_max_chars)
        self.max_file_bytes = max(10_000, max_file_bytes)
        self.include_suffixes = include_suffixes or self._INCLUDE_SUFFIXES
        self._lock = Lock()
        self._chunks: list[CodeChunk] = []
        self._indexed_files = 0

    def reindex(self) -> tuple[int, int]:
        chunks: list[CodeChunk] = []
        indexed_files = 0
        for file_path in self._iter_files():
            indexed_files += 1
            chunks.extend(self._chunk_file(file_path))
        with self._lock:
            self._chunks = chunks
            self._indexed_files = indexed_files
        return indexed_files, len(chunks)

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        path_prefix: str = "",
    ) -> list[CodeChunk]:
        safe_limit = max(1, min(limit, 20))
        with self._lock:
            if not self._chunks:
                self.reindex()
            candidates = list(self._chunks)

        tokens = self._tokenize(query)
        if not tokens:
            return []

        prefix = path_prefix.strip().replace("\\", "/")
        scored: list[CodeChunk] = []
        for chunk in candidates:
            if prefix and not chunk.path.startswith(prefix):
                continue
            score = self._score_chunk(tokens, chunk)
            if score <= 0:
                continue
            scored.append(
                CodeChunk(
                    path=chunk.path,
                    line_start=chunk.line_start,
                    line_end=chunk.line_end,
                    content=chunk.content,
                    score=score,
                )
            )

        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:safe_limit]

    def stats(self) -> dict[str, int]:
        with self._lock:
            return {
                "indexed_files": self._indexed_files,
                "indexed_chunks": len(self._chunks),
            }

    def _iter_files(self) -> list[Path]:
        files: list[Path] = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in self._SKIP_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in self.include_suffixes:
                continue
            try:
                if path.stat().st_size > self.max_file_bytes:
                    continue
            except OSError:
                continue
            files.append(path)
        return files

    def _chunk_file(self, file_path: Path) -> list[CodeChunk]:
        rel_path = str(file_path.relative_to(self.root))
        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []

        lines = text.splitlines()
        if not lines:
            return []

        chunks: list[CodeChunk] = []
        start_idx = 0
        buffer: list[str] = []
        buffer_len = 0

        def flush(end_idx: int) -> None:
            nonlocal start_idx, buffer, buffer_len
            if not buffer:
                return
            chunks.append(
                CodeChunk(
                    path=rel_path,
                    line_start=start_idx + 1,
                    line_end=end_idx,
                    content="\n".join(buffer),
                )
            )
            start_idx = end_idx
            buffer = []
            buffer_len = 0

        for index, line in enumerate(lines, start=1):
            line_len = len(line) + 1
            if buffer and buffer_len + line_len > self.chunk_max_chars:
                flush(index - 1)
                start_idx = index - 1
            buffer.append(line)
            buffer_len += line_len

        if buffer:
            flush(len(lines))
        return chunks

    @staticmethod
    def _tokenize(query: str) -> list[str]:
        expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", query)
        tokens = re.findall(r"[a-zA-Z0-9_./-]{2,}", expanded.lower())
        seen: set[str] = set()
        unique: list[str] = []
        for token in tokens:
            if token in seen:
                continue
            seen.add(token)
            unique.append(token)
        return unique

    def _score_chunk(self, tokens: list[str], chunk: CodeChunk) -> float:
        path_lower = chunk.path.lower()
        path_compact = path_lower.replace("_", "")
        haystack = f"{path_lower}\n{chunk.content}".lower()
        haystack_compact = haystack.replace("_", "")
        score = 0.0
        for token in tokens:
            if token in path_lower or token in path_compact:
                score += 3.0
            occurrences = max(haystack.count(token), haystack_compact.count(token))
            if occurrences:
                score += min(occurrences, 8) * 1.0
        if score > 0:
            score /= max(1.0, len(chunk.content) ** 0.35)
        return score
