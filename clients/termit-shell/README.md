# Termit Shell (macOS, no Electron)

Native Termit wrapper for macOS built with Swift (`AppKit + WKWebView`).

This shell loads the already built web UI from `clients/termit-desktop/dist` and exposes
the same `window.termitDesktop` bridge used by the existing desktop runtime:

- `getLauncherConfig` / `setLauncherConfig`
- `ensureServer`
- `showNotification`
- `getDocFileUrl` / `getDocPath` / `openDocExternal`

## Run

From repo root:

```bash
./scripts/run_termit_shell.sh
```

## Package as .app

From repo root:

```bash
./scripts/package_termit_shell.sh
open clients/termit-shell/release/TermitShell.app
```

This creates a standalone bundle with embedded renderer/docs:

- `clients/termit-shell/release/TermitShell.app`

Optional release signing/notarization:

```bash
export TERMIT_CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)"
export TERMIT_NOTARY_PROFILE="termitshell-notary-profile"
./scripts/package_termit_shell.sh
```

- `TERMIT_CODESIGN_IDENTITY` enables `codesign --deep --options runtime`
- `TERMIT_NOTARY_PROFILE` enables `notarytool submit` + `stapler`

Release pipeline:

- `.github/workflows/release.yml` now builds `TermitShell.app` on macOS
- picks signing/notary credentials from GitHub Secrets:
  - `TERMIT_CODESIGN_IDENTITY`
  - `TERMIT_NOTARY_PROFILE`
- runs post-build launch smoke for `TermitShell.app`
- creates `clients/termit-shell/release/TermitShell.app.zip`
- uploads it as a GitHub Release asset for tag builds (`v*`)

Manual run:

```bash
cd clients/termit-shell
swift build -c release
.build/release/termit-shell \
  --renderer-root /absolute/path/to/clients/termit-desktop/dist \
  --docs-root /absolute/path/to/clients/termit-desktop/docs/pdf
```

Optional:

- `--user-data-dir /path` to override launcher config storage

Launcher config is stored in:

- `~/Library/Application Support/TermitShell/termit-launcher.json`
