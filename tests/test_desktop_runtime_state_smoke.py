import re
import unittest
from pathlib import Path


class DesktopRuntimeStateSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.settings_ts = (self.root / "clients" / "termit-desktop" / "src" / "settings.ts").read_text(
            encoding="utf-8"
        )
        self.runtime_ts = (
            self.root / "clients" / "termit-desktop" / "src" / "desktopRuntime.ts"
        ).read_text(encoding="utf-8")
        self.app_tsx = (self.root / "clients" / "termit-desktop" / "src" / "App.tsx").read_text(
            encoding="utf-8"
        )

    def test_settings_default_runtime_mode_is_auto(self) -> None:
        self.assertIn('runtimeMode: "auto"', self.settings_ts)
        self.assertIn('runtimeMode: "auto" | "desktop" | "web"', self.settings_ts)

    def test_runtime_meta_contract_is_consistent(self) -> None:
        self.assertIn("interface DesktopRuntimeMeta", self.runtime_ts)
        self.assertIn("requested: runtimePreference", self.runtime_ts)
        self.assertIn("nativeAvailable: Boolean(native)", self.runtime_ts)
        self.assertIn("serverControl: isDesktop", self.runtime_ts)

    def test_app_persists_runtime_preference(self) -> None:
        self.assertIn("setDesktopRuntimePreference(settings.runtimeMode);", self.app_tsx)
        self.assertRegex(
            self.app_tsx,
            re.compile(r"runtimeMeta\.mode\s*===\s*\"web\""),
        )
        self.assertRegex(
            self.app_tsx,
            re.compile(r"runtimeMeta\.mode\s*===\s*\"desktop\""),
        )

    def test_no_legacy_runtime_prompts_in_app(self) -> None:
        self.assertNotIn("window.prompt(", self.app_tsx)
        self.assertNotIn("window.confirm(", self.app_tsx)


if __name__ == "__main__":
    unittest.main()
