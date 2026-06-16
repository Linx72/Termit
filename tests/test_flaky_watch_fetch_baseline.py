from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.flaky_watch_fetch_baseline import FetchResult, fetch_baseline


class FlakyWatchFetchBaselineTests(unittest.TestCase):
    def test_missing_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = fetch_baseline(
                token="",
                repo="",
                artifact_name="flaky-watch-nightly",
                output_json_path=Path(tmp) / "baseline.json",
                output_zip_path=Path(tmp) / "baseline.zip",
            )
            self.assertEqual(result.status, "missing_credentials")
            self.assertFalse(result.baseline_found)

    @patch("scripts.flaky_watch_fetch_baseline._request_json")
    def test_missing_artifact(self, request_json) -> None:  # type: ignore[no-untyped-def]
        request_json.return_value = {"artifacts": []}
        with tempfile.TemporaryDirectory() as tmp:
            result = fetch_baseline(
                token="token",
                repo="owner/repo",
                artifact_name="flaky-watch-nightly",
                output_json_path=Path(tmp) / "baseline.json",
                output_zip_path=Path(tmp) / "baseline.zip",
            )
            self.assertEqual(result.status, "missing")
            self.assertFalse(result.baseline_found)

    @patch("scripts.flaky_watch_fetch_baseline._request_json")
    def test_rate_limit_error(self, request_json) -> None:  # type: ignore[no-untyped-def]
        request_json.side_effect = RuntimeError("HTTP Error 403: rate limit exceeded")
        with tempfile.TemporaryDirectory() as tmp:
            result = fetch_baseline(
                token="token",
                repo="owner/repo",
                artifact_name="flaky-watch-nightly",
                output_json_path=Path(tmp) / "baseline.json",
                output_zip_path=Path(tmp) / "baseline.zip",
            )
            self.assertEqual(result.status, "rate_limited")
            self.assertFalse(result.baseline_found)

    @patch("scripts.flaky_watch_fetch_baseline.zipfile.ZipFile")
    @patch("scripts.flaky_watch_fetch_baseline._download_file")
    @patch("scripts.flaky_watch_fetch_baseline._request_json")
    def test_available_baseline(self, request_json, download_file, zip_file_cls) -> None:  # type: ignore[no-untyped-def]
        request_json.return_value = {
            "artifacts": [
                {
                    "name": "flaky-watch-nightly",
                    "expired": False,
                    "created_at": "2026-06-15T00:00:00Z",
                    "archive_download_url": "https://example.com/archive.zip",
                }
            ]
        }
        zip_inst = zip_file_cls.return_value.__enter__.return_value
        zip_inst.namelist.return_value = ["flaky_watch_report.json"]
        zip_inst.read.return_value = b'{"pass_rate": 1.0, "suites": []}'
        with tempfile.TemporaryDirectory() as tmp:
            baseline_path = Path(tmp) / "baseline.json"
            result = fetch_baseline(
                token="token",
                repo="owner/repo",
                artifact_name="flaky-watch-nightly",
                output_json_path=baseline_path,
                output_zip_path=Path(tmp) / "baseline.zip",
            )
            self.assertEqual(result.status, "available")
            self.assertTrue(result.baseline_found)
            self.assertTrue(baseline_path.exists())
            download_file.assert_called_once()


if __name__ == "__main__":
    unittest.main()
