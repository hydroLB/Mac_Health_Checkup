from __future__ import annotations

import argparse
import sys

from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils.error_boundary import ErrorBoundary, map_boundary_exception

MODULE_PATH = "run.py"


def _parse_args() -> argparse.Namespace:
    """
    Summary
    Parse CLI arguments for the one-file run entrypoint.

    Inputs
    None.

    Outputs
    argparse.Namespace with parsed options.

    Side effects
    Reads process argv.

    Error handling
    Raises contextual errors from `run.py:_parse_args` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by main to choose between UI and headless agent modes.

    Why this exists
    Keeps "press Run" ergonomics while still allowing explicit mode selection.
    """
    try:
        parser = argparse.ArgumentParser(description="Run Mac Health Checkup.")
        parser.add_argument(
            "--agent",
            action="store_true",
            help="Run the headless agent API server (prints pairing payload, no UI window).",
        )
        return parser.parse_args()
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_parse_args", "Failed to parse args", exc)) from exc


def _emit_boundary_error(method: str, message: str, exc: Exception) -> None:
    """
    Summary
    Write a formatted boundary error for the one-file runner.

    Inputs
    method: Boundary method name associated with the failure.
    message: High-level failure context.
    exc: Captured exception instance.

    Outputs
    None.

    Side effects
    Writes one line to stderr.

    Error handling
    Raises contextual errors from `run.py:_emit_boundary_error` when output formatting fails unexpectedly.

    Ties to other methods
    Used by `main` for script-boundary error reporting.

    Why this exists
    Keeps user-facing failures explicit without surfacing Python tracebacks for expected operational errors.
    """
    try:
        mapped = map_boundary_exception(exc, boundary=ErrorBoundary.CLI, default_message=message)
        print(mapped.to_stderr_line(module_path=MODULE_PATH, method=method), file=sys.stderr)
    except (RuntimeError, ValueError, TypeError, OSError) as emit_exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_emit_boundary_error",
                "Failed while emitting boundary error",
                emit_exc,
            )
        ) from emit_exc


def main() -> int:
    """
    Summary
    Provide a single-file entrypoint for running the project from an IDE.

    Inputs
    CLI args parsed by _parse_args.

    Outputs
    Process exit code.

    Side effects
    Starts either the SwiftUI dashboard or the Python agent server.

    Error handling
    Returns exit code `2` after emitting a formatted boundary error for runtime failures. `argparse` can still raise
    `SystemExit` for `--help`.

    Ties to other methods
    Dispatches to `run_mac_health_checkup_ui.py` (default) or `run_mac_health_checkup.py` (agent).

    Why this exists
    Makes "press Run" launch the UI without requiring the user to remember filenames.
    """
    try:
        args = _parse_args()
        if args.agent:
            from run_mac_health_checkup import main as run_agent

            return int(run_agent())
        from run_mac_health_checkup_ui import main as run_ui

        return int(run_ui())
    except (RuntimeError, ValueError, TypeError, ImportError, OSError) as exc:
        _emit_boundary_error("main", "Failed to run project", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
