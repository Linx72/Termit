"""Тесты standalone eval builder."""

from __future__ import annotations

import unittest

from app.services.eval_standalone import (
    build_standalone_eval_service,
    default_post_dpo_scenario_ids,
    extra_eval_scenario_paths,
)
from app.core.config import get_settings


class EvalStandaloneTests(unittest.TestCase):
    def test_extra_paths_include_terminal(self) -> None:
        settings = get_settings()
        paths = extra_eval_scenario_paths(settings)
        self.assertTrue(any("terminal" in path for path in paths))

    def test_post_dpo_ids_include_swe_and_terminal(self) -> None:
        ids = default_post_dpo_scenario_ids().split(",")
        self.assertIn("SWE1", ids)
        self.assertIn("TB3", ids)

    def test_standalone_service_model_bound_count(self) -> None:
        service = build_standalone_eval_service(root_path=".")
        self.assertEqual(len(service.model_bound_tool_scenario_ids()), 12)


if __name__ == "__main__":
    unittest.main()
