import os
import unittest
from unittest.mock import patch

from app.core.config import get_settings


class ConfigParsingTests(unittest.TestCase):
    def test_degrade_thresholds_invalid_values_fall_back_to_defaults(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TERMIT_DEGRADE_EMPTY_RATE": "not-a-number",
                "TERMIT_DEGRADE_FALLBACK_RATE": "bad-value",
            },
            clear=False,
        ):
            settings = get_settings()
        self.assertEqual(settings.degrade_empty_response_rate, 0.05)
        self.assertEqual(settings.degrade_fallback_rate, 0.35)

    def test_degrade_thresholds_are_clamped_to_range(self) -> None:
        with patch.dict(
            os.environ,
            {
                "TERMIT_DEGRADE_EMPTY_RATE": "-1.5",
                "TERMIT_DEGRADE_FALLBACK_RATE": "2.4",
            },
            clear=False,
        ):
            settings = get_settings()
        self.assertEqual(settings.degrade_empty_response_rate, 0.0)
        self.assertEqual(settings.degrade_fallback_rate, 1.0)


if __name__ == "__main__":
    unittest.main()
