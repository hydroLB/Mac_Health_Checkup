from __future__ import annotations

from mac_health_checkup.core.config.models.runtime import (
    BenchmarkConfig,
    IoConfig,
    RateLimitConfig,
    RetryConfig,
    ShutdownConfig,
    TimeoutConfig,
)
from mac_health_checkup.core.config.parsing.base import get_section
from mac_health_checkup.core.config.validation.primitives import require_bool, require_float, require_int
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/parsing/runtime.py"


def parse_retries(raw: JsonDict) -> RetryConfig:
    """
    Summary
    Parse the `retries` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `RetryConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by `safe_run` and related subprocess helpers.

    Why this exists
    Centralizes retry policy and prevents ad hoc backoff behavior from creeping into callers.
    """
    try:
        section = get_section(raw, "retries")
        return RetryConfig(
            enabled=require_bool(section.get("enabled")),
            max_attempts=require_int(1, 20)(section.get("max_attempts")),
            base_delay_ms=require_int(0, 60_000)(section.get("base_delay_ms")),
            max_delay_ms=require_int(0, 300_000)(section.get("max_delay_ms")),
            backoff_factor=require_float(1.0, 10.0)(section.get("backoff_factor")),
            jitter_ms=require_int(0, 60_000)(section.get("jitter_ms")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "parse_retries", "Failed to parse retries", exc)
        ) from exc


def parse_rate_limits(raw: JsonDict) -> RateLimitConfig:
    """
    Summary
    Parse the `rate_limits` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `RateLimitConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by dashboard queueing and refresh logic.

    Why this exists
    Ensures UI background work remains bounded and stable under slow system calls.
    """
    try:
        section = get_section(raw, "rate_limits")
        return RateLimitConfig(
            ui_queue_max_items=require_int(1, 10_000)(section.get("ui_queue_max_items")),
            refresh_min_interval_ms=require_int(10, 60_000)(section.get("refresh_min_interval_ms")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "parse_rate_limits", "Failed to parse rate_limits", exc)
        ) from exc


def parse_io(raw: JsonDict) -> IoConfig:
    """
    Summary
    Parse the `io` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `IoConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by PTY and file reads in shell utilities.

    Why this exists
    Prevents unbounded reads and makes IO limits explicit.
    """
    try:
        section = get_section(raw, "io")
        return IoConfig(
            pty_read_max_bytes=require_int(1, 10_000_000)(section.get("pty_read_max_bytes")),
            file_read_max_bytes=require_int(1, 10_000_000)(section.get("file_read_max_bytes")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "parse_io", "Failed to parse io", exc)) from exc


def parse_shutdown(raw: JsonDict) -> ShutdownConfig:
    """
    Summary
    Parse the `shutdown` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `ShutdownConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by `ShutdownManager` to bound join and cleanup time.

    Why this exists
    Avoids hangs during shutdown and keeps signal handling predictable.
    """
    try:
        section = get_section(raw, "shutdown")
        return ShutdownConfig(
            graceful_timeout_sec=require_int(1, 120)(section.get("graceful_timeout_sec")),
            thread_join_timeout_sec=require_int(1, 120)(section.get("thread_join_timeout_sec")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "parse_shutdown", "Failed to parse shutdown", exc)
        ) from exc


def parse_benchmarks(raw: JsonDict) -> BenchmarkConfig:
    """
    Summary
    Parse the `benchmarks` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `BenchmarkConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by benchmark runners to tune iteration counts and regression thresholds.

    Why this exists
    Keeps benchmark runs deterministic and comparable across environments.
    """
    try:
        section = get_section(raw, "benchmarks")
        return BenchmarkConfig(
            iterations=require_int(1, 1_000_000)(section.get("iterations")),
            repeats=require_int(1, 1000)(section.get("repeats")),
            max_regression=require_float(0.0, 10.0)(section.get("max_regression")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "parse_benchmarks", "Failed to parse benchmarks", exc)
        ) from exc


def parse_timeouts(raw: JsonDict) -> TimeoutConfig:
    """
    Summary
    Parse the `timeouts` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `TimeoutConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by diagnostics collectors and snapshot workflows to bound system calls and caches.

    Why this exists
    Provides one place to tune time bounds for IO and caching across the application.
    """
    try:
        section = get_section(raw, "timeouts")
        return TimeoutConfig(
            cache_ttl=require_int(1, 3600)(section.get("cache_ttl")),
            default_cmd_timeout=require_int(1, 600)(section.get("default_cmd_timeout")),
            snapshot_backend_timeout_sec=require_int(1, 60)(section.get("snapshot_backend_timeout_sec")),
            smartctl_timeout=require_int(1, 120)(section.get("smartctl_timeout")),
            sudo_pty_timeout=require_int(1, 60)(section.get("sudo_pty_timeout")),
            powermetrics_timeout=require_int(1, 60)(section.get("powermetrics_timeout")),
            performance_cache_ttl=require_int(1, 3600)(section.get("performance_cache_ttl")),
            network_quality_timeout=require_int(1, 120)(section.get("network_quality_timeout")),
            network_cache_ttl=require_int(1, 3600)(section.get("network_cache_ttl")),
            display_cache_ttl=require_int(1, 3600)(section.get("display_cache_ttl")),
            power_sp_cache_ttl=require_int(1, 3600)(section.get("power_sp_cache_ttl")),
            power_ioreg_cache_ttl=require_int(1, 3600)(section.get("power_ioreg_cache_ttl")),
            istats_timeout=require_int(1, 120)(section.get("istats_timeout")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "parse_timeouts", "Failed to parse timeouts", exc)
        ) from exc
