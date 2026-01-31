from __future__ import annotations

from mac_health_checkup.app.entrypoint import main
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/__main__.py"


def _run() -> None:
    """
    Purpose: Execute the main entrypoint and exit on failure.
    Ties: Used by python -m mac_health_checkup.
    Inputs: None.
    Outputs: None. Exits with non zero on errors.
    Side effects: Runs the application.
    Why: Provides a standard module entrypoint for the package.
    """
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_run", "Application failed", exc)) from exc


if __name__ == "__main__":
    _run()
