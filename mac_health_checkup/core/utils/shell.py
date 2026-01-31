from __future__ import annotations

import random
import subprocess
import threading
import time
from dataclasses import dataclass
from shlex import quote
from typing import Sequence

from mac_health_checkup.core.config import RetryConfig, get_config
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/shell.py"


@dataclass(frozen=True)
class CommandResult:
    """
    Purpose: Represent a command execution result.
    Ties: Used by safe_run for structured output.
    Inputs: stdout, stderr, and returncode.
    Outputs: Immutable command result container.
    Side effects: None.
    Why: Keeps command results typed and explicit.
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
    Purpose: Run a command safely with retries, timeout, and clear errors.
    Ties: Used by diagnostics to access system commands safely.
    Inputs: cmd is the command list, context labels logs, allow_sudo toggles sudo fallback, timeout overrides config, cancel_event can abort.
    Outputs: Tuple of (stdout, error message). Error is None on success.
    Side effects: Executes a subprocess and may sleep for backoff.
    Why: Provides bounded, reliable command execution with clear errors.
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
    Purpose: Run system_profiler for a given data type.
    Ties: Used by diagnostics for system information.
    Inputs: data_type is the system_profiler data type, context labels logs, timeout overrides default.
    Outputs: Tuple of (stdout, error message).
    Side effects: Executes a subprocess.
    Why: Centralizes system_profiler invocation with safe defaults.
    """
    try:
        return safe_run(["system_profiler", data_type], context=context, allow_sudo=False, timeout=timeout)
    except (RuntimeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "system_profiler_out", "system_profiler failed", exc)
        ) from exc


def run_with_admin_prompt(
    cmd: Sequence[str],
    context: str,
    *,
    timeout: int | None = None,
) -> tuple[str | None, str | None]:
    """
    Summary
    Run a command via a macOS admin authorization prompt (AppleScript).

    Inputs
    cmd: Command list to execute.
    context: Context label used for error messages.
    timeout: Optional timeout override in seconds.

    Outputs
    Tuple of (stdout, error message). Error is None on success.

    Side effects
    May display a macOS admin password prompt and executes a subprocess.

    Error handling
    Raises RuntimeError on unexpected subprocess failures. Returns stderr text on normal command failures.

    Ties to other methods
    Used by diagnostics collectors when `sudo -n` timestamps are unreliable in background agents.

    Why this exists
    `sudo` timestamps are often tied to a TTY; the SwiftUI local agent runs without a TTY, so a proper system prompt is required.
    """
    try:
        if not cmd:
            return None, "empty command"
        timeout_sec = timeout if timeout is not None else get_config().timeouts.default_cmd_timeout
        marker = "__MHC_EXIT__="
        shell_cmd = " ".join(quote(str(part)) for part in cmd)
        wrapped = f"{shell_cmd} 2>&1; echo {quote(marker)}$?; exit 0"
        script = f'do shell script "{_escape_applescript_string(wrapped)}" with administrator privileges'
        result = _run_once(["/usr/bin/osascript", "-e", script], timeout_sec)
        if result.returncode == 0 and result.stdout is not None:
            stdout = result.stdout
            lines = stdout.splitlines()
            if lines and lines[-1].startswith(marker):
                try:
                    exit_code = int(lines[-1][len(marker) :].strip())
                except ValueError:
                    return stdout, None
                output = "\n".join(lines[:-1]).strip()
                if exit_code != 0:
                    return output, f"command_failed exit_code={exit_code}"
                return output, None
            return stdout, None
        err = result.stderr or f"admin prompt command failed with code {result.returncode}"
        return result.stdout, err
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "run_with_admin_prompt", f"Admin prompt failed: {context}", exc)
        ) from exc


def _escape_applescript_string(value: str) -> str:
    """
    Summary
    Escape a string for inclusion inside an AppleScript quoted string literal.

    Inputs
    value: Raw string.

    Outputs
    Escaped string safe for AppleScript.

    Side effects
    None.

    Error handling
    Raises RuntimeError when the input cannot be processed as a string.

    Ties to other methods
    Used by `run_with_admin_prompt`.

    Why this exists
    Prevents malformed AppleScript when commands contain quotes or backslashes.
    """
    try:
        return value.replace("\\", "\\\\").replace('"', '\\"')
    except (AttributeError, TypeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH, "_escape_applescript_string", "Failed to escape AppleScript string", exc
            )
        ) from exc


def _run_once(cmd: Sequence[str], timeout_sec: int) -> CommandResult:
    """
    Purpose: Run a command once with a timeout.
    Ties: Used by safe_run retry logic.
    Inputs: cmd is the command list, timeout_sec is timeout in seconds.
    Outputs: CommandResult with stdout, stderr, and returncode.
    Side effects: Executes a subprocess.
    Why: Encapsulates a single subprocess execution.
    """
    try:
        completed = subprocess.run(
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
    Purpose: Decide whether a sudo retry is appropriate.
    Ties: Used by safe_run after command failures.
    Inputs: cmd is the original command, result is the failed result.
    Outputs: True if sudo retry should be attempted.
    Side effects: None.
    Why: Prevents unnecessary sudo attempts.
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
    Purpose: Sleep for exponential backoff with jitter.
    Ties: Used by safe_run when retrying commands.
    Inputs: attempt is the retry attempt number, retry_conf is a RetryConfig instance.
    Outputs: None.
    Side effects: Sleeps for a computed duration.
    Why: Prevents hammering system commands while retrying.
    """
    try:
        if retry_conf.max_attempts <= 0:
            return
        exponent = attempt - 1
        delay = min(retry_conf.base_delay_ms * (retry_conf.backoff_factor**exponent), retry_conf.max_delay_ms)
        jitter = random.uniform(0, retry_conf.jitter_ms)
        time.sleep((delay + jitter) / 1000.0)
    except (AttributeError, TypeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_sleep_backoff", "Failed to compute backoff", exc)
        ) from exc
