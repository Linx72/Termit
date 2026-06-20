from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.services.cohesion_partition_service import CohesionPartitionService
from app.services.agent_tool_schema import (
    build_tool_schema_response,
    expand_tools_after_use,
    resolve_described_tools,
    select_initial_tool_names,
)
from app.services.symbol_index_service import SymbolIndexService


class CohesionPartitionTests(unittest.TestCase):
    def test_partition_groups_connected_files(self) -> None:
        adjacency = {
            "app/a.py": {"app/b.py"},
            "app/b.py": {"app/a.py"},
            "web/x.tsx": {"web/y.tsx"},
            "web/y.tsx": {"web/x.tsx"},
        }
        service = CohesionPartitionService(hub_degree_threshold=99)
        parts = service.partition_paths(
            ["app/a.py", "web/x.tsx"],
            adjacency,
            max_partitions=3,
        )
        self.assertEqual(len(parts), 2)
        flat = {tuple(group) for group in parts}
        self.assertIn(("app/a.py", "app/b.py"), flat)
        self.assertIn(("web/x.tsx", "web/y.tsx"), flat)

    def test_symbol_index_file_adjacency_from_python_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "alpha.py").write_text(
                "from beta import helper\n\ndef run():\n    return helper()\n",
                encoding="utf-8",
            )
            (root / "beta.py").write_text(
                "def helper():\n    return 1\n",
                encoding="utf-8",
            )
            index = SymbolIndexService(str(root))
            adjacency = index.file_adjacency()
            self.assertIn("alpha.py", adjacency)
            self.assertTrue({"beta.py"} & adjacency.get("alpha.py", set()))


class DescribeToolsTests(unittest.TestCase):
    def test_describe_tools_expands_lazy_set(self) -> None:
        enabled = ["list_files", "read_file", "apply_patch", "execute_command", "describe_tools"]
        active = set(select_initial_tool_names(enabled, "explore codebase"))
        expanded = expand_tools_after_use(
            "describe_tools",
            enabled,
            active,
            describe_request=["apply_patch"],
        )
        self.assertIn("apply_patch", expanded)

    def test_build_tool_schema_response_json(self) -> None:
        payload = build_tool_schema_response(["list_files", "read_file"])
        self.assertIn("list_files", payload)
        self.assertIn("schemas", payload)

    def test_resolve_described_tools_filters_unknown(self) -> None:
        names = resolve_described_tools(
            {"tool_names": ["apply_patch", "unknown_tool"]},
            ["apply_patch", "read_file"],
        )
        self.assertEqual(names, ["apply_patch"])


if __name__ == "__main__":
    unittest.main()
