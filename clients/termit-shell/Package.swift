// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "TermitShell",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "termit-shell", targets: ["TermitShell"])
    ],
    targets: [
        .executableTarget(
            name: "TermitShell",
            path: "Sources/TermitShell"
        )
    ]
)
