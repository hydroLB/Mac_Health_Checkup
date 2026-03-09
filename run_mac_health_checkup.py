from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mac_health_checkup.app.backend import run_one_click_agent
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils.error_boundary import ErrorBoundary, map_boundary_exception

MODULE_PATH = "run_mac_health_checkup.py"


def _parse_args() -> argparse.Namespace:
    """
    Summary
    Parse CLI arguments for the one-click Mac agent runner.

    Inputs
    None.

    Outputs
    Parsed `argparse.Namespace`.

    Side effects
    Reads process argv.

    Error handling
    Raises `RuntimeError` with module and method context if parsing fails.

    Ties to other methods
    Used by `main` to support `--help` without starting the server.

    Why this exists
    `python3 run_mac_health_checkup.py --help` should not attempt to bind sockets or start background services.
    """
    try:
        parser = argparse.ArgumentParser(description="Run the Mac Health Checkup headless agent (one-click).")
        # Preserve existing behavior of ignoring unknown flags while still supporting `--help`.
        return parser.parse_known_args()[0]
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_parse_args", "Failed to parse args", exc)) from exc


def _emit_boundary_error(method: str, message: str, exc: Exception) -> None:
    """
    Summary
    Write a formatted boundary error for the one-click agent runner.

    Inputs
    method: Boundary method name associated with the failure.
    message: High-level failure context.
    exc: Captured exception instance.

    Outputs
    None.

    Side effects
    Writes one line to stderr.

    Error handling
    Raises contextual errors from `run_mac_health_checkup.py:_emit_boundary_error` when output formatting fails unexpectedly.

    Ties to other methods
    Used by `main` as the script boundary error sink.

    Why this exists
    Keeps boundary failures consistent and action-oriented without tracebacks for expected runtime issues.
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
    Provide a single-file, one-click entrypoint for running the Mac agent.

    Inputs
    None.

    Outputs
    Process exit code.

    Side effects
    Starts the agent server and writes a derived config under `.local/`.

    Error handling
    Returns exit code `2` after emitting a formatted boundary error for runtime failures. `argparse` can still raise
    `SystemExit` for `--help`.

    Ties to other methods
    Calls mac_health_checkup.app.backend.one_click.run_one_click_agent.

    Why this exists
    Makes "press Run" in an IDE work without requiring manual setup commands.
    """
    try:
        _parse_args()
        repo_root = Path(__file__).resolve().parent
        return run_one_click_agent(repo_root=repo_root)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError) as exc:
        _emit_boundary_error("main", "Failed to run one-click agent", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
