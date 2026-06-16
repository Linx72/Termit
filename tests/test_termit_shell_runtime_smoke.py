import unittest
from pathlib import Path


class TermitShellRuntimeSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.shell_main = (
            self.root / "clients" / "termit-shell" / "Sources" / "TermitShell" / "main.swift"
        ).read_text(encoding="utf-8")
        self.package_script = (self.root / "scripts" / "package_termit_shell.sh").read_text(
            encoding="utf-8"
        )

    def test_bridge_exposes_expected_termit_desktop_api_methods(self) -> None:
        for method in [
            "getLauncherConfig",
            "setLauncherConfig",
            "ensureServer",
            "showNotification",
            "getDocFileUrl",
            "getDocPath",
            "openDocExternal",
        ]:
            self.assertIn(f'"{method}"', self.shell_main)

        self.assertIn("window.termitDesktop = {", self.shell_main)
        self.assertIn('if (!window.webkit?.messageHandlers?.termitBridge)', self.shell_main)

    def test_bundle_mode_defaults_exist(self) -> None:
        self.assertIn("func bundleDefaults()", self.shell_main)
        self.assertIn('Bundle.main.bundleURL.pathExtension == "app"', self.shell_main)
        self.assertIn('resources.appendingPathComponent("renderer"', self.shell_main)
        self.assertIn('resources.appendingPathComponent("docs/pdf"', self.shell_main)

    def test_renderer_loader_normalizes_vite_html_for_wkwebview(self) -> None:
        self.assertIn("struct RendererCache", self.shell_main)
        self.assertIn("private func normalizeRendererHtml(_ html: String)", self.shell_main)
        self.assertIn("private func loadRenderer(into webView: WKWebView)", self.shell_main)
        self.assertIn('pattern: #"<meta\\s+http-equiv="Content-Security-Policy"[^>]*>"#', self.shell_main)
        self.assertIn("webView.loadFileURL(indexUrl, allowingReadAccessTo: cacheRoot)", self.shell_main)

    def test_packaging_script_supports_release_signing_and_notary(self) -> None:
        self.assertIn("TERMIT_CODESIGN_IDENTITY", self.package_script)
        self.assertIn("TERMIT_NOTARY_PROFILE", self.package_script)
        self.assertIn("codesign --force --deep --options runtime", self.package_script)
        self.assertIn("xcrun notarytool submit", self.package_script)
        self.assertIn("xcrun stapler staple", self.package_script)

    def test_package_desktop_wraps_termit_shell(self) -> None:
        desktop_script = (self.root / "scripts" / "package_desktop.sh").read_text(encoding="utf-8")
        self.assertIn("package_termit_shell.sh", desktop_script)
        verify_script = (self.root / "scripts" / "verify_desktop_signature.sh").read_text(encoding="utf-8")
        self.assertIn("codesign --verify", verify_script)
        self.assertIn("spctl -a", verify_script)

    def test_training_loop_full_script(self) -> None:
        script = (self.root / "scripts" / "training_loop_full.sh").read_text(encoding="utf-8")
        self.assertIn("training_loop_week2.sh", script)
        self.assertIn("eval_regression_report.py", script)
        self.assertIn("run-suite", script)


if __name__ == "__main__":
    unittest.main()
