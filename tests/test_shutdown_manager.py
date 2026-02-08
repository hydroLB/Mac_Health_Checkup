from __future__ import annotations

import unittest
from dataclasses import replace
from typing import Callable
from unittest.mock import patch

from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.core.config import get_config

MODULE_PATH = "tests/test_shutdown_manager.py"


class ShutdownManagerTests(unittest.TestCase):
    """
    Summary
    Validate graceful shutdown coordination logic without installing real signal handlers.

    Inputs
    None.

    Outputs
    Assertions on shutdown state and callback execution.

    Side effects
    Patches signal and timer behavior to avoid interacting with the process signal table.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `mac_health_checkup/app/gui/dashboard/lifecycle.py`.

    Why this exists
    Shutdown handling is a boundary concern for CLI, UI, and server modes; regressions can cause hangs or leaked threads.
    """

    def test_install_handlers_registers_sigint_and_sigterm(self) -> None:
        """
        Summary
        Ensure install_handlers registers SIGINT and SIGTERM handlers.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches signal.signal.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `ShutdownManager.install_handlers`.

        Why this exists
        The entrypoint depends on predictable handler installation.
        """
        try:
            calls: list[int] = []

            def _fake_signal(sig: int, _handler: object) -> None:
                calls.append(int(sig))

            with patch(
                "mac_health_checkup.app.gui.dashboard.lifecycle.signal.signal",
                autospec=True,
                side_effect=_fake_signal,
            ):
                mgr = ShutdownManager()
                mgr.install_handlers()
            self.assertGreaterEqual(len(calls), 2)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShutdownManagerTests.test_install_handlers_registers_sigint_and_sigterm failed: {exc}"
            ) from exc

    def test_trigger_shutdown_runs_cleanup_once(self) -> None:
        """
        Summary
        Ensure trigger_shutdown runs registered callbacks once and sets shutdown state.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Executes test callbacks.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `register_cleanup`, `trigger_shutdown`, and `shutdown_requested`.

        Why this exists
        Double-running cleanup can cause errors (closing resources twice). The manager should be idempotent.
        """
        try:
            mgr = ShutdownManager()
            calls: list[str] = []
            mgr.register_cleanup(lambda: calls.append("a"))
            mgr.register_cleanup(lambda: calls.append("b"))

            with patch(
                "mac_health_checkup.app.gui.dashboard.lifecycle.threading.Timer", autospec=True
            ) as timer_mock:
                timer_mock.return_value.start.return_value = None
                timer_mock.return_value.cancel.return_value = None
                mgr.trigger_shutdown()
                mgr.trigger_shutdown()

            self.assertTrue(mgr.shutdown_requested())
            self.assertEqual(calls, ["a", "b"])
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShutdownManagerTests.test_trigger_shutdown_runs_cleanup_once failed: {exc}"
            ) from exc

    def test_cleanup_is_time_bounded(self) -> None:
        """
        Summary
        Ensure cleanup loop stops when the deadline event is set.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches threading.Timer to set deadline immediately.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `ShutdownManager._run_cleanup`.

        Why this exists
        Cleanup must not hang forever during shutdown.
        """
        try:
            mgr = ShutdownManager()
            calls: list[str] = []
            mgr.register_cleanup(lambda: calls.append("a"))
            mgr.register_cleanup(lambda: calls.append("b"))

            class _ImmediateTimer:
                def __init__(self, _timeout: float, fn: Callable[[], None]) -> None:
                    self._fn = fn

                def start(self) -> None:
                    self._fn()

                def cancel(self) -> None:
                    return

            cfg = get_config()
            cfg_fast = replace(cfg, shutdown=replace(cfg.shutdown, graceful_timeout_sec=0))

            with patch(
                "mac_health_checkup.app.gui.dashboard.lifecycle.get_config",
                autospec=True,
                return_value=cfg_fast,
            ):
                with patch(
                    "mac_health_checkup.app.gui.dashboard.lifecycle.threading.Timer",
                    autospec=True,
                    side_effect=_ImmediateTimer,
                ):
                    mgr.trigger_shutdown()

            self.assertEqual(calls, [])
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShutdownManagerTests.test_cleanup_is_time_bounded failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
