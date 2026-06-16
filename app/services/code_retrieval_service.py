from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from urllib import error, request

from app.services.embedding_cache import EmbeddingCache


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
    _SEMANTIC_MAX_CANDIDATES = 48
    _SEMANTIC_MAX_EMBED_FAILURES = 3
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
        mode: str = "keyword",
        ollama_base_url: str = "http://localhost:11434",
        embed_model: str = "nomic-embed-text",
        embed_cache_path: str = "./data/retrieval_embeddings.db",
    ) -> None:
        self.root = Path(root_path).resolve()
        self.chunk_max_chars = max(400, chunk_max_chars)
        self.max_file_bytes = max(10_000, max_file_bytes)
        self.include_suffixes = include_suffixes or self._INCLUDE_SUFFIXES
        normalized_mode = mode.strip().lower() if mode else "keyword"
        self.mode = "semantic" if normalized_mode in {"semantic", "hybrid"} else "keyword"
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.embed_model = embed_model
        self._embed_cache = EmbeddingCache(embed_cache_path)
        self._lock = Lock()
        self._chunks: list[CodeChunk] = []
        self._indexed_files = 0
        self._semantic_available: bool | None = None

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

    def reindex_path(self, rel_path: str) -> int:
        normalized = rel_path.strip().replace("\\", "/")
        if not normalized:
            return 0
        file_path = self._resolve_in_root(normalized)
        if not file_path.exists() or not file_path.is_file():
            with self._lock:
                self._chunks = [chunk for chunk in self._chunks if chunk.path != normalized]
            return 0

        new_chunks = self._chunk_file(file_path)
        with self._lock:
            self._chunks = [chunk for chunk in self._chunks if chunk.path != normalized]
            self._chunks.extend(new_chunks)
        return len(new_chunks)

    def _resolve_in_root(self, rel_path: str) -> Path:
        candidate = (self.root / rel_path).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError("Path escapes workspace root.")
        return candidate

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        path_prefix: str = "",
    ) -> list[CodeChunk]:
        safe_limit = max(1, min(limit, 20))
        if not self._chunks:
            self.reindex()
        with self._lock:
            candidates = list(self._chunks)

        if self.mode == "semantic":
            semantic_hits = self._semantic_search(query, candidates, safe_limit, path_prefix)
            if semantic_hits:
                return semantic_hits

        return self._keyword_search(query, candidates, safe_limit, path_prefix)

    def stats(self) -> dict[str, int | str]:
        with self._lock:
            indexed_files = self._indexed_files
            indexed_chunks = len(self._chunks)
        return {
            "indexed_files": indexed_files,
            "indexed_chunks": indexed_chunks,
            "mode": self.mode,
            "cached_embeddings": self._embed_cache.count(),
            "semantic_available": bool(self._semantic_available),
        }

    def _keyword_search(
        self,
        query: str,
        candidates: list[CodeChunk],
        safe_limit: int,
        path_prefix: str,
    ) -> list[CodeChunk]:
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

    def _semantic_search(
        self,
        query: str,
        candidates: list[CodeChunk],
        safe_limit: int,
        path_prefix: str,
    ) -> list[CodeChunk]:
        prefix = path_prefix.strip().replace("\\", "/")
        filtered = [
            chunk for chunk in candidates if not prefix or chunk.path.startswith(prefix)
        ]
        if not filtered:
            return []
        if len(filtered) > self._SEMANTIC_MAX_CANDIDATES:
            tokens = self._tokenize(query)
            ranked = sorted(
                (
                    (self._score_chunk(tokens, chunk), chunk)
                    for chunk in filtered
                ),
                key=lambda item: item[0],
                reverse=True,
            )
            shortlisted = [chunk for score, chunk in ranked if score > 0]
            filtered = (shortlisted or [chunk for _, chunk in ranked])[
                : self._SEMANTIC_MAX_CANDIDATES
            ]

        query_vec = self._embed_text(query)
        if query_vec is None:
            return []

        scored: list[CodeChunk] = []
        embed_failures = 0
        for chunk in filtered:
            chunk_vec = self._chunk_embedding(chunk)
            if chunk_vec is None:
                embed_failures += 1
                if embed_failures >= self._SEMANTIC_MAX_EMBED_FAILURES:
                    self._semantic_available = False
                    return []
                continue
            score = self._cosine_similarity(query_vec, chunk_vec)
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

    def _warm_semantic_cache(self, chunks: list[CodeChunk]) -> None:
        if not self._probe_semantic_backend():
            return
        for chunk in chunks[:200]:
            self._chunk_embedding(chunk)

    def _probe_semantic_backend(self) -> bool:
        if self._semantic_available is not None:
            return self._semantic_available
        probe = self._embed_text("semantic retrieval probe")
        self._semantic_available = probe is not None
        return self._semantic_available

    def _chunk_id(self, chunk: CodeChunk) -> str:
        digest = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()[:16]
        return f"{chunk.path}:{chunk.line_start}:{digest}"

    def _chunk_embedding(self, chunk: CodeChunk) -> list[float] | None:
        chunk_id = self._chunk_id(chunk)
        cached = self._embed_cache.get(chunk_id)
        if cached is not None:
            return cached
        embedding = self._embed_text(chunk.content)
        if embedding is None:
            return None
        content_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
        self._embed_cache.put(
            chunk_id,
            path=chunk.path,
            line_start=chunk.line_start,
            content_hash=content_hash,
            embedding=embedding,
        )
        return embedding

    def _embed_text(self, text: str) -> list[float] | None:
        payload = json.dumps({"model": self.embed_model, "prompt": text}).encode("utf-8")
        req = request.Request(
            f"{self.ollama_base_url}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=8) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError, OSError):
            return None
        embedding = body.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            return None
        return [float(item) for item in embedding]

    @staticmethod
    def _cosine_similarity(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

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
