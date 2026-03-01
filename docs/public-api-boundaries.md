# Public API Boundaries

This document defines the supported Python import surfaces and the internal module split.
It exists to reduce accidental coupling and keep refactors safe.

## Approved public surfaces

Use these package-level entrypoints for cross-package imports:

- `mac_health_checkup.core.config`
- `mac_health_checkup.core.utils`
- `mac_health_checkup.app.backend`
- `mac_health_checkup.app.backend.security`
- `mac_health_checkup.app.actionability`
- `mac_health_checkup.app.reports`
- `mac_health_checkup.diagnostics`

## Internal/private modules

The following modules are implementation details and are not approved for cross-package imports:

- `mac_health_checkup.app.backend.snapshot`
- `mac_health_checkup.app.backend.server`
- `mac_health_checkup.app.backend.one_click`
- `mac_health_checkup.app.backend.tls`
- `mac_health_checkup.app.backend.http.*`
- `mac_health_checkup.app.backend.security.auth`
- `mac_health_checkup.app.backend.security.throttling`
- `mac_health_checkup.app.backend.security.validation`
- `mac_health_checkup.core.config.models.*`
- `mac_health_checkup.core.config.parsing.*`
- `mac_health_checkup.core.config.validation.*`
- `mac_health_checkup.core.config.public`
- `mac_health_checkup.core.config.io`
- `mac_health_checkup.core.config.lookup`
- `mac_health_checkup.core.utils.errors`
- `mac_health_checkup.core.utils.data`
- `mac_health_checkup.core.utils.health`
- `mac_health_checkup.core.utils.loggers`
- `mac_health_checkup.core.utils.qr`
- `mac_health_checkup.core.utils.regex_utils`
- `mac_health_checkup.core.utils.shell`
- `mac_health_checkup.core.utils.text`
- `mac_health_checkup.core.utils.usb_tree`

Private identifiers (prefixed with `_`) are internal even when defined inside approved public packages.

## Allowed exceptions

- Modules may import internals inside their own package boundary.
  - Example: code inside `mac_health_checkup/app/backend/` may import `mac_health_checkup.app.backend.snapshot`.
- White-box tests may import internals when explicitly testing boundary behavior.
  - Example: tests for `_build_config_with_api_overrides` and `_is_client_disconnect`.

## Boundary rules for contributors

1. Prefer package `__init__.py` exports over direct module imports.
2. If a needed symbol is missing from a public surface, add an explicit export first, then import through that surface.
3. Do not export underscore-prefixed helpers as public API.
4. Keep this document in sync when adding or removing public exports.

## Enforcement

- Rule config: `tools/layer_rules.json`
- Static checker: `tools/enforce_layer_dependencies.py`
- Local command: `make layers` (also runs inside `make check`)
- CI enforcement: `.github/workflows/ci.yml` runs `make check`, so layer violations fail CI.
