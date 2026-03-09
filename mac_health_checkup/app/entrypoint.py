from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from mac_health_checkup.app.backend import Snapshot, SnapshotApiServer, SnapshotBuilder
from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.app.entrypoint_support.args import parse_args as _parse_args_impl
from mac_health_checkup.app.entrypoint_support.export_mode import (
    resolve_export_path as _resolve_export_path_impl,
)
from mac_health_checkup.app.entrypoint_support.export_mode import (
    run_diff_mode as _run_diff_mode_impl,
)
from mac_health_checkup.app.entrypoint_support.export_mode import (
    run_export_mode as _run_export_mode_impl,
)
from mac_health_checkup.app.entrypoint_support.export_mode import (
    write_text_file as _write_text_file_impl,
)
from mac_health_checkup.app.entrypoint_support.failure_policy import (
    should_fail_on_host as _should_fail_on_host_impl,
)
from mac_health_checkup.app.entrypoint_support.failure_policy import (
    should_fail_on_snapshot as _should_fail_on_snapshot_impl,
)
from mac_health_checkup.app.entrypoint_support.output import (
    print_cli_advice as _print_cli_advice_impl,
)
from mac_health_checkup.app.entrypoint_support.output import (
    print_console_output as _print_console_output_impl,
)
from mac_health_checkup.app.entrypoint_support.output import (
    print_pairing_qr_best_effort as _print_pairing_qr_best_effort_impl,
)
from mac_health_checkup.app.entrypoint_support.section_runner import (
    run_sections_best_effort as _run_sections_best_effort_impl,
)
from mac_health_checkup.app.entrypoint_support.urls import (
    resolve_public_base_url as _resolve_public_base_url_impl,
)
from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.app.gui.dashboard.sections import SECTION_HANDLERS, run_section
from mac_health_checkup.core.config import (
    Config,
    build_startup_config_validation_report,
    get_config,
)
from mac_health_checkup.core.utils import (
    LogContext,
    LoggingFields,
    StructuredLogger,
    configure_logging_once,
    format_error,
    new_correlation_id,
)
from mac_health_checkup.core.utils.error_boundary import ErrorBoundary, map_boundary_exception

MODULE_PATH = "mac_health_checkup/app/entrypoint.py"


@dataclass(frozen=True)
class _RuntimeState:
    """
    Summary
    Hold initialized runtime dependencies for the selected entrypoint mode.

    Inputs
    cfg: Loaded application config object.
    logger: Structured logger for lifecycle messages.
    context: Shared log context for the entrypoint run.
    shutdown: Installed shutdown manager.

    Outputs
    Immutable runtime state record.

    Side effects
    None after construction.

    Error handling
    Initialization validation occurs in `_initialize_runtime`.

    Ties to other methods
    Used by `main`, `_dispatch_mode`, and the mode-specific helpers.

    Why this exists
    Grouping runtime dependencies removes repeated setup plumbing from each mode branch.
    """

    cfg: Config
    logger: StructuredLogger
    context: LogContext
    shutdown: ShutdownManager


def main() -> int:
    """
    Summary
    Run the application entrypoint for GUI, CLI, or snapshot workflows.

    Inputs
    None. Reads process arguments and config.

    Outputs
    Process exit code.

    Side effects
    Configures logging, runs diagnostics, and may start a GUI or emit JSON to stdout.

    Error handling
    Returns exit code 1 and prints a bounded error message to stderr when the entrypoint fails unexpectedly.

    Ties to other methods
    Uses `SECTION_HANDLERS` and `run_section` for section execution. Uses snapshot and export helpers for
    machine-readable modes.

    Why this exists
    Provides a single deterministic entrypoint with clear mode selection and safe fallbacks.
    """
    args: argparse.Namespace | None = None
    try:
        args = _parse_args()
        runtime = _initialize_runtime()
        return _dispatch_mode(args, runtime)
    except Exception as exc:
        boundary = _boundary_from_args(args)
        mapped = map_boundary_exception(exc, boundary=boundary, default_message="Entrypoint failed")
        err = mapped.to_stderr_line(module_path=MODULE_PATH, method="main")
        try:
            sys.stderr.write(err + "\n")
        except BrokenPipeError:
            return 1
        except Exception:
            return 1
        return int(mapped.exit_code)


def _initialize_runtime() -> _RuntimeState:
    """
    Summary
    Load configuration, configure logging, and install shutdown handlers for the current process.

    Inputs
    None.

    Outputs
    `_RuntimeState` with initialized runtime dependencies.

    Side effects
    Reads config, configures process logging, writes a startup log event, and installs signal handlers.

    Error handling
    Raises `RuntimeError` with module and method context when runtime setup fails unexpectedly.

    Ties to other methods
    Used by `main` before dispatching into a specific execution mode.

    Why this exists
    Startup wiring should remain isolated from mode-specific logic so failures are easier to localize.
    """
    try:
        cfg = get_config()
        startup_config_report = build_startup_config_validation_report(cfg)
        fields = LoggingFields(
            event_field=cfg.logging.event_field,
            corr_id_field=cfg.logging.correlation_id_field,
            component_field=cfg.logging.component_field,
        )
        configure_logging_once(cfg.logging.redaction(), fields, level=logging.INFO, stream=sys.stderr)
        context = LogContext(component="entrypoint", corr_id=new_correlation_id())
        logger = StructuredLogger("mac_health_checkup", cfg.logging.redaction(), fields)
        logger.info(
            "startup config validated",
            event="startup_config_validated",
            context=context,
            payload=startup_config_report.to_log_payload(),
        )
        shutdown = ShutdownManager()
        shutdown.install_handlers()
        return _RuntimeState(cfg=cfg, logger=logger, context=context, shutdown=shutdown)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_initialize_runtime", "Failed to initialize runtime", exc)
        ) from exc


def _dispatch_mode(args: argparse.Namespace, runtime: _RuntimeState) -> int:
    """
    Summary
    Route parsed CLI args into the matching execution mode.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.

    Outputs
    Mode-specific process exit code.

    Side effects
    Depends on the selected mode and may run collectors, write files, print output, or start the GUI/server.

    Error handling
    Raises contextual runtime errors from downstream mode helpers.

    Ties to other methods
    Used by `main` after startup initialization.

    Why this exists
    Keeping mode selection separate from startup wiring makes the high-level control flow easier to debug.
    """
    if args.snapshot_json_out:
        return _run_snapshot_json_out_mode(args, runtime)
    if args.snapshot_json:
        return _run_snapshot_json_mode(args, runtime)
    _validate_export_args(args)
    if args.diff_snapshots and not args.export:
        return _finish_mode(runtime.shutdown, _run_diff_mode(args))
    if args.export:
        return _finish_mode(runtime.shutdown, _run_export_mode(args))
    if args.serve:
        return _run_serve_mode(runtime)
    if args.cli:
        return _run_cli_mode(args, runtime)
    return _run_gui_mode(args, runtime)


def _run_snapshot_json_out_mode(args: argparse.Namespace, runtime: _RuntimeState) -> int:
    """
    Summary
    Build a live snapshot and write it to a JSON file.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.

    Outputs
    Snapshot-mode process exit code.

    Side effects
    Runs collectors, writes a snapshot file, and triggers shutdown.

    Error handling
    Raises contextual runtime errors from snapshot building or file writing.

    Ties to other methods
    Used by `_dispatch_mode` for `--snapshot-json-out`.

    Why this exists
    File-backed snapshot emission is a distinct automation path and benefits from a focused helper.
    """
    snapshot = _build_snapshot()
    code = _snapshot_exit_code(snapshot, fail_on=str(args.fail_on) if args.fail_on else "")
    payload = _serialize_snapshot(snapshot, pretty=bool(args.snapshot_pretty), ensure_trailing_newline=True)
    _write_text_file(Path(str(args.snapshot_json_out)), payload)
    return _finish_mode(runtime.shutdown, code)


def _run_snapshot_json_mode(args: argparse.Namespace, runtime: _RuntimeState) -> int:
    """
    Summary
    Build a live snapshot and print it to stdout as JSON.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.

    Outputs
    Snapshot-mode process exit code.

    Side effects
    Runs collectors, writes JSON to stdout, and triggers shutdown.

    Error handling
    Raises contextual runtime errors from snapshot building or serialization. Broken pipe output is handled safely.

    Ties to other methods
    Used by `_dispatch_mode` for `--snapshot-json`.

    Why this exists
    Stdout snapshot emission is a stable machine interface for native frontends and automation.
    """
    snapshot = _build_snapshot()
    code = _snapshot_exit_code(snapshot, fail_on=str(args.fail_on) if args.fail_on else "")
    payload = _serialize_snapshot(snapshot, pretty=bool(args.snapshot_pretty), ensure_trailing_newline=False)
    try:
        print(payload)
    except BrokenPipeError:
        return _finish_mode(runtime.shutdown, code)
    return _finish_mode(runtime.shutdown, code)


def _run_serve_mode(runtime: _RuntimeState) -> int:
    """
    Summary
    Start the headless snapshot API server and keep it running until shutdown is requested.

    Inputs
    runtime: Initialized runtime state.

    Outputs
    Process exit code `0` after clean shutdown.

    Side effects
    Starts the HTTP server, prints connection details, waits for shutdown, then stops the server.

    Error handling
    Raises contextual runtime errors when serve mode prerequisites or server lifecycle steps fail.

    Ties to other methods
    Used by `_dispatch_mode` for `--serve`.

    Why this exists
    Serve mode has the largest amount of user-facing operational output and should stay isolated from other modes.
    """
    _ensure_api_enabled(runtime.cfg)
    server = SnapshotApiServer(SECTION_HANDLERS, runtime.cfg.api)
    server.start()
    try:
        public_url = _resolve_public_base_url(default_url=server.url())
        _print_server_banner(server_url=server.url(), public_url=public_url)
        _print_server_network_guidance(runtime.cfg)
        _print_server_tls_guidance(server=server, runtime=runtime, public_url=public_url)
        print(
            "This is the Mac agent (headless). For the macOS UI, run `python3 run.py` or `python3 run_mac_health_checkup_ui.py`."
        )
        print("Press Ctrl+C to stop.")
        runtime.shutdown.wait_for_shutdown()
        return 0
    finally:
        server.stop()
        runtime.shutdown.trigger_shutdown()


def _run_cli_mode(args: argparse.Namespace, runtime: _RuntimeState) -> int:
    """
    Summary
    Run all sections through the console host and emit CLI output.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.

    Outputs
    CLI-mode process exit code.

    Side effects
    Runs collectors, prints CLI output, optionally prints advice, and triggers shutdown.

    Error handling
    Raises contextual runtime errors from section execution or rendering.

    Ties to other methods
    Used by `_dispatch_mode` for explicit `--cli`.

    Why this exists
    CLI mode is the canonical non-GUI workflow and should keep its behavior self-contained.
    """
    host = ConsoleHost()
    code = _run_sections_best_effort(host, logger=runtime.logger, context=runtime.context)
    _print_console_output(host)
    if args.advice:
        _print_cli_advice(host)
    if args.fail_on and _should_fail_on_host(host, fail_on=str(args.fail_on)):
        code = 1
    return _finish_mode(runtime.shutdown, code)


def _run_gui_mode(args: argparse.Namespace, runtime: _RuntimeState) -> int:
    """
    Summary
    Start the GUI when available, falling back to CLI when the GUI stack cannot load.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.

    Outputs
    GUI or CLI fallback exit code.

    Side effects
    Starts the GUI app or runs the CLI fallback path.

    Error handling
    Raises contextual runtime errors from the selected path.

    Ties to other methods
    Used by `_dispatch_mode` when no explicit non-GUI mode was requested.

    Why this exists
    GUI availability depends on the local environment, so fallback behavior should stay explicit and easy to test.
    """
    try:
        from mac_health_checkup.app.gui.app import DashboardApp
    except (ImportError, RuntimeError) as exc:
        return _run_gui_fallback_mode(args, runtime, exc)
    app = DashboardApp()
    app.start()
    return 0


def _run_gui_fallback_mode(args: argparse.Namespace, runtime: _RuntimeState, exc: Exception) -> int:
    """
    Summary
    Fall back to CLI mode when GUI startup is unavailable.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.
    exc: GUI import or startup exception.

    Outputs
    CLI fallback exit code.

    Side effects
    Logs the GUI failure, runs collectors through the CLI host, prints output, and triggers shutdown.

    Error handling
    Raises contextual runtime errors from the fallback CLI path.

    Ties to other methods
    Used by `_run_gui_mode` when Tk or GUI dependencies are missing.

    Why this exists
    GUI fallback needs different logging and execution semantics than explicit CLI mode.
    """
    runtime.logger.warning(
        "tkinter unavailable, falling back to CLI",
        event="gui_unavailable",
        context=runtime.context,
        payload={"error": str(exc)},
    )
    host = ConsoleHost()
    code = _run_sections_best_effort(host, logger=None, context=None)
    _print_console_output(host)
    if args.advice:
        _print_cli_advice(host)
    if args.fail_on and _should_fail_on_host(host, fail_on=str(args.fail_on)):
        code = 1
    return _finish_mode(runtime.shutdown, code)


def _parse_args() -> argparse.Namespace:
    """
    Summary
    Parse CLI arguments for the entrypoint.

    Inputs
    None.

    Outputs
    `argparse.Namespace` with parsed options.

    Side effects
    Reads process argv.

    Error handling
    Raises `RuntimeError` with module and method context if argument parsing fails.

    Ties to other methods
    Used by `main` to determine CLI, GUI, or JSON snapshot mode.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating implementation to a smaller module.
    """
    return _parse_args_impl()


def _boundary_from_args(args: argparse.Namespace | None) -> ErrorBoundary:
    """
    Summary
    Resolve the runtime boundary from parsed entrypoint args.

    Inputs
    args: Parsed args or `None` when parsing failed before boundary mode could be inferred.

    Outputs
    `ErrorBoundary` enum value.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when boundary resolution fails unexpectedly.

    Ties to other methods
    Used by `main` for centralized boundary error mapping.

    Why this exists
    Entrypoint failures should map to a boundary-aware error policy instead of ad-hoc generic handling.
    """
    try:
        if args is None:
            return ErrorBoundary.CLI
        if bool(getattr(args, "serve", False)):
            return ErrorBoundary.API
        if bool(getattr(args, "cli", False)):
            return ErrorBoundary.CLI
        if bool(getattr(args, "snapshot_json", False)) or bool(getattr(args, "snapshot_json_out", None)):
            return ErrorBoundary.CLI
        if bool(getattr(args, "export", None)) or bool(getattr(args, "diff_snapshots", None)):
            return ErrorBoundary.CLI
        return ErrorBoundary.UI
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_boundary_from_args", "Failed to resolve entrypoint boundary", exc)
        ) from exc


def _resolve_public_base_url(*, default_url: str) -> str:
    """
    Summary
    Resolve and validate the optional public base URL environment override.

    Inputs
    default_url: Fallback URL from the running server bind.

    Outputs
    Validated public base URL string.

    Side effects
    Reads `MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL` from environment.

    Error handling
    Raises `RuntimeError` with module and method context when the override is present but invalid.

    Ties to other methods
    Used by `main` in `--serve` mode before printing pairing payloads.

    Why this exists
    Invalid public URLs should fail fast with actionable guidance instead of silently emitting unusable pairing data.
    """
    return _resolve_public_base_url_impl(default_url=default_url)


def _run_diff_mode(args: argparse.Namespace) -> int:
    """
    Summary
    Execute standalone snapshot diff mode.

    Inputs
    args: Parsed CLI args with `diff_snapshots`.

    Outputs
    Process exit code (0 when diff rendered successfully).

    Side effects
    Reads snapshot files and writes to stdout.

    Error handling
    Raises `RuntimeError` with module and method context when diff computation or rendering fails.

    Ties to other methods
    Called by `main` before GUI or CLI execution paths.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating diff internals to a smaller module.
    """
    return _run_diff_mode_impl(args)


def _run_export_mode(args: argparse.Namespace) -> int:
    """
    Summary
    Execute snapshot or diff export mode.

    Inputs
    args: Parsed CLI args with export settings.

    Outputs
    Process exit code.

    Side effects
    May run collectors, reads snapshot files, and writes export output to disk.

    Error handling
    Raises `RuntimeError` with module and method context when export fails.

    Ties to other methods
    Called by `main` prior to serve, GUI, or CLI modes.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating export internals to a smaller module.
    """
    return _run_export_mode_impl(
        args,
        build_snapshot=_build_snapshot,
        resolve_export_path_fn=_resolve_export_path,
        write_text_file_fn=_write_text_file,
        should_fail_on_snapshot_fn=lambda snapshot, fail_on: _should_fail_on_snapshot(
            snapshot, fail_on=fail_on
        ),
    )


def _write_text_file(path: Path, content: str) -> None:
    """
    Summary
    Write UTF-8 text to disk, creating parent directories as needed.

    Inputs
    path: Output path.
    content: Text content.

    Outputs
    None.

    Side effects
    Writes a file to disk.

    Error handling
    Raises `RuntimeError` with module and method context when writing fails.

    Ties to other methods
    Used by snapshot and diff export flows.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating file-writing internals to a smaller module.
    """
    _write_text_file_impl(path, content)


def _resolve_export_path(format_name: str, *, explicit_path: str | None, kind: str) -> Path:
    """
    Summary
    Resolve an export output path from CLI flags, falling back to a git-ignored default location.

    Inputs
    format_name: "markdown" or "html".
    explicit_path: Optional explicit path string.
    kind: "snapshot" or "diff" for default naming.

    Outputs
    Resolved output path.

    Side effects
    None.

    Error handling
    Raises `ValueError` when inputs are invalid.

    Ties to other methods
    Used by `_run_export_mode` to determine export file location.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating path generation to a smaller module.
    """
    return _resolve_export_path_impl(
        format_name,
        explicit_path=explicit_path,
        kind=kind,
        strftime_fn=time.strftime,
    )


def _print_pairing_qr_best_effort(pairing_payload: str, *, enabled: bool) -> None:
    """
    Summary
    Print a pairing QR code best-effort for the iOS client when enabled and supported.

    Inputs
    pairing_payload: Compact JSON payload used by the iOS app.
    enabled: Whether QR output is enabled via config.

    Outputs
    None.

    Side effects
    May execute `qrencode` and writes to stdout.

    Error handling
    Never raises; emits nothing on failure.

    Ties to other methods
    Called by `main` in `--serve` mode after printing the pairing payload JSON.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating QR rendering details to a smaller module.
    """
    _print_pairing_qr_best_effort_impl(pairing_payload, enabled=enabled)


def _run_sections_best_effort(
    host: ConsoleHost, *, logger: StructuredLogger | None, context: LogContext | None
) -> int:
    """
    Summary
    Run all configured sections without letting one failure abort the overall run.

    Inputs
    host: Section host that receives render output.
    logger: Optional structured logger for section lifecycle logs.
    context: Optional log context used when logging is enabled.

    Outputs
    Exit code `0` when all sections run without raising, else `1`.

    Side effects
    Executes section handlers and mutates the host output stores.

    Error handling
    Captures section exceptions into the host field output and continues. Never raises.

    Ties to other methods
    Used by `main` for CLI mode and GUI-unavailable CLI fallback mode.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating per-section orchestration to a smaller module.
    """
    return _run_sections_best_effort_impl(
        host,
        logger=logger,
        context=context,
        section_keys=SECTION_HANDLERS,
        run_section_fn=run_section,
    )


def _should_fail_on_host(host: ConsoleHost, *, fail_on: str) -> bool:
    """
    Summary
    Decide whether CLI-rendered section output should trigger `--fail-on` automation behavior.

    Inputs
    host: ConsoleHost containing rendered fields, metrics, and captured diagnostics.
    fail_on: "warn" or "bad".

    Outputs
    True when any section meets or exceeds the requested severity threshold.

    Side effects
    None.

    Error handling
    Never raises; returns false when evaluation fails.

    Ties to other methods
    Used by `main` in CLI mode to implement `--fail-on warn|bad`.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating advice evaluation to a smaller module.
    """
    return _should_fail_on_host_impl(host, fail_on=fail_on, section_keys=SECTION_HANDLERS)


def _should_fail_on_snapshot(snapshot: object, *, fail_on: str) -> bool:
    """
    Summary
    Decide whether a snapshot should trigger `--fail-on` automation behavior.

    Inputs
    snapshot: Snapshot instance treated as an opaque object.
    fail_on: "warn" or "bad".

    Outputs
    True when any section meets or exceeds the requested severity threshold.

    Side effects
    None.

    Error handling
    Never raises; returns false on evaluation errors.

    Ties to other methods
    Used by `main` for `--snapshot-json` and `--snapshot-json-out`.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating advice evaluation to a smaller module.
    """
    return _should_fail_on_snapshot_impl(snapshot, fail_on=fail_on, snapshot_type=Snapshot)


def _print_console_output(host: ConsoleHost) -> None:
    """
    Summary
    Print rendered section output to stdout for CLI mode.

    Inputs
    host: ConsoleHost holding fields, metrics, and tables.

    Outputs
    None.

    Side effects
    Writes to stdout.

    Error handling
    Raises `RuntimeError` with module and method context if printing fails.

    Ties to other methods
    Used by `main` after running section handlers in CLI fallback mode.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating formatting details to a smaller module.
    """
    _print_console_output_impl(host)


def _print_cli_advice(host: ConsoleHost) -> None:
    """
    Summary
    Print per-section diagnosis and recommended next steps for CLI mode.

    Inputs
    host: ConsoleHost containing rendered fields, metrics, and captured diagnostics.

    Outputs
    None.

    Side effects
    Writes to stdout.

    Error handling
    Raises `RuntimeError` with module and method context when printing fails.

    Ties to other methods
    Called by `main` when `--advice` is enabled.

    Why this exists
    Keeps the stable entrypoint helper name available while delegating advice formatting to a smaller module.
    """
    _print_cli_advice_impl(host, section_keys=SECTION_HANDLERS)


def _validate_export_args(args: argparse.Namespace) -> None:
    """
    Summary
    Validate cross-flag relationships for export and diff modes.

    Inputs
    args: Parsed CLI args.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when incompatible args are provided.

    Ties to other methods
    Used by `_dispatch_mode` before export or diff helpers run.

    Why this exists
    Cross-flag validation is easier to audit when separated from the main mode router.
    """
    try:
        if args.diff_against and not args.export:
            raise RuntimeError("--diff-against requires --export")
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_validate_export_args", "Invalid export arguments", exc)
        ) from exc


def _build_snapshot() -> Snapshot:
    """
    Summary
    Build a live snapshot from the configured section handlers.

    Inputs
    None.

    Outputs
    `Snapshot`.

    Side effects
    Runs section collectors and renderers through the snapshot builder.

    Error handling
    Propagates snapshot builder failures to the caller.

    Ties to other methods
    Used by snapshot, export, and diff-against mode helpers.

    Why this exists
    Snapshot construction should live behind one helper so dependency injection remains straightforward in tests.
    """
    return SnapshotBuilder(SECTION_HANDLERS).build()


def _serialize_snapshot(snapshot: Snapshot, *, pretty: bool, ensure_trailing_newline: bool) -> str:
    """
    Summary
    Convert a snapshot into JSON with the requested formatting behavior.

    Inputs
    snapshot: Snapshot to serialize.
    pretty: Whether to pretty-print JSON.
    ensure_trailing_newline: Whether to guarantee a trailing newline in the returned text.

    Outputs
    Serialized snapshot JSON text.

    Side effects
    None.

    Error handling
    Propagates snapshot serialization failures to the caller.

    Ties to other methods
    Used by snapshot stdout and snapshot file mode helpers.

    Why this exists
    Snapshot serialization rules should stay in one place so file and stdout modes remain consistent.
    """
    payload = snapshot.to_json(pretty=pretty)
    if ensure_trailing_newline and not payload.endswith("\n"):
        return payload + "\n"
    return payload


def _snapshot_exit_code(snapshot: Snapshot, *, fail_on: str) -> int:
    """
    Summary
    Resolve the exit code for snapshot emission modes.

    Inputs
    snapshot: Built snapshot.
    fail_on: Optional fail threshold.

    Outputs
    Snapshot-mode exit code.

    Side effects
    None.

    Error handling
    Propagates fail-policy failures to the caller.

    Ties to other methods
    Used by snapshot stdout and snapshot file mode helpers.

    Why this exists
    Snapshot exit semantics should stay aligned across both machine-readable snapshot outputs.
    """
    code = 0 if snapshot.ok else 1
    if fail_on and _should_fail_on_snapshot(snapshot, fail_on=fail_on):
        return 1
    return code


def _ensure_api_enabled(cfg: Config) -> None:
    """
    Summary
    Validate that API serve mode is enabled in config.

    Inputs
    cfg: Loaded config object.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` when serve mode is requested while `api.enabled` is false.

    Ties to other methods
    Used by `_run_serve_mode`.

    Why this exists
    Serve mode should fail fast with an actionable config error instead of partially initializing.
    """
    if not cfg.api.enabled:
        raise RuntimeError("api.enabled must be true in config to use --serve")


def _print_server_banner(*, server_url: str, public_url: str) -> None:
    """
    Summary
    Print the primary server startup banner and optional public URL override.

    Inputs
    server_url: Bound server URL.
    public_url: Effective public URL for pairing payloads.

    Outputs
    None.

    Side effects
    Writes startup information to stdout.

    Error handling
    None.

    Ties to other methods
    Used by `_run_serve_mode`.

    Why this exists
    Core server connection details should render before the more detailed networking guidance.
    """
    print(f"Snapshot API running at {server_url} (endpoints: /v1/health, /v1/snapshot, /v1/section)")
    if public_url != server_url:
        print(f"Public base URL: {public_url}")


def _print_server_network_guidance(cfg: Config) -> None:
    """
    Summary
    Print LAN and TLS guidance for serve mode.

    Inputs
    cfg: Loaded config object.

    Outputs
    None.

    Side effects
    Writes operational guidance to stdout.

    Error handling
    None.

    Ties to other methods
    Used by `_run_serve_mode`.

    Why this exists
    Networking guidance is a separate concern from banner and pairing output, so it should stay isolated.
    """
    if cfg.api.allow_lan:
        print("LAN access is enabled (api.allow_lan=true). Use a strong token and avoid sharing it.")
        print("If the URL shows 127.0.0.1, use your Mac's LAN IP address with the same port.")
        if not cfg.api.tls_enabled:
            print(
                "Warning: TLS is disabled. This is insecure on untrusted networks. "
                "Enable api.tls_enabled or disable LAN access."
            )


def _print_server_tls_guidance(*, server: SnapshotApiServer, runtime: _RuntimeState, public_url: str) -> None:
    """
    Summary
    Print TLS pairing details for serve mode when TLS is enabled and a certificate fingerprint is available.

    Inputs
    server: Running snapshot API server.
    runtime: Initialized runtime state.
    public_url: Effective public URL for pairing payloads.

    Outputs
    None.

    Side effects
    Writes TLS and pairing guidance to stdout and may render a QR code.

    Error handling
    None. Missing fingerprints simply suppress pairing output.

    Ties to other methods
    Used by `_run_serve_mode`.

    Why this exists
    TLS pairing output is substantial enough to deserve its own helper and keeps `_run_serve_mode` readable.
    """
    if not runtime.cfg.api.tls_enabled:
        return
    fingerprint = server.tls_certificate_fingerprint_sha256()
    if not fingerprint:
        return
    print("TLS is enabled (api.tls_enabled=true).")
    print(f"Certificate fingerprint (sha256): {fingerprint}")
    print("Pairing payload for the optional iOS app (you can ignore this if using the macOS SwiftUI app):")
    pairing_payload = json.dumps(
        {"url": public_url, "token": runtime.cfg.api.auth_token, "pin": fingerprint},
        separators=(",", ":"),
        sort_keys=True,
    )
    print(pairing_payload)
    _print_pairing_qr_best_effort(pairing_payload, enabled=bool(runtime.cfg.api.pairing_qr_enabled))


def _finish_mode(shutdown: ShutdownManager, code: int) -> int:
    """
    Summary
    Trigger shutdown bookkeeping before returning a mode exit code.

    Inputs
    shutdown: Installed shutdown manager.
    code: Mode exit code.

    Outputs
    The provided exit code.

    Side effects
    Triggers shutdown.

    Error handling
    Propagates shutdown manager failures to the caller.

    Ties to other methods
    Used by snapshot, diff, export, and CLI mode helpers.

    Why this exists
    Mode helpers should not repeat the same shutdown trigger boilerplate.
    """
    shutdown.trigger_shutdown()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
