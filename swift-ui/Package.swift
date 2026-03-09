// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "MacHealthCheckupUI",
    platforms: [
        .macOS(.v13),
        .iOS(.v16)
    ],
    products: [
        .library(name: "MacHealthCheckupCore", targets: ["MacHealthCheckupCore"]),
        .library(name: "MacHealthCheckupUI", targets: ["MacHealthCheckupUI"]),
        .executable(name: "mac-health-checkup-ui", targets: ["MacHealthCheckupApp"])
    ],
    targets: [
        .target(
            name: "MacHealthCheckupCore"
        ),
        .target(
            name: "MacHealthCheckupUI",
            dependencies: ["MacHealthCheckupCore"]
        ),
        .executableTarget(
            name: "MacHealthCheckupApp",
            dependencies: ["MacHealthCheckupUI"]
        ),
        .testTarget(
            name: "MacHealthCheckupCoreTests",
            dependencies: ["MacHealthCheckupCore"]
        ),
        .testTarget(
            name: "MacHealthCheckupAppTests",
            dependencies: ["MacHealthCheckupApp"]
        ),
        .testTarget(
            name: "MacHealthCheckupUITests",
            dependencies: ["MacHealthCheckupUI"]
        ),
    ]
)
