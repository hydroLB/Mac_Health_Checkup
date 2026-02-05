from __future__ import annotations

import signal
import threading
from dataclasses import dataclass, field
from types import FrameType
from typing import Callable

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/lifecycle.py"


@dataclass
class ShutdownManager:
    """
    Purpose: Coordinate graceful shutdown for the application.
    Ties: Used by entrypoints to ensure cleanup on signals.
    Inputs: None. Uses config for timeouts.
    Outputs: None. Manages shutdown state.
    Side effects: Installs signal handlers and runs cleanup callbacks.
    Why: Ensures resources are cleaned up and work is not lost on exit.
    """

    _shutdown_event: threading.Event = field(default_factory=threading.Event)
    _callbacks: list[Callable[[], None]] = field(default_factory=list)

    def install_handlers(self) -> None:
        """
        Purpose: Install SIGINT and SIGTERM handlers for graceful shutdown.
        Ties: Used by entrypoints at startup.
        Inputs: None.
        Outputs: None.
        Side effects: Registers signal handlers.
        Why: Ensures the app shuts down cleanly on termination signals.
        """
        try:
            signal.signal(signal.SIGINT, self._handle_signal)
            signal.signal(signal.SIGTERM, self._handle_signal)
        except (ValueError, RuntimeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "ShutdownManager.install_handlers", "Failed to install handlers", exc
                )
            ) from exc

    def register_cleanup(self, callback: Callable[[], None]) -> None:
        """
        Purpose: Register a cleanup callback to run on shutdown.
        Ties: Used by components that need cleanup steps.
        Inputs: callback is a no arg callable.
        Outputs: None.
        Side effects: Adds a callback to the internal list.
        Why: Centralizes cleanup execution on shutdown.
        """
        try:
            self._callbacks.append(callback)
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "ShutdownManager.register_cleanup", "Failed to register cleanup", exc
                )
            ) from exc

    def wait_for_shutdown(self) -> None:
        """
        Purpose: Block until a shutdown signal is received.
        Ties: Used by entrypoints to keep the app running.
        Inputs: None.
        Outputs: None.
        Side effects: Blocks on shutdown event.
        Why: Provides a clean waiting loop with an exit path.
        """
        try:
            self._shutdown_event.wait()
        except RuntimeError as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ShutdownManager.wait_for_shutdown", "Failed while waiting", exc)
            ) from exc

    def shutdown_requested(self) -> bool:
        """
        Purpose: Return whether shutdown has been requested.
        Ties: Used by UI refresh loops and server entrypoints to avoid scheduling new work during teardown.
        Inputs: None.
        Outputs: True when shutdown was triggered, else false.
        Side effects: None.
        Why: Provides a safe public check for shutdown state without exposing internal event fields.
        """
        try:
            return bool(self._shutdown_event.is_set())
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "ShutdownManager.shutdown_requested",
                    "Failed to query shutdown state",
                    exc,
                )
            ) from exc

    def trigger_shutdown(self) -> None:
        """
        Purpose: Trigger shutdown and run cleanup callbacks.
        Ties: Used internally by signal handlers.
        Inputs: None.
        Outputs: None.
        Side effects: Runs cleanup callbacks and sets shutdown event.
        Why: Ensures cleanup runs before exit.
        """
        try:
            if self._shutdown_event.is_set():
                return
            self._shutdown_event.set()
            self._run_cleanup()
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ShutdownManager.trigger_shutdown", "Failed to shutdown", exc)
            ) from exc

    def _run_cleanup(self) -> None:
        """
        Purpose: Run registered cleanup callbacks with time bounds.
        Ties: Used by trigger_shutdown.
        Inputs: None.
        Outputs: None.
        Side effects: Executes cleanup callbacks.
        Why: Ensures cleanup completes within a bounded time.
        """
        try:
            timeout = get_config().shutdown.graceful_timeout_sec
            deadline = threading.Event()
            timer = threading.Timer(timeout, deadline.set)
            timer.start()
            try:
                for callback in self._callbacks:
                    if deadline.is_set():
                        break
                    callback()
            finally:
                timer.cancel()
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ShutdownManager._run_cleanup", "Cleanup failed", exc)
            ) from exc

    def _handle_signal(self, _signum: int, _frame: FrameType | None) -> None:
        """
        Purpose: Handle OS signals by triggering shutdown.
        Ties: Registered by install_handlers.
        Inputs: signal number and optional frame are provided by signal module.
        Outputs: None.
        Side effects: Triggers shutdown.
        Why: Ensures graceful shutdown on SIGINT and SIGTERM.
        """
        try:
            self.trigger_shutdown()
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ShutdownManager._handle_signal", "Signal handling failed", exc)
            ) from exc
