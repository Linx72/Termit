from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.flaky_watch_gate import RUNBOOK_HINT, _load_active_overrides, evaluate_gate, main


class FlakyWatchGateTests(unittest.TestCase):
    def test_gate_passes_when_stable(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": 0.0},
                {"suite": "tests.test_platform_e2e", "trend": "improved", "pass_rate_delta": 0.1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api", "tests.test_platform_e2e"},
            fail_on_any_regression=True,
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_fails_on_critical_regression(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "regressed", "pass_rate_delta": -0.1},
                {"suite": "tests.test_platform_e2e", "trend": "stable", "pass_rate_delta": 0.0},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api", "tests.test_platform_e2e"},
            fail_on_any_regression=True,
        )
        self.assertFalse(ok)
        self.assertIn("regressed", message.lower())
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_allows_noncritical_regression_when_flag_set(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": 0.0},
                {"suite": "tests.test_other", "trend": "regressed", "pass_rate_delta": -0.2},
            ]
        }
        ok, _ = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertTrue(ok)

    def test_gate_fail_on_any_regression_message_contains_runbook_hint(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": 0.0},
                {"suite": "tests.test_other", "trend": "regressed", "pass_rate_delta": -0.2},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=True,
        )
        self.assertFalse(ok)
        self.assertIn("regressed suites detected", message.lower())
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_fail_on_any_regression_is_case_insensitive(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_other", "trend": "Regressed", "pass_rate_delta": -0.1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=True,
        )
        self.assertFalse(ok)
        self.assertIn("regressed suites detected", message.lower())
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_allows_overridden_critical_regression(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "regressed", "pass_rate_delta": -0.2},
                {"suite": "tests.test_platform_e2e", "trend": "stable", "pass_rate_delta": 0.0},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api", "tests.test_platform_e2e"},
            fail_on_any_regression=True,
            override_reasons={"tests.test_agents_api": "known issue"},
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_allows_overridden_critical_regression_in_broad_policy(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "regressed", "pass_rate_delta": 0.0},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=True,
            override_reasons={"tests.test_agents_api": "temporary infra override"},
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_allows_overridden_critical_negative_delta_in_broad_policy(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "", "pass_rate_delta": -1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=True,
            override_reasons={"tests.test_agents_api": "temporary infra override"},
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_failure_message_contains_runbook_hint_for_negative_delta(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": -0.05},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertFalse(ok)
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_fails_on_mixed_case_regressed_for_critical_when_noncritical_allowed(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "ReGreSsEd", "pass_rate_delta": 0.0},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertFalse(ok)
        self.assertIn("critical suite tests.test_agents_api marked as regressed", message.lower())
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_fails_on_string_pass_rate_delta_for_critical_suite(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": "-0.1"},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertFalse(ok)
        self.assertIn("invalid pass_rate_delta type", message.lower())
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_fails_on_string_minus_one_pass_rate_delta_for_critical_suite(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": "-1"},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertFalse(ok)
        self.assertIn("invalid pass_rate_delta type", message.lower())
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_fails_on_boolean_pass_rate_delta_for_critical_suite(self) -> None:
        for value in (True, False):
            trend = {
                "suites": [
                    {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": value},
                ]
            }
            ok, message = evaluate_gate(
                trend,
                critical_suites={"tests.test_agents_api"},
                fail_on_any_regression=False,
            )
            self.assertFalse(ok)
            self.assertIn("invalid pass_rate_delta type", message.lower())
            self.assertIn(RUNBOOK_HINT, message)

    def test_gate_allows_none_pass_rate_delta_for_critical_when_stable(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": None},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_allows_zero_pass_rate_delta_for_critical_when_stable(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": 0},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_allows_positive_pass_rate_delta_for_critical_when_stable(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": 0.1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_allows_missing_trend_when_delta_is_zero_for_critical_suite(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "", "pass_rate_delta": 0},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_allows_missing_trend_when_delta_is_none_for_critical_suite(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "", "pass_rate_delta": None},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_fails_when_trend_missing_but_delta_negative_for_critical_suite(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "", "pass_rate_delta": -0.1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertFalse(ok)
        self.assertIn("pass_rate_delta=-0.1", message)
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_fails_when_delta_is_minus_one_for_critical_suite(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable", "pass_rate_delta": -1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertFalse(ok)
        self.assertIn("pass_rate_delta=-1", message)
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_allows_minus_one_for_noncritical_when_noncritical_regressions_allowed(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_other", "trend": "stable", "pass_rate_delta": -1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_fails_on_noncritical_regressed_minus_one_when_any_regression_enabled(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_other", "trend": "regressed", "pass_rate_delta": -1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=True,
        )
        self.assertFalse(ok)
        self.assertIn("regressed suites detected", message.lower())
        self.assertIn("tests.test_other", message)
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_fails_on_noncritical_uppercase_regressed_when_any_regression_enabled(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_other", "trend": "REGRESSED", "pass_rate_delta": 0},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=True,
        )
        self.assertFalse(ok)
        self.assertIn("regressed suites detected", message.lower())
        self.assertIn("tests.test_other", message)
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_fails_on_noncritical_negative_delta_when_any_regression_enabled(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_other", "trend": "", "pass_rate_delta": -1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=True,
        )
        self.assertFalse(ok)
        self.assertIn("regressed suites detected", message.lower())
        self.assertIn("tests.test_other", message)
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_allows_noncritical_negative_delta_when_any_regression_but_overridden(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_other", "trend": "", "pass_rate_delta": -1},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=True,
            override_reasons={"tests.test_other": "known flaky infra incident"},
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_gate_fails_when_trend_missing_but_delta_string_zero_for_critical_suite(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "", "pass_rate_delta": "0"},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertFalse(ok)
        self.assertIn("invalid pass_rate_delta type", message.lower())
        self.assertIn(RUNBOOK_HINT, message)

    def test_gate_allows_missing_pass_rate_delta_key_for_critical_when_stable(self) -> None:
        trend = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "stable"},
            ]
        }
        ok, message = evaluate_gate(
            trend,
            critical_suites={"tests.test_agents_api"},
            fail_on_any_regression=False,
        )
        self.assertTrue(ok)
        self.assertIn("passed", message.lower())

    def test_load_active_overrides_respects_expiry(self) -> None:
        payload = {
            "overrides": [
                {
                    "suite": "tests.test_agents_api",
                    "reason": "known flaky",
                    "expires_at": "2099-01-01T00:00:00Z",
                },
                {
                    "suite": "tests.test_platform_e2e",
                    "reason": "old",
                    "expires_at": "2001-01-01T00:00:00Z",
                },
            ]
        }
        from datetime import datetime, timezone

        active = _load_active_overrides(payload, now_utc=datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertIn("tests.test_agents_api", active)
        self.assertNotIn("tests.test_platform_e2e", active)

    def test_main_appends_active_overrides_suffix(self) -> None:
        trend_payload = {
            "suites": [
                {"suite": "tests.test_agents_api", "trend": "regressed", "pass_rate_delta": -0.3},
            ]
        }
        overrides_payload = {
            "overrides": [
                {
                    "suite": "tests.test_agents_api",
                    "reason": "known flaky",
                    "expires_at": "2099-01-01T00:00:00Z",
                }
            ]
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            trend_path = Path(tmpdir) / "trend.json"
            overrides_path = Path(tmpdir) / "overrides.json"
            trend_path.write_text(json.dumps(trend_payload), encoding="utf-8")
            overrides_path.write_text(json.dumps(overrides_payload), encoding="utf-8")

            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(trend_path),
                "--overrides",
                str(overrides_path),
                "--now-utc",
                "2026-01-01T00:00:00Z",
            ]
            stream = io.StringIO()
            with patch("sys.argv", fake_argv):
                with redirect_stdout(stream):
                    rc = main()
        self.assertEqual(rc, 0)
        output = stream.getvalue()
        self.assertIn("Flaky trend gate passed.", output)
        self.assertIn("Active overrides: tests.test_agents_api (known flaky).", output)

    def test_main_rejects_invalid_now_utc(self) -> None:
        trend_payload = {"suites": []}
        with tempfile.TemporaryDirectory() as tmpdir:
            trend_path = Path(tmpdir) / "trend.json"
            trend_path.write_text(json.dumps(trend_payload), encoding="utf-8")
            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(trend_path),
                "--now-utc",
                "not-a-timestamp",
            ]
            with patch("sys.argv", fake_argv):
                with self.assertRaises(SystemExit) as ctx:
                    main()
        self.assertEqual(str(ctx.exception), "Invalid --now-utc timestamp.")

    def test_main_help_mentions_runbook_path(self) -> None:
        stream = io.StringIO()
        with patch("sys.argv", ["flaky_watch_gate.py", "--help"]):
            with redirect_stdout(stream):
                with self.assertRaises(SystemExit) as ctx:
                    main()
        self.assertEqual(ctx.exception.code, 0)
        self.assertIn("docs/NIGHTLY_FLAKY_GATE_RUNBOOK_RU.md", stream.getvalue())

    def test_main_fails_on_invalid_trend_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            trend_path = Path(tmpdir) / "trend.json"
            trend_path.write_text("{invalid-json", encoding="utf-8")
            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(trend_path),
            ]
            with patch("sys.argv", fake_argv):
                with self.assertRaises(SystemExit) as ctx:
                    main()
        self.assertIn("Invalid trend JSON:", str(ctx.exception))

    def test_main_fails_on_missing_trend_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_trend = Path(tmpdir) / "missing.json"
            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(missing_trend),
            ]
            with patch("sys.argv", fake_argv):
                with self.assertRaises(SystemExit) as ctx:
                    main()
        self.assertIn("Invalid trend JSON:", str(ctx.exception))

    def test_main_rejects_non_object_trend_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            trend_path = Path(tmpdir) / "trend.json"
            trend_path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")
            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(trend_path),
            ]
            with patch("sys.argv", fake_argv):
                with self.assertRaises(SystemExit) as ctx:
                    main()
        self.assertEqual(str(ctx.exception), "Invalid trend payload.")

    def test_main_fails_on_invalid_overrides_json(self) -> None:
        trend_payload = {"suites": []}
        with tempfile.TemporaryDirectory() as tmpdir:
            trend_path = Path(tmpdir) / "trend.json"
            overrides_path = Path(tmpdir) / "overrides.json"
            trend_path.write_text(json.dumps(trend_payload), encoding="utf-8")
            overrides_path.write_text("{invalid-json", encoding="utf-8")
            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(trend_path),
                "--overrides",
                str(overrides_path),
            ]
            with patch("sys.argv", fake_argv):
                with self.assertRaises(SystemExit) as ctx:
                    main()
        self.assertIn("Invalid overrides JSON:", str(ctx.exception))

    def test_main_rejects_non_object_overrides_payload(self) -> None:
        trend_payload = {"suites": []}
        with tempfile.TemporaryDirectory() as tmpdir:
            trend_path = Path(tmpdir) / "trend.json"
            overrides_path = Path(tmpdir) / "overrides.json"
            trend_path.write_text(json.dumps(trend_payload), encoding="utf-8")
            overrides_path.write_text(json.dumps(["not-an-object"]), encoding="utf-8")
            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(trend_path),
                "--overrides",
                str(overrides_path),
            ]
            with patch("sys.argv", fake_argv):
                with self.assertRaises(SystemExit) as ctx:
                    main()
        self.assertEqual(str(ctx.exception), "Invalid overrides payload.")

    def test_main_fails_on_empty_overrides_file(self) -> None:
        trend_payload = {"suites": []}
        with tempfile.TemporaryDirectory() as tmpdir:
            trend_path = Path(tmpdir) / "trend.json"
            overrides_path = Path(tmpdir) / "overrides.json"
            trend_path.write_text(json.dumps(trend_payload), encoding="utf-8")
            overrides_path.write_text("", encoding="utf-8")
            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(trend_path),
                "--overrides",
                str(overrides_path),
            ]
            with patch("sys.argv", fake_argv):
                with self.assertRaises(SystemExit) as ctx:
                    main()
        self.assertIn("Invalid overrides JSON:", str(ctx.exception))

    def test_main_accepts_overrides_file_without_overrides_key(self) -> None:
        trend_payload = {"suites": []}
        with tempfile.TemporaryDirectory() as tmpdir:
            trend_path = Path(tmpdir) / "trend.json"
            overrides_path = Path(tmpdir) / "overrides.json"
            trend_path.write_text(json.dumps(trend_payload), encoding="utf-8")
            overrides_path.write_text(json.dumps({"note": "no overrides yet"}), encoding="utf-8")
            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(trend_path),
                "--overrides",
                str(overrides_path),
            ]
            stream = io.StringIO()
            with patch("sys.argv", fake_argv):
                with redirect_stdout(stream):
                    rc = main()
        self.assertEqual(rc, 0)
        output = stream.getvalue()
        self.assertIn("Flaky trend gate passed.", output)
        self.assertNotIn("Active overrides:", output)

    def test_main_ignores_overrides_path_when_it_is_directory(self) -> None:
        trend_payload = {"suites": []}
        with tempfile.TemporaryDirectory() as tmpdir:
            trend_path = Path(tmpdir) / "trend.json"
            overrides_dir = Path(tmpdir) / "overrides-dir"
            overrides_dir.mkdir(parents=True, exist_ok=True)
            trend_path.write_text(json.dumps(trend_payload), encoding="utf-8")
            fake_argv = [
                "flaky_watch_gate.py",
                "--trend",
                str(trend_path),
                "--overrides",
                str(overrides_dir),
            ]
            stream = io.StringIO()
            with patch("sys.argv", fake_argv):
                with redirect_stdout(stream):
                    rc = main()
        self.assertEqual(rc, 0)
        output = stream.getvalue()
        self.assertIn("Flaky trend gate passed.", output)
        self.assertIn("Overrides ignored: path is not a file", output)


if __name__ == "__main__":
    unittest.main()
