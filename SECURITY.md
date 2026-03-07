# Security Policy

## Supported versions

Only the `main` branch is supported with security updates.

## Reporting a vulnerability

Open a GitHub security advisory for this repository with a clear reproduction path and impact details. Reports are reviewed and acknowledged as quickly as possible.

## Security controls

- Dependency scanning runs in CI with `pip-audit`.
- Secret scanning runs in CI and via pre commit using `.secrets.baseline`.
- Logs redact common secret tokens based on configuration.
- Generated TLS material, virtualenvs, simulator logs, and other local runtime artifacts stay out of Git via `.gitignore`.
- The recommended way to provide a real agent token is `MAC_HEALTH_CHECKUP_API_AUTH_TOKEN`, so GitHub can remain free of live credentials.
