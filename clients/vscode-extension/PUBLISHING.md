# VS Code Marketplace publishing (Termit extension)

## Prerequisites

- [Visual Studio Marketplace publisher](https://marketplace.visualstudio.com/manage) account
- `npm install -g @vscode/vsce`
- Built extension: `clients/vscode-extension/dist/extension.js`

## Build

```bash
cd clients/termit-client && npm install && npm run build
cd ../vscode-extension && npm install && npm run build
```

## Package (.vsix)

```bash
cd clients/vscode-extension
vsce package
# Creates termit-vscode-0.4.0.vsix
```

## Install locally

```bash
code --install-extension termit-vscode-0.4.0.vsix
```

## Publish to Marketplace

1. Create publisher `termit` at https://marketplace.visualstudio.com/manage/createpublisher (must match `package.json` `publisher`).
2. Generate Personal Access Token with **Marketplace (Publish)** scope.
3. Login:

```bash
vsce login termit
```

4. Publish:

```bash
cd clients/vscode-extension
vsce publish
# or: vsce publish 0.4.0
```

## Settings users need

| Setting | Description |
|---------|-------------|
| `termit.baseUrl` | Termit API URL (default `http://127.0.0.1:8765`) |
| `termit.apiKey` | `X-API-Key` when auth enabled (operator for patches) |

See [`README.md`](README.md) and [`../CLIENT_UX.md`](../CLIENT_UX.md).
