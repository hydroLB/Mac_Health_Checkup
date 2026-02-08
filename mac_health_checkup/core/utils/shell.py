from __future__ import annotations

import random
import subprocess  # nosec B404
import threading
import time
from dataclasses import dataclass
from typing import Sequence

from mac_health_checkup.core.config import RetryConfig, get_config
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/shell.py"
_JITTER_RNG = random.SystemRandom()


@dataclass(frozen=True)
class CommandResult:
    """
    Summary
    Represent a command execution result.

    Inputs
    stdout: Optional stdout text.
    stderr: Optional stderr text.
    returncode: Subprocess return code.

    Outputs
    Immutable command result container.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `_run_once` and consumed by `safe_run`.

    Why this exists
    Keeps command results typed and explicit.
    """

    stdout: str | None
    stderr: str | None
    returncode: int


def safe_run(
    cmd: Sequence[str],
    context: str,
    *,
    allow_sudo: bool,
    timeout: int | None = None,
    cancel_event: threading.Event | None = None,
) -> tuple[str | None, str | None]:
    """
    Summary
    Run a command safely with retries, timeout, and clear errors.

    Inputs
    cmd: Command argv list.
    context: Label used in error messages for troubleshooting.
    allow_sudo: Whether a sudo retry is permitted for permission-like failures.
    timeout: Optional timeout override in seconds.
    cancel_event: Optional cancellation event for aborting retries.

    Outputs
    Tuple of (stdout, error message). Error is None on success.

    Side effects
    Executes a subprocess and may sleep for backoff.

    Error handling
    Returns a non-empty error string on command failure. Raises `RuntimeError` with module and method context on
    subprocess invocation failures.

    Ties to other methods
    Uses `_run_once`, `_should_retry_with_sudo`, and `_sleep_backoff`.

    Why this exists
    Provides bounded, reliable command execution with clear errors.
    """
    try:
        cfg = get_config()
        timeout_sec = timeout if timeout is not None else cfg.timeouts.default_cmd_timeout
        retry_conf = cfg.retries
        attempts = retry_conf.max_attempts if retry_conf.enabled else 1
        for attempt in range(1, attempts + 1):
            if cancel_event is not None and cancel_event.is_set():
                return None, "cancelled"
            result = _run_once(cmd, timeout_sec)
            if result.returncode == 0 and result.stdout is not None:
                return result.stdout, None
            err = result.stderr or f"command failed with code {result.returncode}"
            if allow_sudo and _should_retry_with_sudo(cmd, result):
                sudo_cmd = ["sudo", "-n", *cmd]
                sudo_result = _run_once(sudo_cmd, timeout_sec)
                if sudo_result.returncode == 0 and sudo_result.stdout is not None:
                    return sudo_result.stdout, None
                err = sudo_result.stderr or f"sudo failed with code {sudo_result.returncode}"
            if attempt < attempts:
                _sleep_backoff(attempt, retry_conf)
                continue
            return result.stdout, err
        return None, "command did not run"
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "safe_run", f"Command failed: {context}", exc)) from exc


def system_profiler_out(
    data_type: str, context: str, timeout: int | None = None
) -> tuple[str | None, str | None]:
    """
    Summary
    Run system_profiler for a given data type.

    Inputs
    data_type: system_profiler data type.
    context: Error context label.
    timeout: Optional timeout override in seconds.

    Outputs
    Tuple of (stdout, error message).

    Side effects
    Executes a subprocess.

    Error handling
    Raises `RuntimeError` with module and method context when invocation fails unexpectedly.

    Ties to other methods
    Thin wrapper around `safe_run`.

    Why this exists
    Centralizes system_profiler invocation with safe defaults.
    """
    try:
        return safe_run(["system_profiler", data_type], context=context, allow_sudo=False, timeout=timeout)
    except (RuntimeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "system_profiler_out", "system_profiler failed", exc)
        ) from exc


def _run_once(cmd: Sequence[str], timeout_sec: int) -> CommandResult:
    """
    Summary
    Run a command once with a timeout.

    Inputs
    cmd: Command argv list.
    timeout_sec: Timeout in seconds.

    Outputs
    `CommandResult` with stdout, stderr, and returncode.

    Side effects
    Executes a subprocess.

    Error handling
    Never raises; converts common subprocess exceptions into a `CommandResult` with a non-zero return code.

    Ties to other methods
    Used by `safe_run` retry logic.

    Why this exists
    Encapsulates a single subprocess execution.
    """
    try:
        completed = subprocess.run(  # nosec B603
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        stdout = completed.stdout.strip() if completed.stdout is not None else None
        stderr = completed.stderr.strip() if completed.stderr is not None else None
        return CommandResult(stdout=stdout, stderr=stderr, returncode=completed.returncode)
    except subprocess.TimeoutExpired:
        return CommandResult(stdout=None, stderr=f"timeout after {timeout_sec}s", returncode=124)
    except FileNotFoundError as exc:
        return CommandResult(stdout=None, stderr=f"not found: {exc}", returncode=127)
    except PermissionError as exc:
        return CommandResult(stdout=None, stderr=f"not permitted: {exc}", returncode=126)
    except subprocess.SubprocessError as exc:
        return CommandResult(stdout=None, stderr=f"subprocess error: {exc}", returncode=126)


def _should_retry_with_sudo(cmd: Sequence[str], result: CommandResult) -> bool:
    """
    Summary
    Decide whether a sudo retry is appropriate.

    Inputs
    cmd: Original command argv list.
    result: Failed command result.

    Outputs
    True when a sudo retry should be attempted.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when inspection fails unexpectedly.

    Ties to other methods
    Used by `safe_run` after command failures.

    Why this exists
    Prevents unnecessary sudo attempts.
    """
    try:
        if not cmd:
            return False
        if cmd[0] == "sudo":
            return False
        err = (result.stderr or "").lower()
        sudo_hints = (
            "permission",
            "not permitted",
            "operation not permitted",
            "must be invoked as the superuser",
            "must be run as root",
            "superuser",
            "root required",
            "requires root",
            "administrator privileges",
            "ioserviceopen",
            "e00002e2",
        )
        return any(hint in err for hint in sudo_hints)
    except (AttributeError, TypeError, IndexError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_should_retry_with_sudo", "Failed to check sudo retry", exc)
        ) from exc


def _sleep_backoff(attempt: int, retry_conf: RetryConfig) -> None:
    """
    Summary
    Sleep for exponential backoff with jitter.

    Inputs
    attempt: Retry attempt number (1-indexed).
    retry_conf: RetryConfig instance.

    Outputs
    None.

    Side effects
    Sleeps for a computed duration.

    Error handling
    Raises `RuntimeError` with module and method context when backoff computation fails unexpectedly.

    Ties to other methods
    Used by `safe_run` when retrying commands.

    Why this exists
    Prevents hammering system commands while retrying.
    """
    try:
        if retry_conf.max_attempts <= 0:
            return
        exponent = attempt - 1
        delay = min(retry_conf.base_delay_ms * (retry_conf.backoff_factor**exponent), retry_conf.max_delay_ms)
        jitter = _JITTER_RNG.uniform(0, retry_conf.jitter_ms)
        time.sleep((delay + jitter) / 1000.0)
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_sleep_backoff", "Failed to compute backoff", exc)
        ) from exc
