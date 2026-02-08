from __future__ import annotations

import subprocess
import threading
import unittest
from unittest.mock import patch

from mac_health_checkup.core.utils.shell import _run_once, _should_retry_with_sudo, _sleep_backoff, safe_run

MODULE_PATH = "tests/test_shell_safe_run_unit.py"


class ShellSafeRunUnitTests(unittest.TestCase):
    """
    Summary
    Validate safe command execution helpers behave deterministically under mocks.

    Inputs
    None.

    Outputs
    Assertions on stdout/error behavior and retry gates.

    Side effects
    Patches subprocess and sleep functions to avoid real process execution.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `mac_health_checkup/core/utils/shell.py` helpers.

    Why this exists
    IO-heavy collectors depend on safe_run for time bounds and clear failures; testing it directly keeps regressions visible.
    """

    def test_run_once_strips_stdout_and_stderr(self) -> None:
        """
        Summary
        Ensure `_run_once` returns stripped stdout/stderr without raising on success.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches subprocess.run.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_run_once`.

        Why this exists
        Most parsers expect trimmed outputs; normalization should happen at the IO boundary.
        """
        try:
            cp = subprocess.CompletedProcess(
                args=["echo", "x"], returncode=0, stdout=" hi \n", stderr=" err \n"
            )
            with patch("mac_health_checkup.core.utils.shell.subprocess.run", autospec=True, return_value=cp):
                result = _run_once(["echo", "x"], timeout_sec=1)
                self.assertEqual(result.stdout, "hi")
                self.assertEqual(result.stderr, "err")
                self.assertEqual(result.returncode, 0)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShellSafeRunUnitTests.test_run_once_strips_stdout_and_stderr failed: {exc}"
            ) from exc

    def test_run_once_handles_timeout_and_not_found(self) -> None:
        """
        Summary
        Ensure `_run_once` converts common subprocess failures into deterministic return codes and errors.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches subprocess.run.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_run_once` exception paths.

        Why this exists
        Collectors should not crash on missing tools; errors must be captured into diagnostics.
        """
        try:
            with patch(
                "mac_health_checkup.core.utils.shell.subprocess.run",
                autospec=True,
                side_effect=subprocess.TimeoutExpired(cmd=["x"], timeout=1),
            ):
                result = _run_once(["x"], timeout_sec=1)
                self.assertEqual(result.returncode, 124)
                self.assertIn("timeout", str(result.stderr))

            with patch(
                "mac_health_checkup.core.utils.shell.subprocess.run",
                autospec=True,
                side_effect=FileNotFoundError("missing"),
            ):
                result2 = _run_once(["missing"], timeout_sec=1)
                self.assertEqual(result2.returncode, 127)
                self.assertIn("not found", str(result2.stderr))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShellSafeRunUnitTests.test_run_once_handles_timeout_and_not_found failed: {exc}"
            ) from exc

    def test_should_retry_with_sudo_detects_permission_hints(self) -> None:
        """
        Summary
        Ensure sudo retry heuristics only trigger on permission-like failures.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_should_retry_with_sudo`.

        Why this exists
        The tool must not spam sudo attempts for unrelated failures.
        """
        try:
            from mac_health_checkup.core.utils.shell import CommandResult

            self.assertFalse(
                _should_retry_with_sudo([], CommandResult(stdout=None, stderr="x", returncode=1))
            )
            self.assertFalse(
                _should_retry_with_sudo(
                    ["sudo", "x"], CommandResult(stdout=None, stderr="permission", returncode=1)
                )
            )
            self.assertTrue(
                _should_retry_with_sudo(
                    ["x"], CommandResult(stdout=None, stderr="Operation not permitted", returncode=1)
                )
            )
            self.assertFalse(
                _should_retry_with_sudo(
                    ["x"], CommandResult(stdout=None, stderr="no such file", returncode=1)
                )
            )
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShellSafeRunUnitTests.test_should_retry_with_sudo_detects_permission_hints failed: {exc}"
            ) from exc

    def test_safe_run_retries_and_sudo_fallback(self) -> None:
        """
        Summary
        Ensure safe_run retries and optionally attempts sudo when configured.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches `_run_once` and backoff sleep to avoid real subprocesses and delays.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `safe_run` retry and sudo paths.

        Why this exists
        Retrying and sudo fallback are primary resilience mechanisms for collectors.
        """
        try:
            from mac_health_checkup.core.utils.shell import CommandResult

            calls: list[list[str]] = []

            def _fake_run_once(cmd: list[str], _timeout: int) -> CommandResult:
                calls.append(list(cmd))
                if cmd[:2] == ["sudo", "-n"]:
                    return CommandResult(stdout="ok", stderr=None, returncode=0)
                return CommandResult(stdout=None, stderr="operation not permitted", returncode=1)

            with patch(
                "mac_health_checkup.core.utils.shell._run_once", autospec=True, side_effect=_fake_run_once
            ):
                with patch(
                    "mac_health_checkup.core.utils.shell._sleep_backoff", autospec=True, return_value=None
                ):
                    out, err = safe_run(["x"], context="t", allow_sudo=True, timeout=1)
                    self.assertEqual(out, "ok")
                    self.assertIsNone(err)
                    self.assertGreaterEqual(len(calls), 2)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShellSafeRunUnitTests.test_safe_run_retries_and_sudo_fallback failed: {exc}"
            ) from exc

    def test_safe_run_honors_cancel_event(self) -> None:
        """
        Summary
        Ensure cancel_event causes safe_run to return early without executing commands.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises safe_run cancellation gate.

        Why this exists
        UI refresh loops should be able to cancel long-running work during shutdown.
        """
        try:
            cancel = threading.Event()
            cancel.set()
            out, err = safe_run(["x"], context="t", allow_sudo=False, timeout=1, cancel_event=cancel)
            self.assertIsNone(out)
            self.assertEqual(err, "cancelled")
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShellSafeRunUnitTests.test_safe_run_honors_cancel_event failed: {exc}"
            ) from exc

    def test_sleep_backoff_uses_delay_and_jitter(self) -> None:
        """
        Summary
        Ensure sleep backoff computes a bounded delay and calls time.sleep with seconds.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches random.uniform and time.sleep.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_sleep_backoff`.

        Why this exists
        Backoff should be bounded and deterministic under mocks to avoid slowing tests.
        """
        try:
            from mac_health_checkup.core.config.models.runtime import RetryConfig

            retry = RetryConfig(
                enabled=True,
                max_attempts=3,
                base_delay_ms=100,
                max_delay_ms=1000,
                backoff_factor=2.0,
                jitter_ms=50,
            )
            with patch(
                "mac_health_checkup.core.utils.shell.random.uniform", autospec=True, return_value=10.0
            ):
                with patch("mac_health_checkup.core.utils.shell.time.sleep", autospec=True) as sleep_mock:
                    _sleep_backoff(2, retry)
                    assert sleep_mock.call_count == 1
                    seconds = float(sleep_mock.call_args[0][0])
                    self.assertGreater(seconds, 0.0)
                    self.assertLess(seconds, 2.0)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShellSafeRunUnitTests.test_sleep_backoff_uses_delay_and_jitter failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
