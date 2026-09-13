from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
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
from mac_health_checkup.app.entrypoint_support.interactive_modes import (
    run_cli_mode as _run_cli_mode_impl,
)
from mac_health_checkup.app.entrypoint_support.interactive_modes import (
    run_gui_fallback_mode as _run_gui_fallback_mode_impl,
)
from mac_health_checkup.app.entrypoint_support.interactive_modes import (
    run_gui_mode as _run_gui_mode_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    _RuntimeStateProtocol,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    build_snapshot as _build_snapshot_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    ensure_api_enabled as _ensure_api_enabled_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    print_server_banner as _print_server_banner_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    print_server_network_guidance as _print_server_network_guidance_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    print_server_tls_guidance as _print_server_tls_guidance_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    run_serve_mode as _run_serve_mode_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    run_snapshot_json_mode as _run_snapshot_json_mode_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    run_snapshot_json_out_mode as _run_snapshot_json_out_mode_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    serialize_snapshot as _serialize_snapshot_impl,
)
from mac_health_checkup.app.entrypoint_support.modes import (
    snapshot_exit_code as _snapshot_exit_code_impl,
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
from mac_health_checkup.app.entrypoint_support.runtime_mode import (
    _ShutdownManagerProtocol,
)
from mac_health_checkup.app.entrypoint_support.runtime_mode import (
    boundary_from_args as _boundary_from_args_impl,
)
from mac_health_checkup.app.entrypoint_support.runtime_mode import (
    finish_mode as _finish_mode_impl,
)
from mac_health_checkup.app.entrypoint_support.runtime_mode import (
    initialize_runtime as _initialize_runtime_impl,
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
    return _initialize_runtime_impl(
        get_config_fn=get_config,
        build_startup_config_validation_report_fn=build_startup_config_validation_report,
        configure_logging_once_fn=configure_logging_once,
        new_correlation_id_fn=new_correlation_id,
        structured_logger_type=StructuredLogger,
        logging_fields_type=LoggingFields,
        shutdown_manager_type=ShutdownManager,
        state_factory=lambda cfg, logger, context, shutdown: _RuntimeState(
            cfg=cfg,
            logger=logger,
            context=context,
            shutdown=shutdown,
        ),
    )


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
    return _run_snapshot_json_out_mode_impl(
        args,
        runtime,
        build_snapshot_fn=_build_snapshot,
        snapshot_exit_code_fn=lambda snapshot, fail_on: _snapshot_exit_code(snapshot, fail_on=fail_on),
        serialize_snapshot_fn=lambda snapshot, pretty, ensure_trailing_newline: _serialize_snapshot(
            snapshot,
            pretty=pretty,
            ensure_trailing_newline=ensure_trailing_newline,
        ),
        write_text_file_fn=_write_text_file,
        finish_mode_fn=_finish_mode,
    )


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
    return _run_snapshot_json_mode_impl(
        args,
        runtime,
        build_snapshot_fn=_build_snapshot,
        snapshot_exit_code_fn=lambda snapshot, fail_on: _snapshot_exit_code(snapshot, fail_on=fail_on),
        serialize_snapshot_fn=lambda snapshot, pretty, ensure_trailing_newline: _serialize_snapshot(
            snapshot,
            pretty=pretty,
            ensure_trailing_newline=ensure_trailing_newline,
        ),
        finish_mode_fn=_finish_mode,
    )


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
    return _run_serve_mode_impl(
        runtime,
        section_handlers=SECTION_HANDLERS,
        snapshot_api_server_type=SnapshotApiServer,
        resolve_public_base_url_fn=lambda default_url: _resolve_public_base_url(default_url=default_url),
        print_pairing_qr_best_effort_fn=lambda pairing_payload, enabled: _print_pairing_qr_best_effort(
            pairing_payload,
            enabled=enabled,
        ),
        ensure_api_enabled_fn=_ensure_api_enabled,
        print_server_banner_fn=lambda server_url, public_url: _print_server_banner(
            server_url=server_url,
            public_url=public_url,
        ),
        print_server_network_guidance_fn=_print_server_network_guidance,
        print_server_tls_guidance_fn=lambda server,
        state,
        public_url,
        print_pairing_qr_fn: _print_server_tls_guidance(
            server=server,
            runtime=state,
            public_url=public_url,
            print_pairing_qr_best_effort_fn=print_pairing_qr_fn,
        ),
    )


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
    return _run_cli_mode_impl(
        args,
        runtime,
        console_host_type=ConsoleHost,
        run_sections_best_effort_fn=lambda host, logger, context: _run_sections_best_effort(
            host,
            logger=logger,
            context=context,
        ),
        print_console_output_fn=_print_console_output,
        print_cli_advice_fn=_print_cli_advice,
        should_fail_on_host_fn=lambda host, fail_on: _should_fail_on_host(host, fail_on=fail_on),
        finish_mode_fn=_finish_mode,
    )


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
    return _run_gui_mode_impl(
        args,
        runtime,
        run_gui_fallback_mode_fn=lambda fallback_args, fallback_runtime, exc: _run_gui_fallback_mode(
            fallback_args,
            runtime,
            exc,
        ),
    )


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
    return _run_gui_fallback_mode_impl(
        args,
        runtime,
        exc,
        console_host_type=ConsoleHost,
        run_sections_best_effort_fn=lambda host, logger, context: _run_sections_best_effort(
            host,
            logger=logger,
            context=context,
        ),
        print_console_output_fn=_print_console_output,
        print_cli_advice_fn=_print_cli_advice,
        should_fail_on_host_fn=lambda host, fail_on: _should_fail_on_host(host, fail_on=fail_on),
        finish_mode_fn=_finish_mode,
    )


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
    return _boundary_from_args_impl(args)


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
    return _build_snapshot_impl(section_handlers=SECTION_HANDLERS, snapshot_builder_type=SnapshotBuilder)


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
    return _serialize_snapshot_impl(
        snapshot,
        pretty=pretty,
        ensure_trailing_newline=ensure_trailing_newline,
    )


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
    return _snapshot_exit_code_impl(
        snapshot,
        fail_on=fail_on,
        should_fail_on_snapshot_fn=lambda value, threshold: _should_fail_on_snapshot(
            value,
            fail_on=threshold,
        ),
    )


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
    _ensure_api_enabled_impl(cfg)


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
    _print_server_banner_impl(server_url=server_url, public_url=public_url)


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
    _print_server_network_guidance_impl(cfg)


def _print_server_tls_guidance(
    *,
    server: SnapshotApiServer,
    runtime: _RuntimeStateProtocol,
    public_url: str,
    print_pairing_qr_best_effort_fn: Callable[[str, bool], None] | None = None,
) -> None:
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
    qr_fn = (
        print_pairing_qr_best_effort_fn
        if print_pairing_qr_best_effort_fn is not None
        else lambda pairing_payload, enabled: _print_pairing_qr_best_effort(pairing_payload, enabled=enabled)
    )
    _print_server_tls_guidance_impl(
        server=server,
        runtime=runtime,
        public_url=public_url,
        print_pairing_qr_best_effort_fn=qr_fn,
    )


def _finish_mode(shutdown: _ShutdownManagerProtocol, code: int) -> int:
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
    return _finish_mode_impl(shutdown, code)


if __name__ == "__main__":
    raise SystemExit(main())
