from __future__ import annotations

from pathlib import Path

from app.services.code_retrieval_service import CodeRetrievalService
from app.services.context_compaction import ContextCompactor
from app.services.symbol_index_service import SymbolIndexService


class ContextPackingService:
    def __init__(
        self,
        root_path: str = ".",
        max_file_chars: int = 2500,
        max_total_chars: int = 9000,
    ) -> None:
        self.root = Path(root_path).resolve()
        self.max_file_chars = max(256, max_file_chars)
        self.max_total_chars = max(1024, max_total_chars)

    def pack(
        self,
        *,
        query: str,
        changed_files: list[str],
        retrieval: CodeRetrievalService | None,
        symbol_index: SymbolIndexService | None,
        retrieval_limit: int = 5,
        path_prefix: str = "",
        exclude_paths: set[str] | None = None,
        include_retrieval: bool = True,
        include_neighbors: bool = True,
    ) -> str:
        excluded = {item.strip().replace("\\", "/") for item in (exclude_paths or set()) if item.strip()}
        sections: list[str] = []
        used_chars = 0

        def append_section(title: str, body: str) -> None:
            nonlocal used_chars
            chunk = f"### {title}\n{body.strip()}\n"
            if used_chars + len(chunk) > self.max_total_chars:
                remaining = self.max_total_chars - used_chars
                if remaining < 128:
                    return
                chunk = chunk[:remaining] + "\n...(truncated)\n"
            sections.append(chunk)
            used_chars += len(chunk)

        normalized_changed = [
            item.strip().replace("\\", "/")
            for item in changed_files
            if item.strip() and item.strip().replace("\\", "/") not in excluded
        ]
        for rel_path in normalized_changed[:8]:
            excerpt = self._read_excerpt(rel_path)
            if excerpt:
                append_section(f"Changed file: {rel_path}", excerpt)

        if include_retrieval and retrieval is not None:
            hits = retrieval.search(query, limit=retrieval_limit, path_prefix=path_prefix)
            if hits:
                append_section(
                    "Retrieval hits",
                    ContextCompactor.format_retrieval_context(
                        [(item.path, item.excerpt, item.score) for item in hits]
                    ),
                )

        if include_neighbors and symbol_index is not None and normalized_changed:
            neighbors = symbol_index.neighbor_paths(normalized_changed, limit=6)
            for rel_path in neighbors:
                if rel_path in excluded:
                    continue
                excerpt = self._read_excerpt(rel_path, max_chars=1200)
                if excerpt:
                    append_section(f"Related file: {rel_path}", excerpt)

        if not sections:
            return ""
        return "[Context packing]\n" + "\n".join(sections).strip()

    def pack_incremental(
        self,
        *,
        query: str,
        changed_files: list[str],
        seen_paths: set[str],
        retrieval: CodeRetrievalService | None,
        symbol_index: SymbolIndexService | None,
        retrieval_limit: int = 5,
        path_prefix: str = "",
        include_retrieval: bool = False,
    ) -> tuple[str, set[str]]:
        """Delta packing: только новые файлы; retrieval по умолчанию один раз на run."""
        packed = self.pack(
            query=query,
            changed_files=changed_files,
            retrieval=retrieval,
            symbol_index=symbol_index,
            retrieval_limit=retrieval_limit,
            path_prefix=path_prefix,
            exclude_paths=seen_paths,
            include_retrieval=include_retrieval,
            include_neighbors=True,
        )
        updated_seen = set(seen_paths)
        for rel_path in changed_files:
            normalized = rel_path.strip().replace("\\", "/")
            if normalized:
                updated_seen.add(normalized)
        return packed, updated_seen

    def _read_excerpt(self, rel_path: str, max_chars: int | None = None) -> str:
        limit = max_chars or self.max_file_chars
        target = (self.root / rel_path).resolve()
        if target != self.root and self.root not in target.parents:
            return ""
        if not target.is_file():
            return ""
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""
        if len(text) > limit:
            return text[: limit - 3] + "..."
        return text
