import tempfile
import unittest
from pathlib import Path

from app.services.symbol_index_service import SymbolIndexService


class SymbolGraphTests(unittest.TestCase):
    def test_call_edges_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            sample = Path(tmp) / "sample.py"
            sample.write_text(
                "def helper():\n"
                "    return 1\n\n"
                "def main():\n"
                "    return helper()\n",
                encoding="utf-8",
            )
            service = SymbolIndexService(root_path=tmp)
            service.reindex()
            callees = service.callees_of("main")
            self.assertEqual(len(callees), 1)
            self.assertEqual(callees[0].callee_name, "helper")
            callers = service.callers_of("helper")
            self.assertEqual(len(callers), 1)
            self.assertEqual(callers[0].caller_name, "main")


if __name__ == "__main__":
    unittest.main()
