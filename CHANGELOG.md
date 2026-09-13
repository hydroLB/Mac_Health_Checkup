# Changelog

All notable changes to this project are documented here.

## [Unreleased]

- A public browser-only Demo Mode now reproduces the complete diagnostic interface with fictional data, interactive
  sections, metric history, specialized tables, settings, and refresh behavior while exposing no device, export,
  account, or telemetry path.
- Network capacity testing is now explicit opt-in, disclosed as outbound traffic, and rate-limited independently
  from the live network refresh path.
- One-click agent startup now fails closed to loopback-only HTTP when TLS material cannot be generated.
- One-click generated-token storage now uses atomic writes plus owner-only directory and file permissions.
- Remote clients now reject cleartext non-loopback connections and require the paired certificate pin for LAN HTTPS.
- Snapshot/report exports and native snapshot caches now enforce owner-only file permissions.
- API server startup now closes bound sockets transactionally when TLS or worker startup fails.
- Tk diagnostics refresh now runs outside the UI event loop so the window remains responsive during slow collectors.
- `--redact-sensitive` now creates safe-share snapshot, report, and diff output without mutating source snapshots.
- Unavailable and unknown health signals now produce warning advice instead of an incorrect healthy result.
- The deterministic layout renderer now uses clipped row writes and byte-buffer diffs, cutting its end-to-end test
  runtime from minutes to seconds while preserving pixel-level checks.
- Parser benchmarks now exercise real multiline fixtures, interleave longer best-of process-CPU samples to exclude
  shared-runner scheduling noise, and emit measured throughput for review.
- iOS snapshot caching models now encode and decode symmetrically, and the mobile backend satisfies the complete
  snapshot protocol contract.
- Dependency-lock verification now compiles into a temporary directory and never rewrites a contributor's working
  lockfiles merely to check them.
- The managed staged repo-hygiene hook now distinguishes staged policy checks from repository-wide recovery checks.
- Repo hygiene now blocks untracked Finder-style shadow copies such as `README 2.md` before local quality gates are trusted.
- `make check` is now split into `make check-python` and `make check-platform` so Python-only iteration does not depend on ignored visual-regression baselines.
- `./start` and repository-managed hooks now handle stale or moved `.venv` interpreters more safely.
- Configuration reference generation was refreshed and now emits repo-relative source paths.
- Development dependency pins were refreshed to resolve current `pip-audit` findings while preserving hash-locked installs.
- CI now uses a currently available Python 3.11 runtime, immutable action revisions, and GitHub-hosted pull-request runners.
- Secret scanning now compares against the committed baseline without rewriting it during local checks.
- Python wheel and source-distribution builds now include the validated default configuration and are smoke-tested
  from an isolated environment outside the source checkout.
- Coverage runs now propagate the repository's branch settings into subprocesses, preventing mixed-mode data from
  invalidating an otherwise successful test run.

## Development milestone 0.2.0 (untagged) - 2025-01-02

- Consolidated the codebase under `mac_health_checkup` with clear module boundaries.
- Added typed diagnostics and section renderers for deterministic refresh workflows.
- Exposed logging field names and UI window title in config.
- Hardened error handling with consistent, contextual messages across utilities.
- Refined benchmarks, profiling, and CLI entrypoints for repeatable performance checks.

## Development milestone 0.1.0 (untagged) - 2025-01-01

- Centralized configuration with validation and size limits.
- Structured logging with redaction, correlation ids, and consistent fields.
- Deterministic benchmarks with baseline regression checks and profiling support.
- Strict typing and expanded tests across parsing, config, and workflow paths.
- UI queueing with backpressure and improved shutdown handling.
