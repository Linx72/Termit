"""Convert non-JSON-native Python values for safe serialization."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any


def json_safe(value: object) -> object:
    """Recursively convert sets/frozensets to sorted lists for JSON encoding."""
    if isinstance(value, set):
        return sorted(value, key=str)
    if isinstance(value, frozenset):
        return sorted(value, key=str)
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def json_dumps(value: object, **kwargs: Any) -> str:
    """json.dumps after json_safe (sets, nested dicts from literal_eval, etc.)."""
    return json.dumps(json_safe(value), **kwargs)
