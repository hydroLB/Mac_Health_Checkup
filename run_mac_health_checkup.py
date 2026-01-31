from __future__ import annotations

from pathlib import Path

from mac_health_checkup.app.backend.one_click import run_one_click_agent

MODULE_PATH = "run_mac_health_checkup.py"


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
        repo_root = Path(__file__).resolve().parent
        return run_one_click_agent(repo_root=repo_root)
    except Exception as exc:
        raise RuntimeError(f"{MODULE_PATH}:main failed: {exc}") from exc


if __name__ == "__main__":
    raise SystemExit(main())
