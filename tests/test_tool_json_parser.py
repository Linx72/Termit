import unittest

from app.services.tool_json_parser import (
    ToolJsonParseError,
    extract_json_object,
    extract_json_objects,
    parse_loop_action,
)


class ToolJsonParserTests(unittest.TestCase):
    def test_extract_json_from_fenced_block(self) -> None:
        text = 'Here is the action:\n```json\n{"action":"tool","tool":"read_file","arguments":{"path":"."}}\n```'
        payload = extract_json_object(text)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["tool"], "read_file")

    def test_extract_multiple_json_objects(self) -> None:
        text = (
            '{"action":"tool","tool":"list_files","arguments":{"path":"."}}\n'
            '{"action":"final","answer":"done"}'
        )
        objects = extract_json_objects(text)
        self.assertEqual(len(objects), 2)

    def test_parse_loop_action_prefers_tool_over_final(self) -> None:
        text = (
            '{"action":"tool","tool":"apply_patch","arguments":{"path":"a.py","dry_run":true}}\n'
            '{"action":"final","answer":"ignored"}'
        )
        action = parse_loop_action(text)
        self.assertEqual(action["action"], "tool")
        self.assertEqual(action["tool"], "apply_patch")

    def test_parse_loop_action_missing_tool_raises(self) -> None:
        with self.assertRaises(ToolJsonParseError):
            parse_loop_action('{"action":"tool","arguments":{}}')

    def test_parse_loop_action_plain_text_is_final(self) -> None:
        action = parse_loop_action("All done.")
        self.assertEqual(action["action"], "final")
        self.assertEqual(action["answer"], "All done.")


if __name__ == "__main__":
    unittest.main()
