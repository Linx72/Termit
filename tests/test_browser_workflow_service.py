import unittest

from app.domain.schemas import WebAutomationRequest
from app.services.browser_workflow_service import BrowserWorkflowService, WebWorkflowError


class BrowserWorkflowServiceTests(unittest.TestCase):
    def test_rejects_invalid_url_scheme(self) -> None:
        service = BrowserWorkflowService(fetcher=lambda _u, _t: (200, "<html></html>", "x"))
        with self.assertRaises(WebWorkflowError):
            service.run(WebAutomationRequest(url="ftp://example.com", objective="test"))

    def test_detects_blocker_login(self) -> None:
        html = "<html><title>Sign In</title><body>Please sign in with password</body></html>"
        service = BrowserWorkflowService(fetcher=lambda _u, _t: (200, html, "https://example.com/login"))
        result = service.run(WebAutomationRequest(url="https://example.com/login", objective="collect"))
        self.assertFalse(result.success)
        self.assertTrue(result.blocker_detected)
        self.assertIn("Login required", result.blocker_reason or "")

    def test_collects_evidence_and_honors_step_limit(self) -> None:
        html = (
            "<html><title>Docs</title><body>"
            "<a href='/a'>A</a><a href='https://example.org/b'>B</a>"
            "</body></html>"
        )
        service = BrowserWorkflowService(fetcher=lambda _u, _t: (200, html, "https://example.com/docs"))
        result = service.run(
            WebAutomationRequest(
                url="https://example.com/docs",
                objective="collect docs links",
                max_steps=2,
                capture_links_limit=5,
            )
        )
        self.assertTrue(result.success)
        self.assertIsNotNone(result.evidence)
        assert result.evidence is not None
        self.assertEqual(result.evidence.title, "Docs")
        self.assertEqual(len(result.evidence.links), 2)
        self.assertLessEqual(len(result.steps), 3)
        self.assertIn("max_steps", " ".join(result.steps))


if __name__ == "__main__":
    unittest.main()
