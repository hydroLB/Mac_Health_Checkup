from __future__ import annotations

import signal
import threading
import time
from dataclasses import dataclass, field
from types import FrameType
from typing import Callable

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/lifecycle.py"


@dataclass
class ShutdownManager:
    """
    Summary
    Coordinate graceful shutdown for the application.

    Inputs
    None. Uses config for timeouts.

    Outputs
    None. Manages shutdown state.

    Side effects
    Installs signal handlers and runs cleanup callbacks.

    Error handling
    Methods raise `RuntimeError` with module and method context when shutdown coordination fails unexpectedly.

    Ties to other methods
    Used by entrypoints to ensure cleanup on signals.

    Why this exists
    Ensures resources are cleaned up and work is not lost on exit.
    """

    _shutdown_event: threading.Event = field(default_factory=threading.Event)
    _callbacks: list[Callable[[], None]] = field(default_factory=list)

    def install_handlers(self) -> None:
        """
        Summary
        Install SIGINT and SIGTERM handlers for graceful shutdown.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Registers signal handlers.

        Error handling
        Raises `RuntimeError` with module and method context when handler installation fails.

        Ties to other methods
        Used by entrypoints at startup.

        Why this exists
        Ensures the app shuts down cleanly on termination signals.
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
        Summary
        Register a cleanup callback to run on shutdown.

        Inputs
        callback: No-arg callable.

        Outputs
        None.

        Side effects
        Adds a callback to the internal list.

        Error handling
        Raises `RuntimeError` with module and method context when registration fails unexpectedly.

        Ties to other methods
        Used by components that need cleanup steps.

        Why this exists
        Centralizes cleanup execution on shutdown.
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
        Summary
        Block until a shutdown signal is received.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Blocks on shutdown event.

        Error handling
        Raises `RuntimeError` with module and method context when waiting fails unexpectedly.

        Ties to other methods
        Used by entrypoints to keep the app running.

        Why this exists
        Provides a clean waiting loop with an exit path.
        """
        try:
            self._shutdown_event.wait()
        except RuntimeError as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ShutdownManager.wait_for_shutdown", "Failed while waiting", exc)
            ) from exc

    def shutdown_requested(self) -> bool:
        """
        Summary
        Return whether shutdown has been requested.

        Inputs
        None.

        Outputs
        True when shutdown was triggered, else false.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when querying state fails unexpectedly.

        Ties to other methods
        Used by UI refresh loops and server entrypoints to avoid scheduling new work during teardown.

        Why this exists
        Provides a safe public check for shutdown state without exposing internal event fields.
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
        Summary
        Trigger shutdown and run cleanup callbacks.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Runs cleanup callbacks and sets shutdown event.

        Error handling
        Raises `RuntimeError` with module and method context when shutdown triggering fails unexpectedly.

        Ties to other methods
        Used internally by signal handlers.

        Why this exists
        Ensures cleanup runs before exit.
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
        Summary
        Run registered cleanup callbacks with time bounds.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Executes cleanup callbacks.

        Error handling
        Raises `RuntimeError` with module and method context when cleanup fails unexpectedly.

        Ties to other methods
        Used by `trigger_shutdown`.

        Why this exists
        Ensures cleanup completes within a bounded time.
        """
        try:
            timeout = float(get_config().shutdown.graceful_timeout_sec)
            deadline = time.monotonic() + timeout
            for callback in self._callbacks:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break

                finished = threading.Event()
                callback_errors: list[Exception] = []

                def _run_callback(cleanup_callback: Callable[[], None] = callback) -> None:
                    """
                    Summary
                    Run one cleanup callback and signal completion.

                    Inputs
                    cleanup_callback: Registered cleanup action.

                    Outputs
                    None.

                    Side effects
                    Executes cleanup and records any exception for the coordinating thread.

                    Error handling
                    Captures callback exceptions so they can be re-raised after the bounded wait.

                    Ties to other methods
                    Used by `_run_cleanup` as a daemon-thread target.

                    Why this exists
                    A misbehaving callback must not block the shutdown deadline.
                    """
                    try:
                        cleanup_callback()
                    except Exception as callback_exc:
                        callback_errors.append(callback_exc)
                    finally:
                        finished.set()

                worker = threading.Thread(
                    target=_run_callback,
                    name="shutdown-cleanup",
                    daemon=True,
                )
                worker.start()
                if not finished.wait(timeout=remaining):
                    break
                if callback_errors:
                    raise callback_errors[0]
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ShutdownManager._run_cleanup", "Cleanup failed", exc)
            ) from exc

    def _handle_signal(self, _signum: int, _frame: FrameType | None) -> None:
        """
        Summary
        Handle OS signals by triggering shutdown.

        Inputs
        signal number and optional frame are provided by the signal module.

        Outputs
        None.

        Side effects
        Triggers shutdown.

        Error handling
        Raises `RuntimeError` with module and method context when signal handling fails unexpectedly.

        Ties to other methods
        Registered by `install_handlers`.

        Why this exists
        Ensures graceful shutdown on SIGINT and SIGTERM.
        """
        try:
            self.trigger_shutdown()
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ShutdownManager._handle_signal", "Signal handling failed", exc)
            ) from exc
