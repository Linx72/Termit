from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.cross_platform import router as cross_platform_router
from app.domain.schemas import TaskType
from app.services.cross_platform_dev_service import CrossPlatformDevService


class CrossPlatformDevServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CrossPlatformDevService()

    def test_detects_cross_platform_task(self) -> None:
        self.assertTrue(
            self.service.is_cross_platform_task(
                "Build Flutter app for iOS and Android with shared auth"
            )
        )
        self.assertFalse(self.service.is_cross_platform_task("Fix typo in README"))

    def test_decompose_flutter_includes_platform_shells(self) -> None:
        profile, platforms, tasks = self.service.decompose(
            "Flutter MVP for iOS and Windows",
            stack_id="flutter",
            platforms=["ios", "windows"],
        )
        self.assertEqual(profile.stack_id, "flutter")
        self.assertEqual({p.value for p in platforms}, {"ios", "windows"})
        step_ids = [t.step_id for t in tasks]
        self.assertIn("platform_ios", step_ids)
        self.assertIn("platform_windows", step_ids)

    def test_unity_game_includes_game_loop(self) -> None:
        _, _, tasks = self.service.decompose(
            "Unity mobile game with pause menu",
            stack_id="unity",
        )
        step_ids = [t.step_id for t in tasks]
        self.assertIn("game_loop", step_ids)
        self.assertIn("unity_input_actions", step_ids)

    def test_format_atomic_prompt_includes_verify(self) -> None:
        profile, platforms, tasks = self.service.decompose(
            "Flutter app for iOS",
            stack_id="flutter",
            platforms=["ios"],
        )
        prompt = self.service.format_atomic_prompt(
            "Flutter app for iOS",
            profile,
            platforms,
            tasks[0],
            index=0,
            total=len(tasks),
        )
        self.assertIn("Atomic step 1/", prompt)
        self.assertIn("Verify:", prompt)

    def test_build_agent_context_lists_steps(self) -> None:
        block = self.service.build_agent_context("Godot game for Android and iOS")
        self.assertIn("cross-platform-atomic", block)
        self.assertIn("godot", block)

    def test_prepare_first_step_prompt(self) -> None:
        profile, platforms, tasks, prompt = self.service.prepare_first_step_prompt(
            "SwiftUI app for iPhone and Mac",
            stack_id="swift_multiplatform",
            platforms=["ios", "macos"],
        )
        self.assertEqual(profile.stack_id, "swift_multiplatform")
        self.assertGreaterEqual(len(tasks), 5)
        self.assertIn("scope", prompt.lower())

    def test_plan_orchestration_steps_for_mobile_task(self) -> None:
        steps = self.service.plan_orchestration_steps(
            "Godot game for Android and iOS",
            TaskType.coding,
        )
        self.assertEqual(steps[0], "analyze_requirements")
        self.assertIn("detect_stack_and_targets", steps)
        self.assertTrue(any(step.startswith("atomic_") for step in steps))
        self.assertEqual(steps[-1], "compose_delivery")


class CrossPlatformApiTests(unittest.TestCase):
    def test_stacks_and_decompose_endpoints(self) -> None:
        from app.api.routes.projects import router as projects_router

        app = FastAPI()
        app.include_router(cross_platform_router)
        app.include_router(projects_router)
        client = TestClient(app)

        stacks_resp = client.get("/api/dev/cross-platform/stacks")
        self.assertEqual(stacks_resp.status_code, 200)
        stacks = stacks_resp.json()["stacks"]
        self.assertGreaterEqual(len(stacks), 6)
        ids = {item["stack_id"] for item in stacks}
        self.assertIn("flutter", ids)
        self.assertIn("unity", ids)

        decompose_resp = client.post(
            "/api/dev/cross-platform/decompose",
            json={
                "goal": "SwiftUI app for iPhone and Mac",
                "stack_id": "swift_multiplatform",
                "platforms": ["ios", "macos"],
            },
        )
        self.assertEqual(decompose_resp.status_code, 200)
        body = decompose_resp.json()
        self.assertEqual(body["stack_id"], "swift_multiplatform")
        self.assertEqual(body["agent_template_id"], "cross-platform-swift")
        self.assertGreaterEqual(len(body["atomic_tasks"]), 5)
        self.assertIn("first_step_prompt", body)
        self.assertIn("skill_id", body)

        prepare_resp = client.post(
            "/api/dev/cross-platform/prepare",
            json={
                "goal": "SwiftUI app for iPhone and Mac",
                "stack_id": "swift_multiplatform",
                "platforms": ["ios", "macos"],
                "step_index": 1,
            },
        )
        self.assertEqual(prepare_resp.status_code, 200)
        prepared = prepare_resp.json()
        self.assertEqual(prepared["step_index"], 1)
        self.assertIn("prompt", prepared)
        self.assertEqual(prepared["skill_id"], "cross-platform-atomic")

        bad = client.post(
            "/api/dev/cross-platform/decompose",
            json={"goal": "test", "stack_id": "unknown-stack"},
        )
        self.assertEqual(bad.status_code, 400)

        ensure = client.post("/api/projects/agent-templates/cross-platform-flutter/ensure-agent")
        self.assertEqual(ensure.status_code, 200)
        self.assertEqual(ensure.json()["name"], "Cross-platform Flutter")

        record = client.post(
            "/api/dev/cross-platform/record-step",
            json={
                "goal": "Flutter MVP",
                "stack_id": "flutter",
                "step_id": "scope",
                "step_index": 0,
                "verify_ok": True,
                "verify_detail": "ok",
            },
        )
        self.assertEqual(record.status_code, 200)
        self.assertIn("recorded", record.json())


class CrossPlatformEvalRunnerTests(unittest.TestCase):
    def test_x1_cross_platform_decompose_passes(self) -> None:
        from app.services.eval_service import EvalService

        service = EvalService(scenarios_path="./data/eval_scenarios.json")
        result = service.run_scenario("X1")
        self.assertEqual(result["status"], "passed", msg=result.get("message"))


class MultiAgentCrossPlatformPlanTests(unittest.TestCase):
    def test_build_plan_uses_atomic_steps(self) -> None:
        from app.services.multi_agent_orchestrator import MultiAgentOrchestrator

        steps = MultiAgentOrchestrator._build_plan(
            "Create Flutter app for iOS and Android",
            TaskType.coding,
        )
        self.assertIn("detect_stack_and_targets", steps)
        self.assertTrue(any(s.startswith("atomic_") for s in steps))


class TaskServiceCrossPlatformTests(unittest.TestCase):
    def test_cross_platform_task_uses_atomic_plan(self) -> None:
        from app.domain.schemas import TaskCreateRequest, TaskType
        from app.services.task_service import TaskService
        from app.services.task_store import InMemoryTaskStore
        from app.services.tooling_service import ToolingService

        service = TaskService(
            ToolingService(root_path="."),
            InMemoryTaskStore(),
            max_attempts=2,
        )
        created = service.create_task(
            TaskCreateRequest(
                input="Build Flutter app for iOS and Android with shared auth",
                task_type=TaskType.coding,
            )
        )
        task = service.get_task(created.task_id)
        self.assertEqual(task.state.value, "completed")
        step_messages = [
            event.message
            for event in task.events
            if event.event_type == "step_started"
        ]
        self.assertTrue(any("atomic_" in message for message in step_messages))
