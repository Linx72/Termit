import AppKit
import Foundation
import WebKit
@preconcurrency import UserNotifications

struct LauncherConfig: Codable {
    var repoRoot: String
    var autoStartServer: Bool
}

struct BridgeResult: Codable {
    var ok: Bool
    var message: String
}

private let defaultBaseUrl = "http://127.0.0.1:8765"

final class ServerLauncher {
    let fileManager = FileManager.default
    let userDataDir: URL
    let docsRoot: URL
    private var serverProcess: Process?

    init(userDataDir: URL, docsRoot: URL) {
        self.userDataDir = userDataDir
        self.docsRoot = docsRoot
    }

    var configPath: URL {
        userDataDir.appendingPathComponent("termit-launcher.json")
    }

    func readConfig() -> LauncherConfig {
        guard let data = try? Data(contentsOf: configPath) else {
            return LauncherConfig(repoRoot: "", autoStartServer: false)
        }
        guard let decoded = try? JSONDecoder().decode(LauncherConfig.self, from: data) else {
            return LauncherConfig(repoRoot: "", autoStartServer: false)
        }
        return decoded
    }

    func writeConfig(_ config: LauncherConfig) throws {
        try fileManager.createDirectory(at: userDataDir, withIntermediateDirectories: true)
        let data = try JSONEncoder().encode(config)
        try data.write(to: configPath, options: .atomic)
    }

    func docPath(for docId: String) -> URL {
        let fileName: String
        switch docId {
        case "training":
            fileName = "TERMIT_TRAINING_RU.pdf"
        default:
            fileName = "TERMIT_HELP_RU.pdf"
        }
        return docsRoot.appendingPathComponent(fileName)
    }

    func checkHealth(baseUrl: String) -> Bool {
        let normalized = baseUrl.hasSuffix("/") ? String(baseUrl.dropLast()) : baseUrl
        let endpoint = normalized + "/health"
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/usr/bin/curl")
        process.arguments = ["-fsS", "--max-time", "2.5", endpoint]
        process.standardOutput = FileHandle.nullDevice
        process.standardError = FileHandle.nullDevice
        do {
            try process.run()
            process.waitUntilExit()
            return process.terminationStatus == 0
        } catch {
            return false
        }
    }

    func ensureServer(baseUrl: String) -> BridgeResult {
        let normalized = baseUrl.isEmpty ? defaultBaseUrl : baseUrl
        if checkHealth(baseUrl: normalized) {
            return BridgeResult(ok: true, message: "Termit server already running")
        }

        let config = readConfig()
        if config.repoRoot.isEmpty {
            return BridgeResult(ok: false, message: "Set Termit repo path in launcher settings first.")
        }

        let repoUrl = URL(fileURLWithPath: config.repoRoot)
        var isDir: ObjCBool = false
        guard fileManager.fileExists(atPath: repoUrl.path, isDirectory: &isDir), isDir.boolValue else {
            return BridgeResult(ok: false, message: "Configured repo path does not exist.")
        }

        let uvicornPath = repoUrl.appendingPathComponent(".venv/bin/uvicorn").path
        guard fileManager.isExecutableFile(atPath: uvicornPath) else {
            return BridgeResult(
                ok: false,
                message: "Missing .venv/bin/uvicorn. Create venv and install requirements first."
            )
        }

        if let existing = serverProcess, existing.isRunning {
            Thread.sleep(forTimeInterval: 0.8)
            if checkHealth(baseUrl: normalized) {
                return BridgeResult(ok: true, message: "Termit server started")
            }
        }

        let process = Process()
        process.currentDirectoryURL = repoUrl
        process.executableURL = URL(fileURLWithPath: uvicornPath)
        process.arguments = ["app.main:app", "--host", "127.0.0.1", "--port", "8765"]

        let nullHandle = FileHandle.nullDevice
        process.standardOutput = nullHandle
        process.standardError = nullHandle
        process.standardInput = nullHandle

        do {
            try process.run()
            serverProcess = process
        } catch {
            return BridgeResult(ok: false, message: "Failed to start server: \(error.localizedDescription)")
        }

        for _ in 0..<20 {
            Thread.sleep(forTimeInterval: 0.4)
            if checkHealth(baseUrl: normalized) {
                return BridgeResult(ok: true, message: "Termit server started on :8765")
            }
        }
        return BridgeResult(ok: false, message: "Server did not respond on :8765")
    }
}

final class BridgeHandler: NSObject, WKScriptMessageHandler {
    private let launcher: ServerLauncher
    private let notificationMode: NotificationMode
    private weak var webView: WKWebView?

    enum NotificationMode {
        case system
        case fallback
    }

    init(launcher: ServerLauncher, notificationMode: NotificationMode) {
        self.launcher = launcher
        self.notificationMode = notificationMode
        super.init()
    }

    func attach(webView: WKWebView) {
        self.webView = webView
    }

    private func sendResponse(id: String, payload: Any) {
        guard let webView else {
            return
        }
        let data: Data
        if let typed = payload as? [String: Any] {
            data = (try? JSONSerialization.data(withJSONObject: typed)) ?? Data("null".utf8)
        } else {
            data = (try? JSONSerialization.data(withJSONObject: payload)) ?? Data("null".utf8)
        }
        let json = String(data: data, encoding: .utf8) ?? "null"
        let script = "window.__termitShellResolve(\(quoted(id)), \(json));"
        DispatchQueue.main.async {
            webView.evaluateJavaScript(script, completionHandler: nil)
        }
    }

    private func sendError(id: String, message: String) {
        guard let webView else {
            return
        }
        let script = "window.__termitShellReject(\(quoted(id)), \(quoted(message)));"
        DispatchQueue.main.async {
            webView.evaluateJavaScript(script, completionHandler: nil)
        }
    }

    private func quoted(_ value: String) -> String {
        let escaped = value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "\\n")
            .replacingOccurrences(of: "\r", with: "\\r")
        return "\"\(escaped)\""
    }

    private func dictionary(_ body: Any) -> [String: Any]? {
        body as? [String: Any]
    }

    private func payloadResult(_ result: BridgeResult) -> [String: Any] {
        ["ok": result.ok, "message": result.message]
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.name == "termitBridge",
              let payload = dictionary(message.body),
              let id = payload["id"] as? String,
              let method = payload["method"] as? String else {
            return
        }

        switch method {
        case "getLauncherConfig":
            let config = launcher.readConfig()
            sendResponse(id: id, payload: [
                "repoRoot": config.repoRoot,
                "autoStartServer": config.autoStartServer,
            ])

        case "setLauncherConfig":
            guard let args = payload["args"] as? [String: Any],
                  let repoRoot = args["repoRoot"] as? String else {
                sendError(id: id, message: "Invalid launcher config payload")
                return
            }
            let autoStartServer = (args["autoStartServer"] as? Bool) ?? false
            do {
                try launcher.writeConfig(LauncherConfig(repoRoot: repoRoot, autoStartServer: autoStartServer))
                sendResponse(id: id, payload: NSNull())
            } catch {
                sendError(id: id, message: "Failed to save launcher config: \(error.localizedDescription)")
            }

        case "ensureServer":
            let args = payload["args"] as? [String: Any]
            let baseUrl = (args?["baseUrl"] as? String) ?? defaultBaseUrl
            let result = launcher.ensureServer(baseUrl: baseUrl)
            sendResponse(id: id, payload: payloadResult(result))

        case "showNotification":
            let args = payload["args"] as? [String: Any]
            let title = (args?["title"] as? String) ?? "Termit"
            let body = (args?["body"] as? String) ?? ""
            requestNotification(title: title, body: body)
            sendResponse(id: id, payload: NSNull())

        case "getDocFileUrl":
            let args = payload["args"] as? [String: Any]
            let docId = (args?["docId"] as? String) ?? "help"
            let url = launcher.docPath(for: docId).absoluteURL.absoluteString
            sendResponse(id: id, payload: url)

        case "getDocPath":
            let args = payload["args"] as? [String: Any]
            let docId = (args?["docId"] as? String) ?? "help"
            sendResponse(id: id, payload: launcher.docPath(for: docId).path)

        case "openDocExternal":
            let args = payload["args"] as? [String: Any]
            let docId = (args?["docId"] as? String) ?? "help"
            let docURL = launcher.docPath(for: docId)
            let ok = NSWorkspace.shared.open(docURL)
            let result = BridgeResult(ok: ok, message: ok ? docURL.path : "Failed to open \(docURL.path)")
            sendResponse(id: id, payload: payloadResult(result))

        default:
            sendError(id: id, message: "Unknown method: \(method)")
        }
    }

    private func requestNotification(title: String, body: String) {
        switch notificationMode {
        case .system:
            UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { granted, _ in
                if !granted {
                    return
                }
                let content = UNMutableNotificationContent()
                content.title = title
                content.body = body
                let request = UNNotificationRequest(identifier: UUID().uuidString, content: content, trigger: nil)
                UNUserNotificationCenter.current().add(request)
            }
        case .fallback:
            // Running as plain executable (without app bundle) can crash with UserNotifications.
            DispatchQueue.main.async {
                NSSound.beep()
                NSLog("[Termit] %@: %@", title, body)
            }
        }
    }
}

func bridgeScript() -> String {
    return """
    (() => {
      const pending = new Map();
      function uid() {
        return `id_${Date.now()}_${Math.random().toString(16).slice(2)}`;
      }
      window.__termitShellResolve = (id, value) => {
        const slot = pending.get(id);
        if (!slot) return;
        pending.delete(id);
        slot.resolve(value);
      };
      window.__termitShellReject = (id, error) => {
        const slot = pending.get(id);
        if (!slot) return;
        pending.delete(id);
        slot.reject(new Error(String(error || "Unknown bridge error")));
      };
      function call(method, args = {}) {
        return new Promise((resolve, reject) => {
          const id = uid();
          pending.set(id, { resolve, reject });
          const payload = { id, method, args };
          if (!window.webkit?.messageHandlers?.termitBridge) {
            pending.delete(id);
            reject(new Error("Native bridge unavailable"));
            return;
          }
          window.webkit.messageHandlers.termitBridge.postMessage(payload);
        });
      }
      window.termitDesktop = {
        getLauncherConfig: () => call("getLauncherConfig"),
        setLauncherConfig: (config) => call("setLauncherConfig", config),
        ensureServer: (baseUrl) => call("ensureServer", { baseUrl }),
        showNotification: (payload) => { void call("showNotification", payload); },
        getDocFileUrl: (docId) => call("getDocFileUrl", { docId }),
        getDocPath: (docId) => call("getDocPath", { docId }),
        openDocExternal: (docId) => call("openDocExternal", { docId }),
      };
    })();
    """
}

func usageAndExit() -> Never {
    fputs("Usage: termit-shell [--renderer-root <path-to-dist>] [--docs-root <path-to-pdf-dir>] [--user-data-dir <path>]\\n", stderr)
    exit(2)
}

func bundleDefaults() -> (rendererRoot: URL, docsRoot: URL)? {
    guard let resources = Bundle.main.resourceURL,
          Bundle.main.bundleURL.pathExtension == "app" else {
        return nil
    }
    let renderer = resources.appendingPathComponent("renderer", isDirectory: true)
    let docs = resources.appendingPathComponent("docs/pdf", isDirectory: true)
    return (renderer, docs)
}

func parseArgs() -> (rendererRoot: URL, docsRoot: URL, userDataDir: URL) {
    let args = CommandLine.arguments
    var rendererRoot: URL?
    var docsRoot: URL?
    var userDataDir: URL?

    var i = 1
    while i < args.count {
        let arg = args[i]
        if arg == "--renderer-root", i + 1 < args.count {
            rendererRoot = URL(fileURLWithPath: args[i + 1])
            i += 2
            continue
        }
        if arg == "--docs-root", i + 1 < args.count {
            docsRoot = URL(fileURLWithPath: args[i + 1])
            i += 2
            continue
        }
        if arg == "--user-data-dir", i + 1 < args.count {
            userDataDir = URL(fileURLWithPath: args[i + 1])
            i += 2
            continue
        }
        usageAndExit()
    }

    let defaults = bundleDefaults()
    if rendererRoot == nil {
        rendererRoot = defaults?.rendererRoot
    }
    if docsRoot == nil {
        docsRoot = defaults?.docsRoot
    }

    guard let rendererRoot else {
        usageAndExit()
    }
    let defaultDocs = rendererRoot.deletingLastPathComponent().appendingPathComponent("docs/pdf")
    let defaultUserData = URL(fileURLWithPath: NSHomeDirectory())
        .appendingPathComponent("Library/Application Support/TermitShell", isDirectory: true)
    return (rendererRoot, docsRoot ?? defaultDocs, userDataDir ?? defaultUserData)
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var bridge: BridgeHandler?
    private var launcher: ServerLauncher?
    private let config: (rendererRoot: URL, docsRoot: URL, userDataDir: URL)

    init(config: (rendererRoot: URL, docsRoot: URL, userDataDir: URL)) {
        self.config = config
        super.init()
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let contentController = WKUserContentController()
        let bridgeUserScript = WKUserScript(source: bridgeScript(), injectionTime: .atDocumentStart, forMainFrameOnly: true)
        contentController.addUserScript(bridgeUserScript)

        let webConfig = WKWebViewConfiguration()
        webConfig.userContentController = contentController

        let launcher = ServerLauncher(userDataDir: config.userDataDir, docsRoot: config.docsRoot)
        let notificationMode: BridgeHandler.NotificationMode =
            Bundle.main.bundleURL.pathExtension == "app" ? .system : .fallback
        let bridge = BridgeHandler(launcher: launcher, notificationMode: notificationMode)
        contentController.add(bridge, name: "termitBridge")

        let webView = WKWebView(frame: .zero, configuration: webConfig)
        webView.setValue(true, forKey: "drawsBackground")
        bridge.attach(webView: webView)

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1280, height: 860),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered,
            defer: false
        )
        window.title = "Termit"
        window.minSize = NSSize(width: 960, height: 640)
        window.center()
        window.contentView = webView
        window.makeKeyAndOrderFront(nil)

        let indexUrl = config.rendererRoot.appendingPathComponent("index.html")
        webView.loadFileURL(indexUrl, allowingReadAccessTo: config.rendererRoot)

        self.window = window
        self.webView = webView
        self.bridge = bridge
        self.launcher = launcher

        let launcherConfig = launcher.readConfig()
        if launcherConfig.autoStartServer {
            _ = launcher.ensureServer(baseUrl: defaultBaseUrl)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        true
    }
}

let config = parseArgs()
let app = NSApplication.shared
app.setActivationPolicy(.regular)
let delegate = AppDelegate(config: config)
app.delegate = delegate
app.activate(ignoringOtherApps: true)
app.run()
