from __future__ import annotations

import time
from dataclasses import dataclass, field

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/queueing.py"


@dataclass
class RefreshLimiter:
    """
    Summary
    Enforce minimum refresh intervals per section.

    Inputs
    None. Reads config for minimum interval.

    Outputs
    None. Tracks timestamps internally.

    Side effects
    Stores timestamps in memory.

    Error handling
    Methods raise `RuntimeError` with module and method context when throttling computations fail unexpectedly.

    Ties to other methods
    Used by dashboard section runner for backpressure.

    Why this exists
    Prevents refresh loops from overwhelming the system.
    """

    _last_run: dict[str, float] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        """
        Summary
        Check whether a section is allowed to run now.

        Inputs
        key: Section key.

        Outputs
        True when enough time has elapsed, false otherwise.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when limit checks fail unexpectedly.

        Ties to other methods
        Used by `run_section` to throttle refreshes.

        Why this exists
        Enforces a consistent refresh cadence.
        """
        try:
            min_interval = get_config().rate_limits.refresh_min_interval_ms / 1000.0
            last = self._last_run.get(key)
            if last is None:
                return True
            return (time.time() - last) >= min_interval
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "RefreshLimiter.allow", "Failed to check limit", exc)
            ) from exc

    def mark(self, key: str) -> None:
        """
        Summary
        Record a section run timestamp.

        Inputs
        key: Section key.

        Outputs
        None.

        Side effects
        Updates timestamp tracking.

        Error handling
        Raises `RuntimeError` with module and method context when timestamp updates fail unexpectedly.

        Ties to other methods
        Used by `run_section` after executing a handler.

        Why this exists
        Keeps refresh throttling accurate.
        """
        try:
            self._last_run[key] = time.time()
        except (RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "RefreshLimiter.mark", "Failed to mark run", exc)
            ) from exc


@dataclass
class SectionQueue:
    """
    Summary
    Queue section refresh work with a bounded size.

    Inputs
    None. Uses config rate limits.

    Outputs
    None. Stores queued keys.

    Side effects
    Stores queued keys in memory.

    Error handling
    Methods raise `RuntimeError` with module and method context when queue operations fail unexpectedly.

    Ties to other methods
    Used by the GUI to prevent unbounded refresh backlog.

    Why this exists
    Provides simple backpressure for GUI refresh work.
    """

    _keys: list[str] = field(default_factory=list)
    _key_set: set[str] = field(default_factory=set)

    def enqueue(self, key: str) -> bool:
        """
        Summary
        Add a section key to the queue if space allows.

        Inputs
        key: Section key.

        Outputs
        True when enqueued, false when queue is full.

        Side effects
        Updates queue state.

        Error handling
        Raises `RuntimeError` with module and method context when enqueueing fails unexpectedly.

        Ties to other methods
        Used by the GUI refresh loop.

        Why this exists
        Prevents unbounded refresh backlog.
        """
        try:
            limit = get_config().rate_limits.ui_queue_max_items
            if key in self._key_set:
                return True
            if len(self._keys) >= limit:
                return False
            self._keys.append(key)
            self._key_set.add(key)
            return True
        except (RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SectionQueue.enqueue", "Failed to enqueue", exc)
            ) from exc

    def drain(self) -> list[str]:
        """
        Summary
        Drain all queued keys in FIFO order.

        Inputs
        None.

        Outputs
        List of queued section keys.

        Side effects
        Clears queue state.

        Error handling
        Raises `RuntimeError` with module and method context when draining fails unexpectedly.

        Ties to other methods
        Used by the GUI refresh loop.

        Why this exists
        Allows the refresh loop to process bounded work.
        """
        try:
            keys = list(self._keys)
            self._keys.clear()
            self._key_set.clear()
            return keys
        except (RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SectionQueue.drain", "Failed to drain queue", exc)
            ) from exc
