from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from shutil import rmtree, which
from typing import Iterable, Sequence, cast

from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils.error_boundary import ErrorBoundary, map_boundary_exception

MODULE_PATH = "run_mac_health_checkup_ui.py"


def _parse_args() -> argparse.Namespace:
    """
    Summary
    Parse CLI arguments for the one-click SwiftUI launcher.

    Inputs
    None.

    Outputs
    Parsed `argparse.Namespace`.

    Side effects
    Reads process argv.

    Error handling
    Raises `RuntimeError` with a location-tagged message if parsing fails.

    Ties to other methods
    Called by `main` to support `--help` without launching the SwiftUI app.

    Why this exists
    Users should be able to run `python3 run_mac_health_checkup_ui.py --help` safely without triggering builds.
    """
    try:
        parser = argparse.ArgumentParser(description="Launch the native macOS SwiftUI UI (one-click).")
        # Preserve existing behavior of ignoring unknown flags while still supporting `--help`.
        return parser.parse_known_args()[0]
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_parse_args", "Failed to parse args", exc)) from exc


def _should_clean_swiftpm_cache(combined_output: str) -> bool:
    """
    Summary
    Decide whether a SwiftPM build/run failure looks like a stale module cache that can be fixed by cleaning.

    Inputs
    combined_output: The combined stdout/stderr text from a failed `make swift-run` invocation.

    Outputs
    True if the failure matches known stale-cache signatures; otherwise False.

    Side effects
    None.

    Error handling
    Raises RuntimeError with a location-tagged message if inputs are invalid.

    Ties to other methods
    Used by `_run_make_swift_run_with_retry` to decide whether to remove `.local/swiftpm` and retry once.

    Why this exists
    SwiftPM caches can embed absolute paths; moving the repo makes builds fail with "PCH was compiled with module
    cache path ..." and "missing required module 'SwiftShims'". Auto-healing keeps the one-command runner reliable.
    """
    try:
        if not isinstance(combined_output, str):
            raise TypeError(f"combined_output must be str, got {type(combined_output).__name__}")

        # These signatures are stable across SwiftPM versions and are strongly correlated with stale caches.
        triggers = (
            "PCH was compiled with module cache path",
            "missing required module 'SwiftShims'",
            "Invalid manifest",
        )
        return any(t in combined_output for t in triggers)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_should_clean_swiftpm_cache",
                "Failed to decide whether to clean SwiftPM cache",
                exc,
            )
        ) from exc


def _stream_command(
    argv: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
) -> tuple[int, str]:
    """
    Summary
    Run a subprocess while streaming its output to the caller's stdout, and also capture the combined output.

    Inputs
    argv: Command argv to execute.
    cwd: Working directory for the subprocess.
    env: Environment variables for the subprocess.

    Outputs
    Tuple of (exit_code, combined_output).

    Side effects
    Starts a child process and writes its output to stdout.

    Error handling
    Raises RuntimeError with a location-tagged message when process creation fails.

    Ties to other methods
    Used by `_run_make_swift_run_with_retry` to capture error text without hiding build progress.

    Why this exists
    Swift builds can take time; streaming output keeps the user informed while still allowing error inspection for
    auto-retry decisions.
    """
    try:
        proc = subprocess.Popen(
            list(argv),
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except (OSError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_stream_command", f"Failed to start process: {argv!r}", exc)
        ) from exc

    try:
        captured: list[str] = []
        assert proc.stdout is not None  # stdout is PIPE by construction.
        for line in cast(Iterable[str], proc.stdout):
            sys.stdout.write(line)
            sys.stdout.flush()
            captured.append(line)
        return int(proc.wait()), "".join(captured)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_stream_command", "Failed while streaming process output", exc)
        ) from exc


def _run_make_swift_run_with_retry(*, repo_root: Path, env: dict[str, str]) -> int:
    """
    Summary
    Invoke `make swift-run` and, on known SwiftPM stale-cache failures, clean `.local/swiftpm` and retry once.

    Inputs
    repo_root: Repository root directory.
    env: Environment variables to pass to `make`.

    Outputs
    Process exit code from the final `make swift-run` attempt.

    Side effects
    Builds Swift targets; may delete `.local/swiftpm` to clear stale caches; launches the SwiftUI app on success.

    Error handling
    Raises RuntimeError with a location-tagged message when cleanup fails unexpectedly.

    Ties to other methods
    Called by `main` after it prepares `SWIFT_APP_ARGS`.

    Why this exists
    Moving the repo between folders can poison SwiftPM module caches with embedded absolute paths. Retrying after
    cleaning keeps the "one command" UX reliable without requiring manual cache surgery.
    """
    try:
        exit_code, output = _stream_command(["make", "swift-run"], cwd=repo_root, env=env)
        if exit_code == 0:
            return 0

        if not _should_clean_swiftpm_cache(output):
            return int(exit_code)

        swiftpm_cache_dir = repo_root / ".local" / "swiftpm"
        if swiftpm_cache_dir.exists():
            # Local build cache only; safe to remove to recover from path-embedded artifacts.
            rmtree(swiftpm_cache_dir)

        sys.stdout.write(
            "\n[mac-health-checkup] Detected stale SwiftPM cache. Cleaned .local/swiftpm and retrying once.\n"
        )
        sys.stdout.flush()
        exit_code2, _ = _stream_command(["make", "swift-run"], cwd=repo_root, env=env)
        return int(exit_code2)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_run_make_swift_run_with_retry", "Failed to run SwiftUI app", exc)
        ) from exc


def _emit_boundary_error(method: str, message: str, exc: Exception) -> None:
    """
    Summary
    Write a formatted boundary error for the SwiftUI one-click launcher.

    Inputs
    method: Boundary method name associated with the failure.
    message: High-level failure context.
    exc: Captured exception instance.

    Outputs
    None.

    Side effects
    Writes one line to stderr.

    Error handling
    Raises contextual errors from `run_mac_health_checkup_ui.py:_emit_boundary_error` when output formatting fails unexpectedly.

    Ties to other methods
    Used by `main` to emit final script-boundary failures.

    Why this exists
    Boundary failures should be actionable and clean without exposing stack traces for routine environment issues.
    """
    try:
        mapped = map_boundary_exception(exc, boundary=ErrorBoundary.UI, default_message=message)
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
    Launch the native macOS SwiftUI UI without opening Xcode.

    Inputs
    None.

    Outputs
    Process exit code from the underlying `make swift-run` invocation.

    Side effects
    Builds Swift targets and launches the macOS SwiftUI dashboard process.

    Error handling
    Returns exit code `2` after emitting a formatted boundary error for runtime failures. `argparse` can still raise
    `SystemExit` for `--help`.

    Ties to other methods
    Sets `SWIFT_APP_ARGS` for the Makefile target and delegates execution to `_run_make_swift_run_with_retry`.

    Why this exists
    Keeps "press Run" ergonomics while ensuring the SwiftUI app always receives the correct repo root and config path.
    """
    try:
        _parse_args()
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

        return int(_run_make_swift_run_with_retry(repo_root=repo_root, env=env))
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        _emit_boundary_error("main", "Failed to launch macOS UI", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
