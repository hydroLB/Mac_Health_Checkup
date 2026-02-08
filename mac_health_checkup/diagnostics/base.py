from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.data import (
    fmt_bytes,
    fmt_percent,
    fmt_temp_c,
    fmt_temp_f,
    safe_float,
    safe_int,
)
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.loggers import (
    LogContext,
    LoggingFields,
    StructuredLogger,
    configure_logging_once,
    new_correlation_id,
)

MODULE_PATH = "mac_health_checkup/diagnostics/base.py"


@dataclass
class Cache:
    """
    Summary
    Simple TTL cache for diagnostics results.

    Inputs
    ttl_seconds: TTL in seconds for cache entries.

    Outputs
    Cached values by key.

    Side effects
    Stores cached data in memory.

    Error handling
    Methods raise `RuntimeError` with module and method context when cache operations fail unexpectedly.

    Ties to other methods
    Used by diagnostics to avoid repeated system calls.

    Why this exists
    Reduces repeated system calls while keeping data fresh.
    """

    ttl_seconds: int
    _entries: dict[str, tuple[float, JsonDict]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def get(self, key: str) -> JsonDict | None:
        """
        Summary
        Retrieve a cached value if it is still valid.

        Inputs
        key: Cache key.

        Outputs
        Cached dict or None when expired or missing.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when cache reads fail unexpectedly.

        Ties to other methods
        Used by diagnostics fetch methods.

        Why this exists
        Avoids redundant system calls within a TTL window.
        """
        try:
            with self._lock:
                entry = self._entries.get(key)
            if entry is None:
                return None
            ts, data = entry
            if time.time() - ts > self.ttl_seconds:
                return None
            return data
        except (TypeError, ValueError) as exc:
            raise RuntimeError(format_error(MODULE_PATH, "Cache.get", "Failed to read cache", exc)) from exc

    def set(self, key: str, value: JsonDict) -> None:
        """
        Summary
        Store a value in the cache with current timestamp.

        Inputs
        key: Cache key.
        value: Data to store.

        Outputs
        None.

        Side effects
        Updates the cache.

        Error handling
        Raises `RuntimeError` with module and method context when cache writes fail unexpectedly.

        Ties to other methods
        Used by diagnostics fetch methods.

        Why this exists
        Keeps recent diagnostics results available.
        """
        try:
            with self._lock:
                self._entries[key] = (time.time(), value)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(format_error(MODULE_PATH, "Cache.set", "Failed to store cache", exc)) from exc


def get_diagnostics_logger() -> StructuredLogger:
    """
    Summary
    Return a structured logger for diagnostics modules.

    Inputs
    None.

    Outputs
    StructuredLogger instance.

    Side effects
    Configures logging once if not configured.

    Error handling
    Raises `RuntimeError` with module and method context when logger configuration fails.

    Ties to other methods
    Used by diagnostics classes for logging.

    Why this exists
    Ensures diagnostics logs are consistent and structured.
    """
    try:
        cfg = get_config()
        fields = LoggingFields(
            event_field=cfg.logging.event_field,
            corr_id_field=cfg.logging.correlation_id_field,
            component_field=cfg.logging.component_field,
        )
        configure_logging_once(cfg.logging.redaction(), fields)
        return StructuredLogger("mac_health_checkup.diagnostics", cfg.logging.redaction(), fields)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "get_diagnostics_logger", "Failed to get logger", exc)
        ) from exc


def new_context(component: str) -> LogContext:
    """
    Summary
    Build a new log context for diagnostics.

    Inputs
    component: Diagnostics component name.

    Outputs
    LogContext with component and correlation id.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when context creation fails.

    Ties to other methods
    Used by diagnostics fetch methods.

    Why this exists
    Provides consistent metadata for diagnostics logs.
    """
    try:
        return LogContext(component=component, corr_id=new_correlation_id())
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "new_context", "Failed to build context", exc)) from exc


def cached_fetch(cache: Cache, key: str, fetcher: Callable[[], JsonDict]) -> JsonDict:
    """
    Summary
    Fetch data with caching applied.

    Inputs
    cache: Cache instance.
    key: Cache key.
    fetcher: Callable producing a JsonDict on cache miss.

    Outputs
    Result dict from cache or fetcher.

    Side effects
    Updates the cache on cache miss.

    Error handling
    Raises `RuntimeError` with module and method context when caching or fetching fails unexpectedly.

    Ties to other methods
    Used by diagnostics classes to wrap fetch logic.

    Why this exists
    Centralizes caching logic to keep diagnostics simple.
    """
    try:
        cached = cache.get(key)
        if cached is not None:
            return cached
        data = fetcher()
        cache.set(key, data)
        return data
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "cached_fetch", "Failed to fetch cached data", exc)
        ) from exc


def coalesce_str(value: str | None, fallback: str) -> str:
    """
    Summary
    Return a fallback string when value is empty.

    Inputs
    value: Optional string.
    fallback: Fallback string.

    Outputs
    Chosen string value.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when string handling fails unexpectedly.

    Ties to other methods
    Used by diagnostics formatting helpers.

    Why this exists
    Simplifies formatting of optional strings.
    """
    try:
        if value and value.strip():
            return value.strip()
        return fallback
    except (AttributeError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "coalesce_str", "Failed to coalesce string", exc)
        ) from exc


__all__ = [
    "Cache",
    "cached_fetch",
    "coalesce_str",
    "fmt_bytes",
    "fmt_percent",
    "fmt_temp_c",
    "fmt_temp_f",
    "safe_float",
    "safe_int",
    "get_diagnostics_logger",
    "new_context",
]
