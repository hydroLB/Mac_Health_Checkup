# Repository Layout (Canonical Mapping)

This repository uses a canonical top-level model with a documented partial migration path.
The goal is to keep structure clear without breaking existing entrypoints.

## Canonical domains

| Canonical domain | Current paths (equivalent) | Notes |
|---|---|---|
| `apps/` | `mac_health_checkup/app/`, `swift-ui/Sources/MacHealthCheckupApp/`, `ios/MacHealthCheckupMobile/` | Runtime application surfaces (Python app, macOS SwiftUI app, iOS app). |
| `libs/` | `mac_health_checkup/core/`, `mac_health_checkup/diagnostics/`, `swift-ui/Sources/MacHealthCheckupCore/`, `swift-ui/Sources/MacHealthCheckupUI/` | Shared domain and platform libraries. |
| `docs/` | `docs/`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `RELEASE.md`, `repo-intelligence.md` | Product and engineering documentation. |
| `tests/` | `tests/`, `swift-ui/Tests/` | Python and Swift test suites. |
| `scripts/` | `start`, `run.py`, `run_mac_health_checkup.py`, `run_mac_health_checkup_ui.py`, `tools/`, `benchmarks/` | Operational, tooling, benchmark, and one-click launch scripts. |
| `infra/` | `.github/workflows/`, `.github/dependabot.yml`, `Makefile`, `.pre-commit-config.yaml`, `pytest.ini`, `requirements*.in`, `requirements*.txt` | CI/CD, dependency, and quality-gate infrastructure. |

## Script registry (no orphan scripts)

Every script in this table is either invoked by `make` targets or documented as a supported manual entrypoint in `README.md`.

| Script path | Invoked by | Purpose |
|---|---|---|
| `start` | `make dev`; documented direct run | One-command local bootstrap + app launch. |
| `run.py` | documented manual entrypoint | IDE-friendly top-level runner. |
| `run_mac_health_checkup.py` | documented manual entrypoint | One-click headless Mac agent runner. |
| `run_mac_health_checkup_ui.py` | documented manual entrypoint | One-click native macOS SwiftUI launcher. |
| `benchmarks/run.py` | `make bench` | Deterministic benchmark execution + baseline checks. |
| `benchmarks/profile.py` | `make profile` | Performance profiling run for hot paths. |
| `tools/check_docstring_headings.py` | `make docstrings` (via `make check`) | Enforce project docstring heading standard. |
| `tools/generate_config_reference.py` | `make config-ref`, `make config-ref-check` (via `make check`) | Generate and verify config reference docs. |
| `tools/gui_visual_regression.py` | `make visual-*` (via `make check`) | Capture/diff deterministic GUI visual snapshots. |

## Normalization policy

1. New top-level additions must map to one canonical domain above.
2. New scripts must be added to this registry and wired to `make` or README usage docs before merge.
3. Path moves should be incremental and compatibility-preserving (no big-bang rewrites).
