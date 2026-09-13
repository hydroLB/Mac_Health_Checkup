from __future__ import annotations

import threading
import time
import unittest
from dataclasses import replace
from types import SimpleNamespace
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
                """
                Summary
                Execute `_fake_signal` for its module-level responsibility.

                Inputs
                sig: `int` parameter from the function signature.
                _handler: `object` parameter from the function signature.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_shutdown_manager.py:_fake_signal` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_shutdown_manager.py`.

                Why this exists
                Keeps `_fake_signal` explicit, testable, and maintainable.
                """
                calls.append(int(sig))

            with patch(
                "mac_health_checkup.app.gui.dashboard.lifecycle.signal.signal",
                autospec=True,
                side_effect=_fake_signal,
            ):
                mgr = ShutdownManager()
                mgr.install_handlers()
            self.assertGreaterEqual(len(calls), 2)
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
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
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
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
                    """
                    Summary
                    Execute `__init__` for its module-level responsibility.

                    Inputs
                    _timeout: `float` parameter from the function signature.
                    fn: `Callable[[], None]` parameter from the function signature.

                    Outputs
                    None.

                    Side effects
                    None beyond this method boundary.

                    Error handling
                    Raises contextual errors from `tests/test_shutdown_manager.py:__init__` when this method encounters invalid state or runtime failures.

                    Ties to other methods
                    Used by workflows in `tests/test_shutdown_manager.py`.

                    Why this exists
                    Keeps `__init__` explicit, testable, and maintainable.
                    """
                    self._fn = fn

                def start(self) -> None:
                    """
                    Summary
                    Execute `start` for its module-level responsibility.

                    Inputs
                    None.

                    Outputs
                    None.

                    Side effects
                    None beyond this method boundary.

                    Error handling
                    Raises contextual errors from `tests/test_shutdown_manager.py:start` when this method encounters invalid state or runtime failures.

                    Ties to other methods
                    Used by workflows in `tests/test_shutdown_manager.py`.

                    Why this exists
                    Keeps `start` explicit, testable, and maintainable.
                    """
                    self._fn()

                def cancel(self) -> None:
                    """
                    Summary
                    Execute `cancel` for its module-level responsibility.

                    Inputs
                    None.

                    Outputs
                    None.

                    Side effects
                    None beyond this method boundary.

                    Error handling
                    Raises contextual errors from `tests/test_shutdown_manager.py:cancel` when this method encounters invalid state or runtime failures.

                    Ties to other methods
                    Used by workflows in `tests/test_shutdown_manager.py`.

                    Why this exists
                    Keeps `cancel` explicit, testable, and maintainable.
                    """
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
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ShutdownManagerTests.test_cleanup_is_time_bounded failed: {exc}"
            ) from exc

    def test_blocking_cleanup_callback_cannot_exceed_deadline(self) -> None:
        """
        Summary
        Ensure a callback that never completes cannot block shutdown past the configured deadline.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Starts one daemon cleanup thread that is released before the test exits.

        Error handling
        Raises `AssertionError` when shutdown waits materially beyond the configured bound.

        Ties to other methods
        Exercises the real blocking-callback path in `ShutdownManager._run_cleanup`.

        Why this exists
        A timer flag checked only between callbacks does not bound a callback that hangs internally.
        """
        release = threading.Event()
        manager = ShutdownManager()

        def _blocking_cleanup() -> None:
            """
            Summary
            Wait until the test releases the injected cleanup callback.

            Inputs
            None.

            Outputs
            None.

            Side effects
            Blocks the daemon cleanup thread on an event.

            Error handling
            None.

            Ties to other methods
            Registered with `ShutdownManager` in this test.

            Why this exists
            `threading.Event.wait` returns a boolean and does not directly satisfy the cleanup callback contract.
            """
            release.wait()

        manager.register_cleanup(_blocking_cleanup)
        started_at = time.monotonic()
        try:
            with patch(
                "mac_health_checkup.app.gui.dashboard.lifecycle.get_config",
                return_value=SimpleNamespace(
                    shutdown=SimpleNamespace(graceful_timeout_sec=0.05),
                ),
            ):
                manager.trigger_shutdown()
            self.assertLess(time.monotonic() - started_at, 0.5)
        finally:
            release.set()


if __name__ == "__main__":
    unittest.main()
