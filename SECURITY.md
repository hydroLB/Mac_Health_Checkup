# Security Policy

## Supported versions

Only the `main` branch is supported with security updates.

## Reporting a vulnerability

Open a GitHub security advisory for this repository with a clear reproduction path and impact details. Treat `main` as the only supported branch. If a private advisory cannot be opened, do not disclose the issue publicly until a maintainer response path is available.

## Security controls

- Dependency scanning runs in CI with `pip-audit`.
- Secret scanning runs in CI and via the repository-managed pre-push hook using `.secrets.baseline`.
- Logs redact common secret tokens based on configuration.
- Generated TLS material, virtualenvs, simulator logs, and other local runtime artifacts stay out of Git via `.gitignore`.
- The recommended way to provide a real agent token is `MAC_HEALTH_CHECKUP_API_AUTH_TOKEN`, so GitHub can remain free of live credentials.
- The one-click runner stores its generated token under an ignored owner-only directory (`0700`) and writes the
  derived configuration atomically with mode `0600`.
- Remote clients permit HTTP only for loopback development and require HTTPS plus the paired certificate pin for
  non-loopback agents.
- Snapshot/report exports and the native last-known-good snapshot cache are written with owner-only permissions.
- Repository-managed hooks are installed with `make setup` or `./start` and use `core.hooksPath=.githooks`.
- The managed pre-commit hook runs staged repo hygiene only.
- The managed pre-push hook runs `make verify-push`.
- `.pre-commit-config.yaml` is available for optional manual `pre-commit run --all-files`, but it is not the default managed hook path.

## Operational privacy boundaries

- The application has no analytics or telemetry pipeline. Routine collectors stay on the Mac and the agent API is disabled by default.
- `network.capacity_test_enabled` is `false` by default. Enabling it runs macOS `networkQuality`, which sends test traffic to external measurement endpoints; results are cached for at least the configured interval.
- The one-click agent exposes a LAN listener only when it can generate TLS material. TLS failure falls back to loopback-only HTTP rather than insecure LAN access.
- Snapshots and reports can contain a hardware serial, local IP address, Wi-Fi SSID, process IDs, command paths, and raw collector output. Use `--redact-sensitive` before sharing and still review the result for context-specific identifiers.
