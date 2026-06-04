"""Phase 0: Media Studio discovery artifacts — schemas, ADR, eval registry."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_against_schema(instance: object, schema: dict[str, object]) -> list[str]:
    """Minimal validator (no jsonschema dep): required keys + primitive types."""
    errors: list[str] = []

    def check(obj: object, sch: dict[str, object], path: str) -> None:
        if sch.get("type") == "object":
            if not isinstance(obj, dict):
                errors.append(f"{path}: expected object")
                return
            required = sch.get("required", [])
            if isinstance(required, list):
                for key in required:
                    if key not in obj:
                        errors.append(f"{path}: missing required '{key}'")
            props = sch.get("properties", {})
            if isinstance(props, dict):
                for key, sub in props.items():
                    if key in obj and isinstance(sub, dict):
                        check(obj[key], sub, f"{path}.{key}")
            if sch.get("additionalProperties") is False:
                allowed = set(props.keys()) if isinstance(props, dict) else set()
                if isinstance(required, list):
                    allowed |= set(required)
                for key in obj:
                    if key not in allowed:
                        errors.append(f"{path}: unexpected property '{key}'")
        elif sch.get("type") == "array":
            if not isinstance(obj, list):
                errors.append(f"{path}: expected array")
                return
            items = sch.get("items")
            if isinstance(items, dict):
                for index, item in enumerate(obj):
                    check(item, items, f"{path}[{index}]")
            min_items = sch.get("minItems")
            if isinstance(min_items, int) and len(obj) < min_items:
                errors.append(f"{path}: minItems {min_items}")
        elif sch.get("type") == "string":
            if not isinstance(obj, str):
                errors.append(f"{path}: expected string")
                return
            min_len = sch.get("minLength")
            if isinstance(min_len, int) and len(obj) < min_len:
                errors.append(f"{path}: minLength {min_len}")
            pattern = sch.get("pattern")
            if isinstance(pattern, str) and not re.fullmatch(pattern, obj):
                errors.append(f"{path}: pattern mismatch")
            enum = sch.get("enum")
            if isinstance(enum, list) and obj not in enum:
                errors.append(f"{path}: not in enum")
        elif sch.get("type") == "number":
            if not isinstance(obj, (int, float)):
                errors.append(f"{path}: expected number")
                return
            minimum = sch.get("minimum")
            maximum = sch.get("maximum")
            if isinstance(minimum, (int, float)) and obj < minimum:
                errors.append(f"{path}: below minimum")
            if isinstance(maximum, (int, float)) and obj > maximum:
                errors.append(f"{path}: above maximum")
        elif sch.get("type") == "integer":
            if not isinstance(obj, int) or isinstance(obj, bool):
                errors.append(f"{path}: expected integer")
        elif sch.get("type") == "boolean":
            if not isinstance(obj, bool):
                errors.append(f"{path}: expected boolean")

    check(instance, schema, "$")
    return errors


class MediaStudioPhase0Tests(unittest.TestCase):
    def test_adr_and_roadmap_exist(self) -> None:
        for name in (
            "docs/MEDIA_STUDIO_ADR_RU.md",
            "docs/MEDIA_STUDIO_PHASE0_RU.md",
            "docs/MEDIA_STUDIO_ROADMAP_RU.md",
        ):
            self.assertTrue((ROOT / name).is_file(), name)

    def test_storyboard_example_valid(self) -> None:
        schema = _load_json(ROOT / "data/media/schemas/storyboard.schema.json")
        fixture = _load_json(ROOT / "data/media/examples/storyboard.example.json")
        errors = _validate_against_schema(fixture, schema)
        self.assertEqual(errors, [], errors)

    def test_brief_example_valid(self) -> None:
        schema = _load_json(ROOT / "data/media/schemas/creative_brief.schema.json")
        fixture = _load_json(ROOT / "data/media/examples/creative_brief.example.json")
        errors = _validate_against_schema(fixture, schema)
        self.assertEqual(errors, [], errors)

    def test_brand_kit_example_valid(self) -> None:
        schema = _load_json(ROOT / "data/media/schemas/brand_kit.schema.json")
        fixture = _load_json(ROOT / "data/media/examples/brand_kit.termit-default.json")
        errors = _validate_against_schema(fixture, schema)
        self.assertEqual(errors, [], errors)

    def test_storyboard_duration_matches_scenes(self) -> None:
        sb = _load_json(ROOT / "data/media/examples/storyboard.example.json")
        assert isinstance(sb, dict)
        total = float(sb["total_duration_sec"])
        scenes = sb["scenes"]
        assert isinstance(scenes, list)
        scene_sum = sum(float(s["duration_sec"]) for s in scenes)
        self.assertAlmostEqual(total, scene_sum, places=1)

    def test_tools_v1_lists_generate_image(self) -> None:
        tools_doc = _load_json(ROOT / "data/media/tools_v1.json")
        assert isinstance(tools_doc, dict)
        tools = tools_doc.get("tools", [])
        names = {t["name"] for t in tools if isinstance(t, dict) and "name" in t}
        self.assertIn("generate_image", names)
        self.assertIn("estimate_media_cost", names)

    def test_eval_scenarios_media_registry(self) -> None:
        scenarios = _load_json(ROOT / "data/eval_scenarios_media.json")
        assert isinstance(scenarios, list)
        ids = [s["id"] for s in scenarios if isinstance(s, dict)]
        self.assertIn("MS1", ids)
        self.assertIn("MS10", ids)
        ms1 = next(s for s in scenarios if s.get("id") == "MS1")
        self.assertEqual(ms1.get("runner"), "media_schema")

    def test_skill_media_studio_exists(self) -> None:
        path = ROOT / "data/skills/media-studio/SKILL.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("media-studio", text)
        self.assertIn("estimate_media_cost", text)


if __name__ == "__main__":
    unittest.main()
