from __future__ import annotations

import threading
import time
from collections import deque

from mac_health_checkup.core.config import ApiConfig
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/backend/security/throttling.py"


class RequestThrottler:
    """
    Purpose: Enforce per-client rate limits and temporary bans for the agent API.
    Ties: Used by the HTTP handler to keep the API safe on local networks.
    Inputs: ApiConfig with request and auth throttling knobs.
    Outputs: Allow/deny decisions and retry hints.
    Side effects: Tracks in-memory per-IP request and auth failure windows.
    Why: Prevents accidental exposure and basic brute forcing from degrading the host.
    """

    def __init__(self, api: ApiConfig) -> None:
        """
        Purpose: Initialize the throttler from config.
        Ties: Used by handler factories.
        Inputs: api config.
        Outputs: None.
        Side effects: Initializes tracking state.
        Why: Keeps throttling logic centralized and testable.
        """
        try:
            self._api = api
            self._lock = threading.Lock()
            self._requests: dict[str, deque[float]] = {}
            self._auth_failures: dict[str, deque[float]] = {}
            self._banned_until: dict[str, float] = {}
            self._window_sec = 60.0
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "RequestThrottler.__init__", "Failed to init throttler", exc)
            ) from exc

    def allow_request(self, client_ip: str) -> tuple[bool, int]:
        """
        Purpose: Decide whether a request should be processed.
        Ties: Called by the handler for every request.
        Inputs: client_ip from the connection tuple.
        Outputs: (allowed, retry_after_seconds).
        Side effects: Records request timestamps.
        Error handling: Never raises on missing or malformed IP; treats it as a single shared bucket.
        Why: Provides a deterministic throttling gate for every endpoint.
        """
        try:
            ip = client_ip if isinstance(client_ip, str) and client_ip else "unknown"
            now = time.monotonic()
            with self._lock:
                banned_until = self._banned_until.get(ip)
                if banned_until is not None and banned_until > now:
                    return False, int(max(1.0, banned_until - now))
                self._banned_until.pop(ip, None)

                bucket = self._requests.get(ip)
                if bucket is None:
                    bucket = deque()
                    self._requests[ip] = bucket
                self._prune(bucket, now)
                if len(bucket) >= self._api.rate_limit_requests_per_minute:
                    retry = self._retry_after(bucket, now)
                    return False, retry
                bucket.append(now)
                return True, 0
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "RequestThrottler.allow_request", "Failed to throttle request", exc)
            ) from exc

    def record_auth_failure(self, client_ip: str) -> None:
        """
        Purpose: Record an auth failure and potentially ban the client.
        Ties: Called by the handler when auth fails.
        Inputs: client_ip from the connection tuple.
        Outputs: None.
        Side effects: Updates failure windows and ban state.
        Error handling: Never raises on missing or malformed IP; treats it as a single shared bucket.
        Why: Discourages brute-force guessing and reduces log spam on shared networks.
        """
        try:
            ip = client_ip if isinstance(client_ip, str) and client_ip else "unknown"
            now = time.monotonic()
            with self._lock:
                bucket = self._auth_failures.get(ip)
                if bucket is None:
                    bucket = deque()
                    self._auth_failures[ip] = bucket
                self._prune(bucket, now)
                bucket.append(now)
                if len(bucket) >= self._api.max_auth_failures_per_minute:
                    self._banned_until[ip] = now + float(self._api.auth_ban_seconds)
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "RequestThrottler.record_auth_failure",
                    "Failed recording auth failure",
                    exc,
                )
            ) from exc

    def record_auth_success(self, client_ip: str) -> None:
        """
        Purpose: Clear auth failure counters for a client after a successful auth.
        Ties: Called by the handler when auth succeeds.
        Inputs: client_ip from the connection tuple.
        Outputs: None.
        Side effects: Clears the auth failure bucket for the IP.
        Error handling: None.
        Why: Avoids punishing a client after transient typing errors during pairing.
        """
        try:
            ip = client_ip if isinstance(client_ip, str) and client_ip else "unknown"
            with self._lock:
                bucket = self._auth_failures.get(ip)
                if bucket is not None:
                    bucket.clear()
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "RequestThrottler.record_auth_success",
                    "Failed recording auth success",
                    exc,
                )
            ) from exc

    def _prune(self, bucket: deque[float], now: float) -> None:
        """
        Purpose: Prune timestamps older than the sliding window.
        Ties: Used by allow_request and record_auth_failure.
        Inputs: bucket deque and current monotonic timestamp.
        Outputs: None.
        Side effects: Mutates the deque by removing old entries.
        Error handling: None.
        Why: Keeps memory bounded while preserving deterministic behavior.
        """
        while bucket and (now - bucket[0]) > self._window_sec:
            bucket.popleft()

    def _retry_after(self, bucket: deque[float], now: float) -> int:
        """
        Purpose: Compute a conservative Retry-After value for a full bucket.
        Ties: Used by allow_request for 429 responses.
        Inputs: bucket deque and current monotonic timestamp.
        Outputs: Retry-After seconds as int.
        Side effects: None.
        Error handling: None.
        Why: Helps clients back off deterministically.
        """
        if not bucket:
            return 1
        oldest = bucket[0]
        remaining = max(1.0, self._window_sec - (now - oldest))
        return int(max(1.0, remaining))
