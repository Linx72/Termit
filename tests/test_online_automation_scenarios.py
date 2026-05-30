import unittest

from app.domain.schemas import WebAutomationRequest
from app.services.browser_workflow_service import BrowserWorkflowService


class OnlineAutomationScenariosTests(unittest.TestCase):
    def test_scenario_1_basic_success(self) -> None:
        html = "<html><title>Home</title><body><a href='/docs'>Docs</a></body></html>"
        service = BrowserWorkflowService(fetcher=lambda _u, _t: (200, html, "https://site.test"))
        result = service.run(WebAutomationRequest(url="https://site.test", objective="collect"))
        self.assertTrue(result.success)
        self.assertFalse(result.blocker_detected)
        self.assertEqual(result.evidence.title, "Home")

    def test_scenario_2_redirect_keeps_final_url(self) -> None:
        html = "<html><title>Landing</title></html>"
        service = BrowserWorkflowService(
            fetcher=lambda _u, _t: (200, html, "https://site.test/final")
        )
        result = service.run(WebAutomationRequest(url="https://site.test/start", objective="collect"))
        self.assertTrue(result.success)
        self.assertEqual(result.evidence.final_url, "https://site.test/final")

    def test_scenario_3_login_blocker(self) -> None:
        html = "<html><body>Sign in to continue</body></html>"
        service = BrowserWorkflowService(fetcher=lambda _u, _t: (200, html, "https://site.test/login"))
        result = service.run(WebAutomationRequest(url="https://site.test/login", objective="collect"))
        self.assertFalse(result.success)
        self.assertTrue(result.blocker_detected)

    def test_scenario_4_captcha_blocker(self) -> None:
        html = "<html><body>Please solve CAPTCHA challenge</body></html>"
        service = BrowserWorkflowService(fetcher=lambda _u, _t: (200, html, "https://site.test/check"))
        result = service.run(WebAutomationRequest(url="https://site.test/check", objective="collect"))
        self.assertFalse(result.success)
        self.assertTrue(result.blocker_detected)

    def test_scenario_5_access_denied_status(self) -> None:
        html = "<html><body>Access denied</body></html>"
        service = BrowserWorkflowService(fetcher=lambda _u, _t: (403, html, "https://site.test/protected"))
        result = service.run(WebAutomationRequest(url="https://site.test/protected", objective="collect"))
        self.assertFalse(result.success)
        self.assertIn("status code 403", result.blocker_reason or "")

    def test_scenario_6_link_limit_applies(self) -> None:
        html = (
            "<html><body>"
            "<a href='/a'>A</a><a href='/b'>B</a><a href='/c'>C</a><a href='/d'>D</a>"
            "</body></html>"
        )
        service = BrowserWorkflowService(fetcher=lambda _u, _t: (200, html, "https://site.test"))
        result = service.run(
            WebAutomationRequest(url="https://site.test", objective="collect", capture_links_limit=2)
        )
        self.assertTrue(result.success)
        self.assertEqual(len(result.evidence.links), 2)

    def test_scenario_7_max_steps_stops_loop(self) -> None:
        html = "<html><title>Steps</title></html>"
        service = BrowserWorkflowService(fetcher=lambda _u, _t: (200, html, "https://site.test"))
        result = service.run(
            WebAutomationRequest(url="https://site.test", objective="collect", max_steps=1)
        )
        self.assertTrue(result.success)
        self.assertIn("max_steps", " ".join(result.steps))

    def test_scenario_8_fetch_failure_reported(self) -> None:
        def failing_fetcher(_url: str, _timeout: int) -> tuple[int, str, str]:
            raise RuntimeError("network offline")

        service = BrowserWorkflowService(fetcher=failing_fetcher)
        result = service.run(WebAutomationRequest(url="https://site.test", objective="collect"))
        self.assertFalse(result.success)
        self.assertIn("Fetch failed", result.blocker_reason or "")


if __name__ == "__main__":
    unittest.main()
