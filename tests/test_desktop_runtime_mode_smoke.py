import unittest
from pathlib import Path


class DesktopRuntimeModeSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.app_tsx = (self.root / "clients" / "termit-desktop" / "src" / "App.tsx").read_text(
            encoding="utf-8"
        )
        self.runtime_ts = (
            self.root / "clients" / "termit-desktop" / "src" / "desktopRuntime.ts"
        ).read_text(encoding="utf-8")
        self.ipc_ts = (self.root / "clients" / "termit-desktop" / "shared" / "ipc.ts").read_text(
            encoding="utf-8"
        )

    def test_runtime_mode_is_exposed_in_settings_ui(self) -> None:
        self.assertIn('id="runtimeMode"', self.app_tsx)
        self.assertIn('value={settings.runtimeMode}', self.app_tsx)
        self.assertIn('option value="auto"', self.app_tsx)
        self.assertIn('option value="desktop"', self.app_tsx)
        self.assertIn('option value="web"', self.app_tsx)

    def test_runtime_meta_server_control_guard_exists(self) -> None:
        self.assertIn("runtimeMeta.serverControl", self.app_tsx)
        self.assertIn("serverControl: isDesktop", self.runtime_ts)

    def test_unified_modals_are_used_for_core_flows(self) -> None:
        self.assertIn("<WorkspaceFilePickerModal", self.app_tsx)
        self.assertIn("<PromptInputModal", self.app_tsx)
        self.assertIn("setFilePickerTarget(\"attachments\")", self.app_tsx)
        self.assertIn("setFilePickerTarget(\"folder\")", self.app_tsx)
        self.assertIn("setFilePickerTarget(\"composer\")", self.app_tsx)
        self.assertIn("setSymbolModalOpen(true)", self.app_tsx)
        self.assertIn("setWebModalOpen(true)", self.app_tsx)
        self.assertIn("setPathModalTarget(\"workspace\")", self.app_tsx)
        self.assertIn("setPathModalTarget(\"repo\")", self.app_tsx)

    def test_legacy_prompt_and_picker_branches_are_absent(self) -> None:
        self.assertNotIn("window.prompt(", self.app_tsx)
        self.assertNotIn("pickWorkspace(", self.ipc_ts)
        self.assertNotIn("pickRepoRoot(", self.ipc_ts)
        self.assertNotIn("pickWorkspaceFile(", self.ipc_ts)


if __name__ == "__main__":
    unittest.main()
