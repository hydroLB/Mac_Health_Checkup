from __future__ import annotations

import time
from dataclasses import dataclass, field

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/queueing.py"


@dataclass
class RefreshLimiter:
    """
    Purpose: Enforce minimum refresh intervals per section.
    Ties: Used by dashboard section runner for backpressure.
    Inputs: None. Reads config for minimum interval.
    Outputs: None. Tracks timestamps internally.
    Side effects: Stores timestamps in memory.
    Why: Prevents refresh loops from overwhelming the system.
    """

    _last_run: dict[str, float] = field(default_factory=dict)

    def allow(self, key: str) -> bool:
        """
        Purpose: Check whether a section is allowed to run now.
        Ties: Used by run_section to throttle refreshes.
        Inputs: key is the section key.
        Outputs: True if enough time has elapsed, False otherwise.
        Side effects: None.
        Why: Enforces a consistent refresh cadence.
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
        Purpose: Record a section run timestamp.
        Ties: Used by run_section after executing a handler.
        Inputs: key is the section key.
        Outputs: None.
        Side effects: Updates timestamp tracking.
        Why: Keeps refresh throttling accurate.
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
    Purpose: Queue section refresh work with a bounded size.
    Ties: Used by the GUI to prevent unbounded refresh backlog.
    Inputs: None. Uses config rate limits.
    Outputs: None. Stores queued keys.
    Side effects: Stores queued keys in memory.
    Why: Provides simple backpressure for GUI refresh work.
    """

    _keys: list[str] = field(default_factory=list)
    _key_set: set[str] = field(default_factory=set)

    def enqueue(self, key: str) -> bool:
        """
        Purpose: Add a section key to the queue if space allows.
        Ties: Used by the GUI refresh loop.
        Inputs: key is the section key.
        Outputs: True if enqueued, False if queue is full.
        Side effects: Updates queue state.
        Why: Prevents unbounded refresh backlog.
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
        Purpose: Drain all queued keys in FIFO order.
        Ties: Used by the GUI refresh loop.
        Inputs: None.
        Outputs: List of queued section keys.
        Side effects: Clears queue state.
        Why: Allows the refresh loop to process bounded work.
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
