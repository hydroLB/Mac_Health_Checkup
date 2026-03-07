# Repo Intelligence Snapshot

Last updated (UTC): 2026-02-15 07:14:30Z  
Source of truth: current tracked repository state (`git ls-files`) plus runtime/tooling configs in `pyproject.toml`, `Makefile`, `README.md`, `config/config.json`, and `.github/workflows/ci.yml`.

## 1) Repo tree (top 4 levels)

```text
.codex
.codex/environments
.codex/environments/environment.toml
.gitattributes
.github
.github/workflows
.github/workflows/ci.yml
.gitignore
.pre-commit-config.yaml
.secrets.baseline
CHANGELOG.md
LICENSE
Makefile
README.md
RELEASE.md
SECURITY.md
benchmarks
benchmarks/baseline.json
benchmarks/profile.py
benchmarks/run.py
config
config/config.json
docs
docs/config_reference.md
ios
ios/MacHealthCheckupMobile
ios/MacHealthCheckupMobile/MacHealthCheckupMobile.xcodeproj
ios/MacHealthCheckupMobile/MacHealthCheckupMobile.xcodeproj/project.pbxproj
ios/MacHealthCheckupMobile/MacHealthCheckupMobile.xcodeproj/xcshareddata
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/Info.plist
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/MacHealthCheckupMobileApp.swift
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/MobileAppState.swift
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/MobileRootView.swift
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/PairingView.swift
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/QRCodeScannerView.swift
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/SecureTokenStore.swift
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/SettingsView.swift
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/SnapshotCache.swift
ios/MacHealthCheckupMobile/MacHealthCheckupMobileApp/TLSFingerprintView.swift
mac_health_checkup
mac_health_checkup/__init__.py
mac_health_checkup/__main__.py
mac_health_checkup/app
mac_health_checkup/app/__init__.py
mac_health_checkup/app/actionability
mac_health_checkup/app/actionability/__init__.py
mac_health_checkup/app/actionability/advice.py
mac_health_checkup/app/backend
mac_health_checkup/app/backend/__init__.py
mac_health_checkup/app/backend/http
mac_health_checkup/app/backend/one_click.py
mac_health_checkup/app/backend/security
mac_health_checkup/app/backend/server.py
mac_health_checkup/app/backend/snapshot.py
mac_health_checkup/app/backend/tls.py
mac_health_checkup/app/cli.py
mac_health_checkup/app/entrypoint.py
mac_health_checkup/app/gui
mac_health_checkup/app/gui/__init__.py
mac_health_checkup/app/gui/app.py
mac_health_checkup/app/gui/dashboard
mac_health_checkup/app/gui/sections
mac_health_checkup/app/gui/widgets
mac_health_checkup/app/help_text.py
mac_health_checkup/app/reports
mac_health_checkup/app/reports/__init__.py
mac_health_checkup/app/reports/snapshot_diff.py
mac_health_checkup/app/reports/snapshot_io.py
mac_health_checkup/app/reports/snapshot_render.py
mac_health_checkup/core
mac_health_checkup/core/__init__.py
mac_health_checkup/core/config
mac_health_checkup/core/config/__init__.py
mac_health_checkup/core/config/io.py
mac_health_checkup/core/config/lookup.py
mac_health_checkup/core/config/models
mac_health_checkup/core/config/parsing
mac_health_checkup/core/config/public.py
mac_health_checkup/core/config/validation
mac_health_checkup/core/constants
mac_health_checkup/core/constants/__init__.py
mac_health_checkup/core/types.py
mac_health_checkup/core/utils
mac_health_checkup/core/utils/__init__.py
mac_health_checkup/core/utils/data.py
mac_health_checkup/core/utils/errors.py
mac_health_checkup/core/utils/health.py
mac_health_checkup/core/utils/loggers.py
mac_health_checkup/core/utils/qr.py
mac_health_checkup/core/utils/regex_utils.py
mac_health_checkup/core/utils/shell.py
mac_health_checkup/core/utils/text.py
mac_health_checkup/core/utils/usb_tree.py
mac_health_checkup/diagnostics
mac_health_checkup/diagnostics/__init__.py
mac_health_checkup/diagnostics/backups.py
mac_health_checkup/diagnostics/base.py
mac_health_checkup/diagnostics/battery.py
mac_health_checkup/diagnostics/devices.py
mac_health_checkup/diagnostics/display.py
mac_health_checkup/diagnostics/display_transport.py
mac_health_checkup/diagnostics/fan.py
mac_health_checkup/diagnostics/general.py
mac_health_checkup/diagnostics/network.py
mac_health_checkup/diagnostics/power.py
mac_health_checkup/diagnostics/processes.py
mac_health_checkup/diagnostics/security.py
mac_health_checkup/diagnostics/ssd.py
mac_health_checkup/diagnostics/startup.py
mac_health_checkup/diagnostics/system.py
mac_health_checkup/diagnostics/thermals
mac_health_checkup/diagnostics/thermals/__init__.py
mac_health_checkup/diagnostics/thermals/collector.py
mac_health_checkup/diagnostics/thermals/hid_event_system.py
mac_health_checkup/diagnostics/thermals/iohid
mac_health_checkup/diagnostics/thermals/models.py
mac_health_checkup/diagnostics/thermals/processing
mac_health_checkup/diagnostics/updates.py
pyproject.toml
pytest.ini
requirements-dev.txt
requirements.txt
run.py
run_mac_health_checkup.py
run_mac_health_checkup_ui.py
start
swift-ui
swift-ui/.build
swift-ui/.build/.lock
swift-ui/Package.swift
swift-ui/Sources
swift-ui/Sources/MacHealthCheckupApp
swift-ui/Sources/MacHealthCheckupApp/AppBootstrap.swift
swift-ui/Sources/MacHealthCheckupApp/AppLaunchArgs.swift
swift-ui/Sources/MacHealthCheckupApp/MacHealthCheckupApp.swift
swift-ui/Sources/MacHealthCheckupCore
swift-ui/Sources/MacHealthCheckupCore/Backend
swift-ui/Sources/MacHealthCheckupCore/Config
swift-ui/Sources/MacHealthCheckupCore/Errors
swift-ui/Sources/MacHealthCheckupCore/Security
swift-ui/Sources/MacHealthCheckupCore/Theme
swift-ui/Sources/MacHealthCheckupUI
swift-ui/Sources/MacHealthCheckupUI/Health
swift-ui/Sources/MacHealthCheckupUI/Help
swift-ui/Sources/MacHealthCheckupUI/Sections
swift-ui/Sources/MacHealthCheckupUI/Settings
swift-ui/Sources/MacHealthCheckupUI/Theme
swift-ui/Sources/MacHealthCheckupUI/ViewModel
swift-ui/Sources/MacHealthCheckupUI/Views
swift-ui/Tests
swift-ui/Tests/MacHealthCheckupAppTests
swift-ui/Tests/MacHealthCheckupAppTests/AppLaunchArgsTests.swift
swift-ui/Tests/MacHealthCheckupCoreTests
swift-ui/Tests/MacHealthCheckupCoreTests/ConfigDecodeTests.swift
swift-ui/Tests/MacHealthCheckupCoreTests/PythonInterpreterResolverTests.swift
swift-ui/Tests/MacHealthCheckupCoreTests/RemoteBackendClientTests.swift
swift-ui/Tests/MacHealthCheckupUITests
swift-ui/Tests/MacHealthCheckupUITests/SectionVisibilityStoreTests.swift
tests
tests/test_actionability.py
tests/test_api_security.py
tests/test_backend_http_handler_factory_unit.py
tests/test_backend_server_unit.py
tests/test_config.py
tests/test_config_thread_safety.py
tests/test_devices_section.py
tests/test_diagnostics_parsing_extended.py
tests/test_display_parsing.py
tests/test_display_section_order.py
tests/test_display_transport_parsing.py
tests/test_entrypoint_cli_serve.py
tests/test_entrypoint_export_diff_unit.py
tests/test_entrypoint_internal_coverage.py
tests/test_entrypoint_logging.py
tests/test_entrypoint_modes_unit.py
tests/test_gui_accessibility.py
tests/test_gui_app_helpers.py
tests/test_gui_integration_smoke.py
tests/test_gui_visual_regression_tool.py
tests/test_help_text.py
tests/test_http_disconnect_handling.py
tests/test_input_hid_dedupe.py
tests/test_network_parsing_unit.py
tests/test_one_click_runner.py
tests/test_one_click_runner_help.py
tests/test_one_click_unit.py
tests/test_ports_section.py
tests/test_power_parsing.py
tests/test_regex_utils.py
tests/test_reports_export.py
tests/test_scroll_container_unit.py
tests/test_shell_integration.py
tests/test_shell_safe_run_unit.py
tests/test_shutdown_manager.py
tests/test_smoke_display_pipeline.py
tests/test_smoke_workflow.py
tests/test_snapshot_advice.py
tests/test_snapshot_backend.py
tests/test_snapshot_server.py
tests/test_startup_items_parsing.py
tests/test_swiftpm_autoclean.py
tests/test_thermals_hid_collector.py
tests/test_thermals_processing_unit.py
tests/test_tooltip_manager_unit.py
tests/test_usb_tree.py
tools
tools/check_docstring_headings.py
tools/generate_config_reference.py
tools/gui_visual_regression.py
```

## 2) Stack and runtime identification

### Languages and frameworks

- Python: core diagnostics engine, CLI, Tk GUI, and local HTTP API.
- Swift: SwiftUI native macOS UI (`swift-ui`) and iOS client (`ios/MacHealthCheckupMobile`).
- Frameworks and platform APIs:
- Python stdlib heavy usage (`argparse`, `http.server`, `subprocess`, `ssl`, `threading`, `json`, `tkinter`).
- SwiftUI + Foundation for native clients.

### Package managers and toolchain

- Python packaging: `pip` + hash-locked `requirements.txt` and `requirements-dev.txt`.
- Python lock generation: `pip-tools` (`make deps-lock`) with pinned `pip` and `pip-tools` versions in `Makefile`.
- Python runtime pin: `.python-version` = `3.11.14`.
- Project declared runtime support: `pyproject.toml` has `requires-python = ">=3.10"`.
- Swift package manager: SwiftPM (`swift-ui/Package.swift`, `swift-tools-version: 6.0`).
- iOS build toolchain: `xcodebuild` using `ios/MacHealthCheckupMobile/MacHealthCheckupMobile.xcodeproj`.

### Primary entrypoints

- Python package/script entrypoint: `mac-health-checkup = mac_health_checkup.app.entrypoint:main`.
- One-file launcher: `run.py`.
- One-click Mac agent launcher: `run_mac_health_checkup.py`.
- One-click native SwiftUI launcher: `run_mac_health_checkup_ui.py`.
- Shell bootstrap one-command run: `./start`.
- Unified local commands: `make dev`, `make check`, `make setup`.

### Deploy and run targets

- Local macOS GUI app (Tkinter): default `python -m mac_health_checkup` flow.
- Local macOS CLI mode: `--cli`.
- Local Mac agent HTTP API (`--serve`): `/v1/health`, `/v1/snapshot`, `/v1/section` with token auth for snapshot endpoints.
- Native macOS SwiftUI executable (`swift-ui` product `mac-health-checkup-ui`) using snapshot backend.
- iOS app client (`ios/MacHealthCheckupMobile`) that pairs to the Mac agent API.
- CI target: GitHub Actions macOS runner running `make setup` then `make check`.

### Data stores and persistence

- Main config registry: `config/config.json`.
- Generated docs artifact: `docs/config_reference.md`.
- Lockfiles: `requirements.txt`, `requirements-dev.txt`.
- Runtime local artifacts under `.local/` (reports, TLS cert/key, Swift build cache, visual regression artifacts).
- Benchmark baseline file: `benchmarks/baseline.json`.
- No persistent database configured in-repo.

### External dependencies and boundaries

- Python runtime dependencies: currently stdlib-only at runtime (`requirements.in` intentionally empty).
- Dev/security/quality tooling dependencies: `ruff`, `mypy`, `pytest`, `pytest-cov`, `bandit`, `pip-audit`, `detect-secrets`, `pre-commit`, `pip-tools`.
- macOS system command dependencies used via subprocess wrappers (non-exhaustive):
- `system_profiler`, `ioreg`, `pmset`, `softwareupdate`, `ifconfig`, `netstat`, `spctl`, `csrutil`, `fdesetup`, `diskutil`, `smartctl`, `powermetrics`, `plutil`, `airport`.
- Optional QR generator tool: `qrencode`.

## 3) Architecture map (concise)

### Layers and dependency direction

1. `mac_health_checkup/core/*`
- Shared foundation: typed models, config parsing/validation, constants, shell/log/error utilities.
- No UI-specific responsibilities should leak here.

2. `mac_health_checkup/diagnostics/*`
- IO-heavy collectors and parsers for macOS telemetry.
- Depends on `core/*` for config, types, shell wrappers, and health mapping.

3. `mac_health_checkup/app/*`
- Orchestration and interfaces:
- `app/entrypoint.py` mode router and compatibility facade for GUI, CLI, snapshot JSON, API server, and export/diff flows.
- `app/entrypoint_support/*` internal helpers for argument parsing, mode exports, section execution, output formatting, and URL validation.
- `app/gui/*` Tk UI composition and render sections.
- `app/backend/*` snapshot builder, HTTP handler/server, auth/rate-limit/TLS.
- `app/reports/*` export and diff rendering.

4. Native clients
- `swift-ui/*`: Swift core/UI packages and executable.
- `ios/*`: iOS app consuming Mac agent snapshot endpoints.

### Critical flows

- Flow A: Local run (`make dev` or `./start`)  
`start -> run.py -> app.entrypoint.main -> (Tk GUI or CLI fallback) -> section handlers -> diagnostics -> shell commands`

- Flow B: Headless snapshot JSON  
`app.entrypoint --snapshot-json -> SnapshotBuilder -> section handlers -> diagnostics -> JSON payload`

- Flow C: Mac agent for iOS/macOS native UIs  
`app.entrypoint --serve -> SnapshotApiServer -> HTTP handler factory -> auth/throttle -> SnapshotBuilder`

- Flow D: Native UI client rendering  
`swift-ui` / `ios` -> call `/v1/snapshot` -> decode snapshot schema -> render sections/theme locally

### Domain boundaries and where business logic lives

- Business rules and health scoring logic mostly live in:
- `mac_health_checkup/diagnostics/*`
- `mac_health_checkup/core/utils/health.py`
- `mac_health_checkup/core/config/parsing/*` and `config/config.json` thresholds
- Interface concerns live in:
- Python UI/CLI/API under `mac_health_checkup/app/*`
- Native presentation under `swift-ui/*` and `ios/*`

## 4) Risk register (Top 15)

| Rank | Priority | Area | Risk | Impact | Fix path |
|---|---|---|---|---|---|
| 1 | P0 | Security | API can be intentionally switched to insecure LAN HTTP (`allow_insecure_http_lan=true`). | Token exposure and snapshot data leakage on shared networks. | Keep secure defaults, add CI policy test that disallows insecure LAN in committed config, and require explicit runtime override for local dev only. |
| 2 | P0 | Security | API token is configured in plaintext and pairing payload is printed to stdout. | Token can leak via shell history, screenshots, or logs. | Move token sourcing to env/secret store path, mask token in all human-readable output, rotate token on first-run workflow. |
| 3 | P0 | Availability | Snapshot generation is request-coupled to live collectors and subprocess calls. | Concurrent API requests can saturate CPU/IO and increase timeout/error rate. | Add bounded snapshot cache (short TTL), per-endpoint concurrency caps, and request budget metrics with p95 alerts. |
| 4 | P0 | Correctness | Collector parsing is tied to fragile CLI output formats from macOS utilities. | OS updates can silently degrade diagnostics quality. | Add fixture corpus by macOS version and parser contract tests for each collector family. |
| 5 | P0 | Maintainability | Runtime version contract is split (`requires-python >=3.10` vs pinned `.python-version 3.11.14`). | Drift can hide runtime-specific bugs and confuse contributors. | Align to a single policy (for example exact 3.11.14) and enforce in pyproject + CI + make preflight. |
| 6 | P1 | Architecture | Backend snapshot/API path depends on GUI section handler registry (`SECTION_HANDLERS` in GUI module). | Layer coupling makes backend changes risky and blocks clean domain/app/infra separation. | Extract neutral section orchestrator into app/domain module used by both GUI and backend. |
| 7 | P1 | Reliability | `/v1/health` is liveness-only and does not express readiness of critical dependencies. | Clients can see “healthy” while snapshot path is degraded. | Add `/v1/ready` with dependency checks (config validity, snapshot warmup, TLS material) and document semantics. |
| 8 | P1 | Reproducibility | Swift and Xcode workflows are deterministic only on correctly provisioned macOS hosts. | New contributors can fail setup despite passing Python prerequisites. | Add machine-readable preflight report command and explicit remediation map in docs/runbooks. |
| 9 | P1 | Performance | Benchmarks exist but CI does not persist trend history for regression analysis. | Performance drifts can remain unnoticed until user-visible lag appears. | Persist benchmark artifacts per CI run and compare against rolling baseline with defined budget thresholds. |
| 10 | P1 | Security | Security scans run in CI, but findings are not exported as SARIF for centralized code scanning UX. | Lower visibility and slower triage for recurring vulnerabilities. | Add SARIF upload for SAST/dependency results and make severity policies explicit. |
| 11 | P1 | Operability | Structured logging exists, but section-level latency/error metrics are limited. | Harder incident diagnosis and capacity planning under load. | Add minimal metrics counters/timers per section and per endpoint; include correlation ID in all boundary logs. |
| 12 | P1 | Compatibility | Snapshot JSON schema is consumed by Swift/iOS clients with limited explicit versioned contract tests. | Backward compatibility regressions can break native clients. | Add cross-language contract test suite pinned to schema fixtures and schema version migration policy. |
| 13 | P2 | Repo hygiene | Build/cache artifacts and environment-specific metadata risk entering tracked history over time. | Review noise and accidental non-source diffs. | Tighten `.gitignore`, add CI check for forbidden tracked artifact patterns, and keep generated artifacts out of source tree. |
| 14 | P2 | Documentation | Architecture and design rationale are partially in README but not formalized as ADRs. | Decision context is lost; onboarding and review quality decline as repo grows. | Add `docs/architecture.md` + ADR set for major boundaries and tradeoffs. |
| 15 | P2 | DX | macOS-only runtime constraints reduce contributor pool and test surface on non-macOS hosts. | Slower iteration for contributors without Apple hardware. | Provide limited Linux CI subset for pure parsing/unit layers and document scope of platform-specific tests. |

## 5) Three-phase roadmap with measurable Definition of Done

### Phase 1: Baseline quality gates and safety

Scope:
- Keep `make check` as the single verification entrypoint across docs and CI.
- Keep `make dev` and `./start` as one-command local run paths.
- Preserve deterministic dependency locks and pinned Python runtime checks.
- Maintain baseline collaboration standards docs and templates.
- Maintain deterministic security/config boundary tests and coverage floor.

Definition of Done:
- Fresh clone on supported macOS host: `make setup && make check` passes with no manual edits.
- CI primary quality job runs `make check` only (no divergent ad hoc commands).
- `make deps-check` is stable and yields no lockfile diff on clean repo.
- Coverage gate remains enforced at >= 70 and passes.
- README links all collaboration/quality documents (`CONTRIBUTING`, templates, `CODEOWNERS`, security docs).

### Phase 2: Architecture hardening and operability

Scope:
- Introduce explicit layering contract (`domain -> app -> infra` equivalent) and remove GUI/backend coupling.
- Standardize API error model and boundary mapping.
- Add readiness semantics and richer operational telemetry.
- Expand security posture with threat-model notes for API pairing surface.

Definition of Done:
- Automated dependency-direction checks pass in CI and block layer violations.
- Snapshot orchestration lives outside GUI module; backend and GUI consume same neutral service API.
- `/v1/ready` implemented and tested against failure scenarios.
- Request/section latency metrics and structured error codes are emitted and covered by tests.
- `docs/runbooks/` contains incident and rollback playbooks for agent API failures.

### Phase 3: Scalability, polish, and long-term maintainability

Scope:
- Formalize release automation and public compatibility policy.
- Add sustained performance and load validation for snapshot pipeline.
- Complete architecture narrative with ADRs and design principles.
- Remove residual repository hygiene issues and enforce clean artifact boundaries.

Definition of Done:
- Release workflow produces tagged releases with generated notes/changelog updates.
- Load/perf suite for API endpoints exists with explicit pass/fail budgets.
- Contract tests protect snapshot schema compatibility across Python and Swift/iOS clients.
- `docs/architecture.md` and initial ADR series are merged and linked from README.
- No forbidden generated/build artifacts are tracked; CI guard enforces this.

## 6) Phase 0 completion status

- Repo tree (4 levels): complete.
- Stack/runtime/package manager identification: complete.
- Entrypoints/deploy targets/data stores/external dependency inventory: complete.
- Architecture map with boundaries and critical flows: complete.
- Top-15 prioritized risk register with impact and fix approach: complete.
- 3-phase roadmap with measurable DoD: complete.
