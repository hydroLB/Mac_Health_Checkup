from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from shutil import which

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "run_mac_health_checkup_ui.py"


def main() -> int:
    """
    Purpose: Provide a single-file entrypoint to launch the native macOS SwiftUI UI without opening Xcode.
    Ties: Invokes `make swift-run`, which builds and runs the Swift package executable `mac-health-checkup-ui`.
    Inputs: None.
    Outputs: Process exit code from `make`.
    Side effects: Builds Swift targets and launches the macOS SwiftUI dashboard process.
    Why: Makes "press Run" in VS Code or any IDE start the UI with a predictable config and repo root.
    """
    try:
        repo_root = Path(__file__).resolve().parent
        config_path = repo_root / "config" / "config.json"
        if not config_path.is_file():
            raise ValueError(f"Missing config file: {config_path}")

        if which("make") is None:
            raise RuntimeError(
                "`make` not found. Install Xcode Command Line Tools or a compatible build toolchain."
            )
        if which("swift") is None:
            raise RuntimeError(
                "`swift` not found. Install Xcode Command Line Tools (xcode-select --install) to build the SwiftUI app."
            )

        env = dict(os.environ)
        if "SWIFT_APP_ARGS" not in env:
            repo_arg = shlex.quote(str(repo_root))
            config_arg = shlex.quote(str(config_path))
            env["SWIFT_APP_ARGS"] = f"--repo-root {repo_arg} --config {config_arg}"

        result = subprocess.run(["make", "swift-run"], cwd=str(repo_root), env=env, check=False)
        return int(result.returncode)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "main", "Failed to launch macOS UI", exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
