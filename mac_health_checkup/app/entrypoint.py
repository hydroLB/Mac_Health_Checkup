from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

from mac_health_checkup.app.backend.server import SnapshotApiServer
from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.app.gui.dashboard.sections import SECTION_HANDLERS, run_section
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.loggers import (
    LogContext,
    LoggingFields,
    StructuredLogger,
    configure_logging_once,
    new_correlation_id,
)

MODULE_PATH = "mac_health_checkup/app/entrypoint.py"


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
    Uses `SECTION_HANDLERS` and `run_section` for section execution. Uses `emit_snapshot_json` for frontend
    snapshot mode.

    Why this exists
    Provides a single deterministic entrypoint with clear mode selection and safe fallbacks.
    """
    try:
        args = _parse_args()
        cfg = get_config()
        fields = LoggingFields(
            event_field=cfg.logging.event_field,
            corr_id_field=cfg.logging.correlation_id_field,
            component_field=cfg.logging.component_field,
        )
        log_stream = sys.stderr
        configure_logging_once(cfg.logging.redaction(), fields, level=logging.INFO, stream=log_stream)
        corr_id = new_correlation_id()
        logger = StructuredLogger("mac_health_checkup", cfg.logging.redaction(), fields)
        context = LogContext(component="entrypoint", corr_id=corr_id)
        shutdown = ShutdownManager()
        shutdown.install_handlers()

        if args.snapshot_json_out:
            from mac_health_checkup.app.backend.snapshot import SnapshotBuilder

            snapshot = SnapshotBuilder(SECTION_HANDLERS).build()
            code = 0 if snapshot.ok else 1
            if args.fail_on and _should_fail_on_snapshot(snapshot, fail_on=str(args.fail_on)):
                code = 1
            payload = snapshot.to_json(pretty=bool(args.snapshot_pretty))
            _write_text_file(
                Path(args.snapshot_json_out),
                payload + ("\n" if not payload.endswith("\n") else ""),
            )
            shutdown.trigger_shutdown()
            return code

        if args.snapshot_json:
            from mac_health_checkup.app.backend.snapshot import SnapshotBuilder

            snapshot = SnapshotBuilder(SECTION_HANDLERS).build()
            code = 0 if snapshot.ok else 1
            if args.fail_on and _should_fail_on_snapshot(snapshot, fail_on=str(args.fail_on)):
                code = 1
            payload = snapshot.to_json(pretty=bool(args.snapshot_pretty))
            try:
                print(payload)
            except BrokenPipeError:
                shutdown.trigger_shutdown()
                return code
            shutdown.trigger_shutdown()
            return code

        if args.diff_against and not args.export:
            raise RuntimeError("--diff-against requires --export")

        if args.diff_snapshots and not args.export:
            code = _run_diff_mode(args)
            shutdown.trigger_shutdown()
            return code

        if args.export:
            code = _run_export_mode(args)
            shutdown.trigger_shutdown()
            return code

        if args.serve:
            if not cfg.api.enabled:
                raise RuntimeError("api.enabled must be true in config to use --serve")
            server = SnapshotApiServer(SECTION_HANDLERS, cfg.api)
            server.start()
            public_url = os.environ.get("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL") or server.url()
            print(
                f"Snapshot API running at {server.url()} (endpoints: /v1/health, /v1/snapshot, /v1/section)"
            )
            if public_url != server.url():
                print(f"Public base URL: {public_url}")
            if cfg.api.allow_lan:
                print("LAN access is enabled (api.allow_lan=true). Use a strong token and avoid sharing it.")
                print("If the URL shows 127.0.0.1, use your Mac's LAN IP address with the same port.")
                if not cfg.api.tls_enabled:
                    print(
                        "Warning: TLS is disabled. This is insecure on untrusted networks. "
                        "Enable api.tls_enabled or disable LAN access."
                    )
            if cfg.api.tls_enabled:
                fingerprint = server.tls_certificate_fingerprint_sha256()
                if fingerprint:
                    print("TLS is enabled (api.tls_enabled=true).")
                    print(f"Certificate fingerprint (sha256): {fingerprint}")
                    print(
                        "Pairing payload for the optional iOS app (you can ignore this if using the macOS SwiftUI app):"
                    )
                    pairing_payload = json.dumps(
                        {"url": public_url, "token": cfg.api.auth_token, "pin": fingerprint},
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    print(pairing_payload)
                    _print_pairing_qr_best_effort(pairing_payload, enabled=bool(cfg.api.pairing_qr_enabled))
            print(
                "This is the Mac agent (headless). For the macOS UI, run `python3 run.py` or `python3 run_mac_health_checkup_ui.py`."
            )
            print("Press Ctrl+C to stop.")
            try:
                shutdown.wait_for_shutdown()
            finally:
                server.stop()
                shutdown.trigger_shutdown()
            return 0

        if args.cli:
            host = ConsoleHost()
            code = _run_sections_best_effort(host, logger=logger, context=context)
            _print_console_output(host)
            if args.advice:
                _print_cli_advice(host)
            if args.fail_on and _should_fail_on_host(host, fail_on=str(args.fail_on)):
                code = 1
            shutdown.trigger_shutdown()
            return code

        try:
            from mac_health_checkup.app.gui.app import DashboardApp
        except (ImportError, RuntimeError) as exc:
            logger.warning(
                "tkinter unavailable, falling back to CLI",
                event="gui_unavailable",
                context=context,
                payload={"error": str(exc)},
            )
            host = ConsoleHost()
            code = _run_sections_best_effort(host, logger=None, context=None)
            _print_console_output(host)
            if args.advice:
                _print_cli_advice(host)
            if args.fail_on and _should_fail_on_host(host, fail_on=str(args.fail_on)):
                code = 1
            shutdown.trigger_shutdown()
            return code

        app = DashboardApp()
        app.start()
        return 0
    except Exception as exc:
        err = format_error(MODULE_PATH, "main", "Entrypoint failed", exc)
        try:
            sys.stderr.write(err + "\n")
        except BrokenPipeError:
            return 1
        except Exception:
            return 1
        return 1


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
    Provides a readable CLI summary without requiring a GUI.
    """
    try:
        for key, value in host.fields.items():
            print(f"[{key}] {value}")
        for key, metric_rows in host.metrics.items():
            print(f"\n[{key} metrics]")
            for label, value, status in metric_rows:
                print(f"- {label}: {value} ({status})")
        for key, table_rows in host.tables.items():
            print(f"\n[{key} table]")
            headers = host.headers.get(key)
            if headers:
                print(" | ".join(headers))
            for row in table_rows:
                print(" | ".join(row))
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_print_console_output", "Failed to print output", exc)
        ) from exc


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
    Keeps entrypoint behavior explicit and user controlled.
    """
    try:
        parser = argparse.ArgumentParser(description="Run Mac Health Checkup.")
        parser.add_argument("--cli", action="store_true", help="Run in CLI mode only.")
        parser.add_argument(
            "--fail-on",
            choices=("warn", "bad"),
            help="Exit non-zero when a snapshot/CLI run contains a warn or bad signal (automation).",
        )
        parser.add_argument(
            "--advice",
            action="store_true",
            help="Print per-section diagnosis and recommended next steps in CLI mode.",
        )
        snapshot_group = parser.add_mutually_exclusive_group()
        snapshot_group.add_argument(
            "--snapshot-json",
            action="store_true",
            help="Emit a single JSON snapshot to stdout for native frontends.",
        )
        snapshot_group.add_argument(
            "--snapshot-json-out",
            help="Write a single JSON snapshot to the given file path (no stdout).",
        )
        parser.add_argument(
            "--snapshot-pretty",
            action="store_true",
            help="Pretty-print snapshot JSON when used with --snapshot-json.",
        )
        parser.add_argument(
            "--serve",
            action="store_true",
            help="Run the local snapshot API server for native clients (requires api.enabled).",
        )
        parser.add_argument(
            "--export",
            choices=("markdown", "html"),
            help="Export a snapshot report (or diff report when --diff-snapshots is used) to a file.",
        )
        parser.add_argument(
            "--export-path",
            help="Optional explicit path for --export output. Defaults to a timestamped file under .local/reports/.",
        )
        parser.add_argument(
            "--export-from-snapshot",
            help="Export a report from an existing snapshot JSON file without running collectors.",
        )
        parser.add_argument(
            "--export-include-diagnostics",
            action="store_true",
            help="Include raw diagnostics blobs in exports (may contain sensitive system details).",
        )
        parser.add_argument(
            "--diff-snapshots",
            nargs=2,
            metavar=("BEFORE_JSON", "AFTER_JSON"),
            help="Compute a UI-facing diff between two snapshot JSON files (prints Markdown unless --export is set).",
        )
        parser.add_argument(
            "--diff-against",
            help="Compute a diff between the current snapshot and a prior snapshot JSON file (requires --export).",
        )
        return parser.parse_args()
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_parse_args", "Failed to parse args", exc)) from exc


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
    Called by `main` before GUI/CLI execution paths.

    Why this exists
    Diffs between existing snapshots should be fast and should not run collectors.
    """
    try:
        from mac_health_checkup.app.reports import (
            diff_snapshots,
            load_snapshot_from_path,
            render_diff_markdown,
        )

        before_path, after_path = args.diff_snapshots
        before = load_snapshot_from_path(Path(str(before_path)))
        after = load_snapshot_from_path(Path(str(after_path)))
        diff = diff_snapshots(before, after)
        print(render_diff_markdown(diff), end="")
        return 0
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_run_diff_mode", "Diff mode failed", exc)) from exc


def _run_export_mode(args: argparse.Namespace) -> int:
    """
    Summary
    Execute snapshot or diff export mode.

    Inputs
    args: Parsed CLI args with export settings.

    Outputs
    Process exit code.

    Side effects
    May run collectors (when exporting a live snapshot), reads snapshot files, and writes export output to disk.

    Error handling
    Raises `RuntimeError` with module and method context when export fails.

    Ties to other methods
    Called by `main` prior to serve/GUI/CLI modes.

    Why this exists
    Exports produce shareable artifacts (Markdown/HTML) without requiring the recipient to run the program.
    """
    try:
        export_format = str(args.export)
        include_diagnostics = bool(args.export_include_diagnostics)
        fail_on = str(args.fail_on) if getattr(args, "fail_on", None) else ""
        export_path = _resolve_export_path(
            export_format,
            explicit_path=str(args.export_path) if args.export_path else None,
            kind="diff" if args.diff_snapshots or args.diff_against else "snapshot",
        )

        from mac_health_checkup.app.reports import (
            diff_snapshots,
            load_snapshot_from_path,
            render_diff_html,
            render_diff_markdown,
            render_snapshot_html,
            render_snapshot_markdown,
        )

        if args.diff_snapshots:
            before_path, after_path = args.diff_snapshots
            before = load_snapshot_from_path(Path(str(before_path)))
            after = load_snapshot_from_path(Path(str(after_path)))
            diff = diff_snapshots(before, after)
            content = render_diff_markdown(diff) if export_format == "markdown" else render_diff_html(diff)
            _write_text_file(export_path, content)
            print(str(export_path))
            return 0

        if args.diff_against:
            baseline = load_snapshot_from_path(Path(str(args.diff_against)))
            from mac_health_checkup.app.backend.snapshot import SnapshotBuilder

            current = SnapshotBuilder(SECTION_HANDLERS).build()
            diff = diff_snapshots(baseline, current)
            content = render_diff_markdown(diff) if export_format == "markdown" else render_diff_html(diff)
            _write_text_file(export_path, content)
            print(str(export_path))
            return 0 if current.ok else 1

        if args.export_from_snapshot:
            snapshot = load_snapshot_from_path(Path(str(args.export_from_snapshot)))
            content = (
                render_snapshot_markdown(snapshot, include_diagnostics=include_diagnostics)
                if export_format == "markdown"
                else render_snapshot_html(snapshot, include_diagnostics=include_diagnostics)
            )
            _write_text_file(export_path, content)
            print(str(export_path))
            code = 0 if snapshot.ok else 1
            if fail_on and _should_fail_on_snapshot(snapshot, fail_on=fail_on):
                code = 1
            return code

        from mac_health_checkup.app.backend.snapshot import SnapshotBuilder

        snapshot = SnapshotBuilder(SECTION_HANDLERS).build()
        content = (
            render_snapshot_markdown(snapshot, include_diagnostics=include_diagnostics)
            if export_format == "markdown"
            else render_snapshot_html(snapshot, include_diagnostics=include_diagnostics)
        )
        _write_text_file(export_path, content)
        print(str(export_path))
        code = 0 if snapshot.ok else 1
        if fail_on and _should_fail_on_snapshot(snapshot, fail_on=fail_on):
            code = 1
        return code
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_run_export_mode", "Export mode failed", exc)) from exc


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
    Exports should be deterministic and should fail with actionable messages when paths are invalid.
    """
    try:
        out_path = path.expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_write_text_file", f"Write failed: {path}", exc)
        ) from exc


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
    Default exports should not clutter the repo root and should live under `.local/` by default.
    """
    if explicit_path:
        return Path(explicit_path)
    ext = "md" if format_name == "markdown" else "html"
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return Path(".local") / "reports" / f"mac-health-checkup-{kind}-{timestamp}.{ext}"


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
    Pairing via QR reduces manual typing of tokens on mobile devices.
    """
    try:
        if not enabled:
            return
        from mac_health_checkup.core.utils.qr import maybe_render_qr_ansiutf8

        qr = maybe_render_qr_ansiutf8(pairing_payload, timeout_sec=3)
        if not qr:
            return
        print()
        print("Pairing QR (scan in iOS app):")
        print(qr)
        print()
    except Exception:
        return


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
    Ensures the CLI remains resilient even when individual diagnostics are unavailable on a given macOS build.
    """
    exit_code = 0
    for key in SECTION_HANDLERS:
        if logger is not None and context is not None:
            logger.info("running section", event="section_start", context=context, payload={"section": key})
        try:
            result = run_section(host, key)
            if isinstance(result, dict):
                host.diagnostics[key] = result
            if logger is not None and context is not None:
                logger.info(
                    "section completed",
                    event="section_end",
                    context=context,
                    payload={"section": key, "ok": bool(result)},
                )
        except Exception as exc:
            exit_code = 1
            host.diagnostics[key] = {"ok": False, "error": str(exc)}
            if logger is not None and context is not None:
                logger.error(
                    "section failed",
                    event="section_error",
                    context=context,
                    payload={"section": key, "error": str(exc), "error_type": type(exc).__name__},
                )
            field_exc: Exception | None = None
            try:
                host.set_field(key, f"Error: {type(exc).__name__}", tooltip=str(exc))
            except Exception as render_exc:
                field_exc = render_exc
            if field_exc is not None:
                if logger is not None and context is not None:
                    logger.error(
                        "failed to render section error field",
                        event="section_error_render_failed",
                        context=context,
                        payload={
                            "section": key,
                            "error": str(field_exc),
                            "error_type": type(field_exc).__name__,
                        },
                    )
                continue
    return exit_code


def _should_fail_on_host(host: ConsoleHost, *, fail_on: str) -> bool:
    """
    Summary
    Decide whether CLI-rendered section output should trigger `--fail-on` automation behavior.

    Inputs
    host: ConsoleHost containing rendered fields/metrics and captured diagnostics.
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
    Automation should not depend on parsing human formatted CLI output.
    """
    try:
        from typing import cast

        from mac_health_checkup.app.actionability import AdviceSeverity, build_section_advice, should_fail_on

        for key in SECTION_HANDLERS:
            advice = build_section_advice(
                key,
                field=host.fields.get(key),
                metrics=host.metrics.get(key),
                diagnostics=host.diagnostics.get(key),
            )
            severity = advice.get("severity")
            if severity in {"ok", "warn", "bad"} and should_fail_on(cast(AdviceSeverity, severity), fail_on):
                return True
        return False
    except Exception:
        return False


def _should_fail_on_snapshot(snapshot: object, *, fail_on: str) -> bool:
    """
    Summary
    Decide whether a snapshot should trigger `--fail-on` automation behavior.

    Inputs
    snapshot: Snapshot instance (treated as an opaque object to keep import boundaries small).
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
    Snapshot JSON is machine readable, but the process exit code is still the cleanest automation signal.
    """
    try:
        from typing import cast

        from mac_health_checkup.app.actionability import AdviceSeverity, build_section_advice, should_fail_on
        from mac_health_checkup.app.backend.snapshot import Snapshot

        if not isinstance(snapshot, Snapshot):
            return False
        for section in snapshot.sections:
            advice = build_section_advice(
                section.key,
                field=section.field,
                metrics=section.metrics,
                diagnostics=section.diagnostics,
            )
            severity = advice.get("severity")
            if severity in {"ok", "warn", "bad"} and should_fail_on(cast(AdviceSeverity, severity), fail_on):
                return True
        return False
    except Exception:
        return False


def _print_cli_advice(host: ConsoleHost) -> None:
    """
    Summary
    Print per-section diagnosis and recommended next steps for CLI mode.

    Inputs
    host: ConsoleHost containing rendered fields/metrics and captured diagnostics.

    Outputs
    None.

    Side effects
    Writes to stdout.

    Error handling
    Raises `RuntimeError` with module and method context when printing fails.

    Ties to other methods
    Called by `main` when `--advice` is enabled.

    Why this exists
    Actionability belongs next to the rendered snapshot so users can move directly from signals to next steps.
    """
    try:
        from mac_health_checkup.app.actionability import build_section_advice

        print("\n[advice]")
        for key in SECTION_HANDLERS:
            advice = build_section_advice(
                key,
                field=host.fields.get(key),
                metrics=host.metrics.get(key),
                diagnostics=host.diagnostics.get(key),
            )
            severity = str(advice.get("severity", "ok")).upper()
            diagnosis = str(advice.get("diagnosis", "")).strip()
            steps = advice.get("next_steps")
            print(f"\n[{key}] {severity}")
            if diagnosis:
                print(diagnosis)
            if isinstance(steps, list):
                for step in steps:
                    text = str(step).strip()
                    if text:
                        print(f"- {text}")
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_print_cli_advice", "Failed to print advice", exc)
        ) from exc
