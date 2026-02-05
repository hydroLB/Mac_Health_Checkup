from __future__ import annotations

import argparse
from pathlib import Path

from mac_health_checkup.app.backend.one_click import run_one_click_agent
from mac_health_checkup.core.utils.errors import format_error

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


def main() -> int:
    """
    Purpose: Provide a single-file, one-click entrypoint for running the Mac agent.
    Ties: Calls mac_health_checkup.app.backend.one_click.run_one_click_agent.
    Inputs: None.
    Outputs: Process exit code.
    Side effects: Starts the agent server and writes a derived config under `.local/`.
    Why: Makes "press Run" in an IDE work without requiring manual setup commands.
    """
    try:
        _parse_args()
        repo_root = Path(__file__).resolve().parent
        return run_one_click_agent(repo_root=repo_root)
    except Exception as exc:
        raise RuntimeError(f"{MODULE_PATH}:main failed: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
