# Changelog

All notable changes to this project are documented here.

## [0.2.0] - 2025-01-02

- Consolidated the codebase under `mac_health_checkup` with clear module boundaries.
- Added typed diagnostics and section renderers for deterministic refresh workflows.
- Exposed logging field names and UI window title in config.
- Hardened error handling with consistent, contextual messages across utilities.
- Refined benchmarks, profiling, and CLI entrypoints for repeatable performance checks.

## [0.1.0] - 2025-01-01

- Centralized configuration with validation and size limits.
- Structured logging with redaction, correlation ids, and consistent fields.
- Deterministic benchmarks with baseline regression checks and profiling support.
- Strict typing and expanded tests across parsing, config, and workflow paths.
- UI queueing with backpressure and improved shutdown handling.
