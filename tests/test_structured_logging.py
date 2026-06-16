import json
import logging
import sys
import unittest

from app.core.structured_logging import JsonLogFormatter, configure_logging, redact_sensitive


class StructuredLoggingTests(unittest.TestCase):
    def test_redact_sensitive_masks_api_key(self) -> None:
        raw = "Authorization: Bearer sk-secret-token-12345"
        self.assertIn("***", redact_sensitive(raw))
        self.assertNotIn("sk-secret", redact_sensitive(raw))

    def test_json_formatter_includes_error_class(self) -> None:
        formatter = JsonLogFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="termit.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=exc_info,
        )
        line = formatter.format(record)
        payload = json.loads(line)
        self.assertEqual(payload["error_class"], "ValueError")
        self.assertIn("exc", payload)

    def test_json_formatter_includes_extra_fields(self) -> None:
        formatter = JsonLogFormatter()
        record = logging.LogRecord(
            name="termit.request",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="GET /health -> 200 (3ms)",
            args=(),
            exc_info=None,
        )
        record.trace_id = "tr_abc"
        record.latency_ms = 3
        payload = json.loads(formatter.format(record))
        self.assertEqual(payload["trace_id"], "tr_abc")
        self.assertEqual(payload["latency_ms"], 3)

    def test_configure_logging_json_mode(self) -> None:
        configure_logging(json_logs=True, level="WARNING")
        root = logging.getLogger()
        self.assertTrue(any(isinstance(h.formatter, JsonLogFormatter) for h in root.handlers))
        self.assertEqual(root.level, logging.WARNING)


if __name__ == "__main__":
    unittest.main()
