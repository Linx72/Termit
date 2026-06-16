"""Structured JSON logging with secret redaction for Termit runtime."""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import datetime, timezone
from typing import Any

_REDACT_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?i)(api[_-]?key|token|password|secret|authorization)\s*[:=]\s*['\"]?[^\s'\",}]+"
        ),
        r"\1=***",
    ),
    (re.compile(r"(?i)Bearer\s+\S+"), "Bearer ***"),
    (re.compile(r"(?i)\bsk-[A-Za-z0-9_-]+\b"), "sk-***"),
    (re.compile(r"(?i)(X-API-Key:\s*)\S+"), r"\1***"),
]


def redact_sensitive(text: str) -> str:
    """Mask common credential patterns in log lines."""
    result = text
    for pattern, repl in _REDACT_PATTERNS:
        result = pattern.sub(repl, result)
    return result


class JsonLogFormatter(logging.Formatter):
    """Emit one JSON object per log line (Loki/ELK friendly)."""

    _SKIP_KEYS = frozenset(
        {
            "name",
            "msg",
            "args",
            "created",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "module",
            "msecs",
            "message",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "thread",
            "threadName",
            "exc_info",
            "exc_text",
            "stack_info",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive(record.getMessage()),
        }
        for key, value in record.__dict__.items():
            if key.startswith("_") or key in self._SKIP_KEYS:
                continue
            payload[key] = value
        if record.exc_info:
            exc_info = sys.exc_info() if record.exc_info is True else record.exc_info
            if exc_info and exc_info[0] is not None:
                payload["error_class"] = exc_info[0].__name__
                payload["exc"] = redact_sensitive(self.formatException(exc_info))
        return json.dumps(payload, ensure_ascii=True)


def configure_logging(*, json_logs: bool, level: str = "INFO") -> None:
    """Configure root logger once at process startup."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler()
    if json_logs:
        handler.setFormatter(JsonLogFormatter())
    else:
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(level.upper())
