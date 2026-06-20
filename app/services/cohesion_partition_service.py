"""Cohesion-aware partition файлов для parallel explore/coder (ось B, Co-Coder MVP).

Группирует tightly-coupled файлы по call/import graph, чтобы subagent'ы
минимизировали cross-partition context transfer.
"""

from __future__ import annotations

from collections import defaultdict


class CohesionPartitionService:
    """Graph partition по symbol index (call edges + imports)."""

    def __init__(self, hub_degree_threshold: int = 6) -> None:
        self._hub_degree_threshold = max(2, hub_degree_threshold)

    def partition_paths(
        self,
        seed_paths: list[str],
        adjacency: dict[str, set[str]],
        *,
        max_partitions: int = 3,
    ) -> list[list[str]]:
        """Разбить seed+соседей на связные кластеры; hub-файлы — отдельно."""
        normalized_seeds = [
            item.strip().replace("\\", "/")
            for item in seed_paths
            if item and item.strip()
        ]
        if not normalized_seeds:
            return []

        candidates: set[str] = set(normalized_seeds)
        for seed in list(normalized_seeds):
            for neighbor in adjacency.get(seed, set()):
                candidates.add(neighbor)

        if len(candidates) <= 1:
            return [sorted(candidates)]

        hubs = {
            path
            for path in candidates
            if len(adjacency.get(path, set()) & candidates) >= self._hub_degree_threshold
        }

        parent: dict[str, str] = {}

        def find(node: str) -> str:
            parent.setdefault(node, node)
            if parent[node] != node:
                parent[node] = find(parent[node])
            return parent[node]

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for path in candidates:
            find(path)
        for path in candidates:
            if path in hubs:
                continue
            for neighbor in adjacency.get(path, set()):
                if neighbor in candidates and neighbor not in hubs:
                    union(path, neighbor)

        clusters: dict[str, list[str]] = defaultdict(list)
        for path in sorted(candidates):
            if path in hubs:
                clusters[f"hub:{path}"].append(path)
            else:
                clusters[find(path)].append(path)

        ordered = sorted(clusters.values(), key=len, reverse=True)
        safe_max = max(1, min(max_partitions, 8))
        if len(ordered) <= safe_max:
            return [sorted(group) for group in ordered if group]

        merged: list[list[str]] = ordered[: safe_max - 1]
        tail: list[str] = []
        for group in ordered[safe_max - 1 :]:
            tail.extend(group)
        if tail:
            merged.append(sorted(set(tail)))
        return [sorted(group) for group in merged if group]

    @staticmethod
    def summarize_partition(index: int, paths: list[str]) -> str:
        """Краткая строка для orchestrator explore phase."""
        preview = ", ".join(paths[:5])
        suffix = f" (+{len(paths) - 5} more)" if len(paths) > 5 else ""
        return f"partition {index + 1} ({len(paths)} files): {preview}{suffix}"
