from __future__ import annotations

import argparse

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "run.py"


def _parse_args() -> argparse.Namespace:
    """
    Purpose: Parse CLI arguments for the one-file run entrypoint.
    Ties: Used by main to choose between UI and headless agent modes.
    Inputs: None.
    Outputs: argparse.Namespace with parsed options.
    Side effects: Reads process argv.
    Why: Keeps "press Run" ergonomics while still allowing explicit mode selection.
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


def main() -> int:
    """
    Purpose: Provide a single-file entrypoint for running the project from an IDE.
    Ties: Dispatches to `run_mac_health_checkup_ui.py` (default) or `run_mac_health_checkup.py` (agent).
    Inputs: CLI args parsed by _parse_args.
    Outputs: Process exit code.
    Side effects: Starts either the SwiftUI dashboard or the Python agent server.
    Why: Makes "press Run" launch the UI without requiring the user to remember filenames.
    """
    try:
        args = _parse_args()
        if args.agent:
            from run_mac_health_checkup import main as run_agent

            return int(run_agent())
        from run_mac_health_checkup_ui import main as run_ui

        return int(run_ui())
    except (RuntimeError, ValueError, TypeError, ImportError, OSError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "main", "Failed to run project", exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
