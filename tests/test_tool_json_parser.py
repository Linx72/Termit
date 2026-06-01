import unittest

from app.services.tool_json_parser import (
    ToolJsonParseError,
    extract_json_object,
    parse_loop_action,
    repair_json_text,
)


class ToolJsonParserTests(unittest.TestCase):
    def test_extract_json_from_fenced_block(self) -> None:
        text = 'Here is the action:\n```json\n{"action":"tool","tool":"read_file","arguments":{"path":"."}}\n```'
        payload = extract_json_object(text)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["tool"], "read_file")

    def test_extract_multiple_json_objects(self) -> None:
        from app.services.tool_json_parser import extract_json_objects

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

    def test_repair_trailing_comma_and_python_literals(self) -> None:
        text = '{"action":"tool","tool":"read_file","arguments":{"path":"."},}'
        payload = extract_json_object(text)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["tool"], "read_file")

    def test_repair_python_bool_and_none(self) -> None:
        text = '{"action":"tool","tool":"execute_command","arguments":{"dry_run":True,"confirmed":False,"path":None}}'
        payload = extract_json_object(text)
        self.assertIsNotNone(payload)
        assert payload is not None
        arguments = payload["arguments"]
        assert isinstance(arguments, dict)
        self.assertTrue(arguments["dry_run"])
        self.assertFalse(arguments["confirmed"])
        self.assertIsNone(arguments["path"])

    def test_repair_unquoted_keys(self) -> None:
        text = '{action:"tool",tool:"read_file",arguments:{path:"app/main.py"}}'
        payload = extract_json_object(text)
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["tool"], "read_file")

    def test_parse_python_literal_dict(self) -> None:
        text = "{'action': 'final', 'answer': 'done via literal'}"
        action = parse_loop_action(text)
        self.assertEqual(action["action"], "final")
        self.assertEqual(action["answer"], "done via literal")

    def test_parse_type_alias_and_name_alias(self) -> None:
        text = '{"type":"tool","name":"list_files","args":{"path":"."}}'
        action = parse_loop_action(text)
        self.assertEqual(action["action"], "tool")
        self.assertEqual(action["tool"], "list_files")

    def test_parse_action_with_trailing_prose(self) -> None:
        text = (
            'Sure.\n```json\n{"action":"tool","tool":"read_file","arguments":{"path":"README.md"}}\n```\n'
            "Let me know if you need more."
        )
        action = parse_loop_action(text)
        self.assertEqual(action["tool"], "read_file")

    def test_repair_json_text_normalizes_smart_quotes(self) -> None:
        repaired = repair_json_text('{"action":"final","answer":"ok",}')
        self.assertIn('"answer"', repaired)
        self.assertNotIn(",}", repaired)


if __name__ == "__main__":
    unittest.main()
