from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from app.domain.schemas import ChatRequest, TaskType
from app.services.context_enrichment_service import ContextEnrichmentService
from app.services.context_packing_service import ContextPackingService
from app.services.project_rules_store import ProjectRulesStore
from app.services.repo_map_service import RepoMapService
from app.services.symbol_index_service import SymbolIndexService


class Phase2Tests(unittest.TestCase):
    def test_repo_map_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app").mkdir()
            (root / "app" / "main.py").write_text("print('ok')\n", encoding="utf-8")
            (root / "README.md").write_text("# Demo\n\nHello repo\n", encoding="utf-8")
            summary = RepoMapService(str(root)).build_summary()
            self.assertIn("Repo map", summary)
            self.assertIn("README", summary)
            self.assertIn("app/", summary)

    def test_symbol_index_finds_python_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sample.py").write_text("def greet():\n    return 1\n", encoding="utf-8")
            service = SymbolIndexService(str(root))
            service.reindex()
            hits = service.search("greet", limit=5)
            self.assertGreaterEqual(len(hits), 1)
            self.assertEqual(hits[0].name, "greet")

    def test_context_packing_includes_changed_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "changed.py"
            target.write_text("value = 42\n", encoding="utf-8")
            packed = ContextPackingService(str(root)).pack(
                query="update value",
                changed_files=["changed.py"],
                retrieval=None,
                symbol_index=None,
            )
            self.assertIn("Changed file: changed.py", packed)
            self.assertIn("value = 42", packed)

    def test_project_rules_injected_into_chat_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rules = ProjectRulesStore(base_dir=str(Path(tmp) / "projects"))
            rules.save_rules(
                "demo",
                project_rules="Always run tests.",
                user_rules="Reply in Russian.",
                skills=["fix-ci"],
            )
            enrichment = ContextEnrichmentService(rules_store=rules, repo_map_enabled=False)
            messages = asyncio.run(enrichment.build_system_messages(
                ChatRequest(
                    message="fix bug",
                    task_type=TaskType.coding,
                    project_id="demo",
                    use_retrieval=False,
                    use_repo_map=False,
                    use_context_packing=False,
                )
            ))
            self.assertEqual(len(messages), 1)
            self.assertIn("Always run tests", messages[0].content)
            self.assertIn("Reply in Russian", messages[0].content)

    def test_context_enrichment_infers_symbol_and_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "auth.py").write_text(
                "def check_quota():\n    return True\n\n"
                "def middleware():\n    return check_quota()\n",
                encoding="utf-8",
            )
            enrichment = ContextEnrichmentService(
                repo_map_enabled=False,
                symbol_index=SymbolIndexService(str(root)),
            )
            enrichment._symbol_index.reindex()
            messages = asyncio.run(enrichment.build_system_messages(
                ChatRequest(
                    message="Where is middleware?",
                    task_type=TaskType.coding,
                    project_id="demo",
                    use_retrieval=False,
                    use_repo_map=False,
                    use_context_packing=False,
                )
            ))
            combined = "\n".join(m.content for m in messages)
            self.assertIn("middleware", combined)
            self.assertIn("Symbol graph", combined)

    def test_agent_templates_list(self) -> None:
        from app.services.agent_templates_store import AgentTemplatesStore

        store = AgentTemplatesStore(file_path="data/agent_templates.json")
        templates = store.list_templates()
        self.assertGreaterEqual(len(templates), 9)
        ids = {item.template_id for item in templates}
        self.assertIn("fix-ci", ids)
        self.assertIn("cross-platform-flutter", ids)
        self.assertIn("game-unity", ids)

    def test_phase2_api_routes(self) -> None:
        import tempfile

        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from app.api.routes.projects import router as projects_router
        from app.api.routes.retrieval import router as retrieval_router
        from app.services.agent_templates_store import AgentTemplatesStore
        from app.services.project_rules_store import ProjectRulesStore
        from app.services.repo_map_service import RepoMapService
        from app.services.symbol_index_service import SymbolIndexService
        from app.state import (
            get_agent_templates_store,
            get_project_rules_store,
            get_repo_map_service,
            get_symbol_index_service,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sample.py").write_text("def build_summary():\n    return 1\n", encoding="utf-8")
            rules_dir = root / "projects"
            rules_store = ProjectRulesStore(base_dir=str(rules_dir))
            repo_map = RepoMapService(str(root))
            symbol_index = SymbolIndexService(str(root))
            templates = AgentTemplatesStore(file_path="data/agent_templates.json")

            app = FastAPI()
            app.include_router(projects_router)
            app.include_router(retrieval_router)
            app.dependency_overrides[get_project_rules_store] = lambda: rules_store
            app.dependency_overrides[get_repo_map_service] = lambda: repo_map
            app.dependency_overrides[get_symbol_index_service] = lambda: symbol_index
            app.dependency_overrides[get_agent_templates_store] = lambda: templates

            client = TestClient(app)
            repo_resp = client.get("/api/retrieval/repo-map")
            self.assertEqual(repo_resp.status_code, 200)
            self.assertIn("summary", repo_resp.json())

            templates_resp = client.get("/api/projects/agent-templates")
            self.assertEqual(templates_resp.status_code, 200)
            self.assertGreaterEqual(len(templates_resp.json()["templates"]), 3)

            rules_resp = client.get("/api/projects/demo/rules")
            self.assertEqual(rules_resp.status_code, 200)

            symbols = client.post(
                "/api/retrieval/symbols/search",
                json={"query": "build_summary", "limit": 5},
            )
            self.assertEqual(symbols.status_code, 200)
            self.assertGreaterEqual(len(symbols.json()["matches"]), 1)


if __name__ == "__main__":
    unittest.main()
