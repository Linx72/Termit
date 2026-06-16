# Подпись и notarization Termit Desktop (macOS)

Native desktop — **`TermitShell.app`** (Swift + WKWebView + Vite UI). Electron удалён.

## Быстрая сборка

```bash
./scripts/package_desktop.sh
open clients/termit-shell/release/TermitShell.app
```

## Подписанный релиз (локально)

1. Сертификат **Developer ID Application** в Keychain.
2. Credentials для notarytool:
   ```bash
   xcrun notarytool store-credentials "termit-notary" \
     --apple-id "you@example.com" \
     --team-id "TEAMID" \
     --password "@keychain:AC_PASSWORD"
   ```
3. Сборка:
   ```bash
   export TERMIT_CODESIGN_IDENTITY="Developer ID Application: Name (TEAMID)"
   export TERMIT_NOTARY_PROFILE="termit-notary"
   ./scripts/package_desktop.sh
   ```
4. Проверка:
   ```bash
   ./scripts/verify_desktop_signature.sh
   ```

## CI (GitHub Release)

Workflow [`.github/workflows/release.yml`](file:///Users/amoros/Projects/Termit/.github/workflows/release.yml) запускается на push тега `v*`.

Secrets (repo Settings → Secrets):

| Secret | Назначение |
|--------|------------|
| `TERMIT_CODESIGN_IDENTITY` | Имя identity для `codesign` |
| `TERMIT_NOTARY_PROFILE` | Keychain profile для `notarytool` |

Без secrets собирается **unsigned** `.app` (для smoke/QA).

Артефакты: `TermitShell.app.zip` + `.sha256` на GitHub Release.

## Entitlements

Генерируются в `scripts/package_termit_shell.sh`:

- `com.apple.security.cs.allow-jit` — WKWebView
- `com.apple.security.network.client` — Termit API / Ollama

## Связанные файлы

- [`scripts/package_termit_shell.sh`](file:///Users/amoros/Projects/Termit/scripts/package_termit_shell.sh)
- [`scripts/package_desktop.sh`](file:///Users/amoros/Projects/Termit/scripts/package_desktop.sh)
- [`clients/termit-shell/README.md`](file:///Users/amoros/Projects/Termit/clients/termit-shell/README.md)
