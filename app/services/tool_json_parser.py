from __future__ import annotations

import json
import re
from typing import Optional


class ToolJsonParseError(Exception):
    pass


_FENCE_PATTERN = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _strip_outer_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _find_balanced_json_objects(text: str) -> list[str]:
    objects: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        if text[index] != "{":
            index += 1
            continue
        depth = 0
        in_string = False
        escaped = False
        start = index
        for cursor in range(index, length):
            char = text[cursor]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    objects.append(text[start : cursor + 1])
                    index = cursor + 1
                    break
        else:
            index += 1
    return objects


def _iter_json_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        normalized = candidate.strip()
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    add(_strip_outer_fence(text))
    for match in _FENCE_PATTERN.finditer(text):
        add(match.group(1))
    for candidate in _find_balanced_json_objects(text):
        add(candidate)
    return candidates


def extract_json_object(text: str) -> Optional[dict[str, object]]:
    for candidate in _iter_json_candidates(text):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def extract_json_objects(text: str) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    seen: set[str] = set()
    for candidate in _iter_json_candidates(text):
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        fingerprint = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        found.append(payload)
    return found


def parse_loop_action(text: str) -> dict[str, object]:
    objects = extract_json_objects(text)
    if not objects:
        payload = extract_json_object(text)
        if payload is None:
            stripped = text.strip()
            if stripped.startswith("{") and not stripped.endswith("}"):
                raise ToolJsonParseError("Incomplete JSON object in model response.")
            return {"action": "final", "answer": stripped}

        objects = [payload]

    for payload in objects:
        action = str(payload.get("action", "final")).lower()
        if action == "tool":
            tool = str(payload.get("tool", "")).strip()
            if not tool:
                raise ToolJsonParseError("Tool action missing 'tool' field.")
            arguments = payload.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ToolJsonParseError("Tool action 'arguments' must be a JSON object.")
            return {"action": "tool", "tool": tool, "arguments": arguments}

    for payload in reversed(objects):
        action = str(payload.get("action", "final")).lower()
        if action == "final":
            answer = str(payload.get("answer", "")).strip()
            if answer:
                return {"action": "final", "answer": answer}

    last = objects[-1]
    answer = str(last.get("answer", text)).strip()
    if not answer:
        raise ToolJsonParseError("Final action missing non-empty 'answer'.")
    return {"action": "final", "answer": answer}
