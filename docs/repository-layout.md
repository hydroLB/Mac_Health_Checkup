# Repository Layout

This document describes the repository as it exists today. It is not a conceptual target layout.

## Top-level structure

| Path | Responsibility |
|---|---|
| `mac_health_checkup/app/` | Python entrypoints, CLI, Tk dashboard, backend snapshot server, and report/export flows. |
| `mac_health_checkup/core/` | Typed config, shared models, logging, shell execution, and other cross-cutting utilities. |
| `mac_health_checkup/diagnostics/` | Read-only system collectors and parsing logic for macOS signals. |
| `swift-ui/` | Native macOS SwiftUI app and Swift package tests. |
| `ios/` | iOS pairing client and Xcode project. |
| `showcase/` | Browser-only Demo Mode, fictional snapshot content, and free static deployment configuration. |
| `tests/` | Python tests for config, backend/API, GUI helpers, parsing, runners, and repo tooling. |
| `tools/` | Repo enforcement and generation scripts used by `make` targets. |
| `benchmarks/` | Python benchmark and profiling entrypoints. |
| `config/` | Checked-in runtime defaults. |
| `mac_health_checkup/resources/` | Package data, including the synchronized default used outside a source checkout. |
| `docs/` | Supporting engineering docs that explain enforced boundaries and generated references. |
| `.mac-health-checkup-source` | Project-specific marker that permits checkout-local config precedence without trusting an unrelated installed sibling path. |

## Supported entrypoints

| Entry point | Purpose |
|---|---|
| `./start` | One-command bootstrap that creates or repairs `.venv`, syncs dependencies, installs hooks, and launches the SwiftUI app. |
| `make dev` / `.venv/bin/python run.py` | Launch the native SwiftUI app from a configured checkout. |
| `make run` | Launch the in-process Tk dashboard. |
| `.venv/bin/python -m mac_health_checkup --cli --advice` | Run the terminal health summary and recommendations. |
| `.venv/bin/python run.py --agent` | Start the one-click headless agent; LAN pairing is available only when TLS setup succeeds. |
| `make check-python` | Fastest high-value Python gate for local iteration. |
| `make check` | Full integration gate used by CI. |
| `make showcase-check` | Install the locked Demo Mode dependencies, lint the web source, and create a production build. |

## Maintenance notes

1. Keep this document descriptive. If the repo structure changes, update the actual paths here instead of describing an aspirational future layout.
2. Avoid adding undocumented top-level scripts. Wire them to `make`, README usage, or both.
3. Repo hygiene treats untracked Finder-style shadow copies such as `README 2.md` as blocking clutter because they confuse tests and local tooling.
4. Keep `.mac-health-checkup-source` stable and out of distributions; config resolution uses its exact content to
   distinguish this checkout from an installed package.
