from __future__ import annotations

import argparse

from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/entrypoint.py"


def parse_args() -> argparse.Namespace:
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
    Used by `mac_health_checkup.app.entrypoint.main` to determine CLI, GUI, or JSON snapshot mode.

    Why this exists
    Keeps entrypoint behavior explicit and user controlled.
    """
    try:
        parser = _build_parser()
        return parser.parse_args()
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_parse_args", "Failed to parse args", exc)) from exc


def _build_parser() -> argparse.ArgumentParser:
    """
    Summary
    Build the root entrypoint argument parser.

    Inputs
    None.

    Outputs
    Configured `argparse.ArgumentParser`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context if parser construction fails unexpectedly.

    Ties to other methods
    Used by `parse_args` before argv parsing begins.

    Why this exists
    Splits parser construction from parsing so argument groups remain easy to audit and extend.
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
        parser.add_argument(
            "--redact-sensitive",
            action="store_true",
            help=(
                "Redact serial numbers, SSIDs/IP addresses, process IDs, and full process paths "
                "from snapshot, report, and diff output."
            ),
        )
        _add_snapshot_args(parser)
        _add_server_args(parser)
        _add_export_args(parser)
        return parser
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_build_parser", "Failed to build parser", exc)) from exc


def _add_snapshot_args(parser: argparse.ArgumentParser) -> None:
    """
    Summary
    Register snapshot-related CLI flags on the parser.

    Inputs
    parser: Root argument parser.

    Outputs
    None.

    Side effects
    Mutates the parser by adding snapshot flags.

    Error handling
    Raises `RuntimeError` with module and method context if snapshot flag registration fails.

    Ties to other methods
    Used by `_build_parser`.

    Why this exists
    Snapshot flags share mutual exclusivity rules and are easier to maintain as a dedicated group.
    """
    try:
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
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_add_snapshot_args", "Failed to register snapshot args", exc)
        ) from exc


def _add_server_args(parser: argparse.ArgumentParser) -> None:
    """
    Summary
    Register server-related CLI flags on the parser.

    Inputs
    parser: Root argument parser.

    Outputs
    None.

    Side effects
    Mutates the parser by adding server flags.

    Error handling
    Raises `RuntimeError` with module and method context if server flag registration fails.

    Ties to other methods
    Used by `_build_parser`.

    Why this exists
    Serve mode has a small dedicated flag surface and should stay isolated from export and snapshot settings.
    """
    try:
        parser.add_argument(
            "--serve",
            action="store_true",
            help="Run the local snapshot API server for native clients (requires api.enabled).",
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_add_server_args", "Failed to register server args", exc)
        ) from exc


def _add_export_args(parser: argparse.ArgumentParser) -> None:
    """
    Summary
    Register export and diff CLI flags on the parser.

    Inputs
    parser: Root argument parser.

    Outputs
    None.

    Side effects
    Mutates the parser by adding export and diff flags.

    Error handling
    Raises `RuntimeError` with module and method context if export flag registration fails.

    Ties to other methods
    Used by `_build_parser`.

    Why this exists
    Export workflows combine multiple related inputs, so grouping them keeps the root parser readable.
    """
    try:
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
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_add_export_args", "Failed to register export args", exc)
        ) from exc
