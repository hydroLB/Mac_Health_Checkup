from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from mac_health_checkup.app.backend.server import SnapshotApiServer
from mac_health_checkup.app.backend.snapshot import emit_snapshot_json
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
        cfg = get_config()
        fields = LoggingFields(
            event_field=cfg.logging.event_field,
            corr_id_field=cfg.logging.correlation_id_field,
            component_field=cfg.logging.component_field,
        )
        args = _parse_args()
        log_stream = sys.stderr
        configure_logging_once(cfg.logging.redaction(), fields, level=logging.INFO, stream=log_stream)
        corr_id = new_correlation_id()
        logger = StructuredLogger("mac_health_checkup", cfg.logging.redaction(), fields)
        context = LogContext(component="entrypoint", corr_id=corr_id)
        shutdown = ShutdownManager()
        shutdown.install_handlers()

        if args.snapshot_json:
            code, payload = emit_snapshot_json(SECTION_HANDLERS, pretty=bool(args.snapshot_pretty))
            try:
                print(payload)
            except BrokenPipeError:
                shutdown.trigger_shutdown()
                return code
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
                    print(
                        json.dumps(
                            {"url": public_url, "token": cfg.api.auth_token, "pin": fingerprint},
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                    )
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
            "--snapshot-json",
            action="store_true",
            help="Emit a single JSON snapshot to stdout for native frontends.",
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
        return parser.parse_args()
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_parse_args", "Failed to parse args", exc)) from exc


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
            if logger is not None and context is not None:
                logger.info(
                    "section completed",
                    event="section_end",
                    context=context,
                    payload={"section": key, "ok": bool(result)},
                )
        except Exception as exc:
            exit_code = 1
            if logger is not None and context is not None:
                logger.error(
                    "section failed",
                    event="section_error",
                    context=context,
                    payload={"section": key, "error": str(exc), "error_type": type(exc).__name__},
                )
            try:
                host.set_field(key, f"Error: {type(exc).__name__}", tooltip=str(exc))
            except Exception:
                continue
    return exit_code
