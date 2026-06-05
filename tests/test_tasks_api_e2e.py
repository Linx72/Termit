import unittest

from fastapi.testclient import TestClient

from app.main import app


class TasksApiE2ETests(unittest.TestCase):
    def test_ten_tasks_complete_and_expose_events(self) -> None:
        client = TestClient(app)
        task_inputs = [
            "Summarize repository setup",
            "Inspect app folder and report findings",
            "Readme quality check",
            "Generate execution report for coding task",
            "Review task flow and verify output",
            "Explain recent architecture decisions",
            "Collect diagnostics for general task",
            "Inspect workspace and finalize report",
            "Validate deterministic task handling",
            "Run complete plan execute verify report cycle",
        ]

        for text in task_inputs:
            create_resp = client.post(
                "/api/tasks",
                json={"input": text, "task_type": "general", "mode": "auto", "project_id": "e2e-project"},
            )
            self.assertEqual(create_resp.status_code, 200)
            task_id = create_resp.json()["task_id"]

            status_resp = client.get(f"/api/tasks/{task_id}")
            self.assertEqual(status_resp.status_code, 200)
            body = status_resp.json()
            self.assertEqual(body["state"], "completed")
            self.assertEqual(body["project_id"], "e2e-project")
            self.assertIn("Task execution completed", body["report"])

            events_resp = client.get(f"/api/tasks/{task_id}/events")
            self.assertEqual(events_resp.status_code, 200)
            events = events_resp.json()
            self.assertGreaterEqual(len(events), 4)
            self.assertEqual(events[-1]["event_type"], "task_completed")


if __name__ == "__main__":
    unittest.main()
