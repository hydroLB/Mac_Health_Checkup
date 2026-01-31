from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/core/config/models/runtime.py"


@dataclass(frozen=True)
class RetryConfig:
    """
    Purpose: Hold retry policy configuration.
    Ties: Used by shell utilities for retry behavior.
    Inputs: enabled flag, max attempts, backoff and jitter values.
    Outputs: Immutable retry configuration.
    Side effects: None.
    Why: Makes retry behavior tunable without code edits.
    """

    enabled: bool
    max_attempts: int
    base_delay_ms: int
    max_delay_ms: int
    backoff_factor: float
    jitter_ms: int


@dataclass(frozen=True)
class RateLimitConfig:
    """
    Purpose: Hold UI rate limiting and backpressure settings.
    Ties: Used by dashboard queueing logic.
    Inputs: Max queue size and refresh interval.
    Outputs: Immutable rate limit configuration.
    Side effects: None.
    Why: Ensures UI refresh and background work stays bounded.
    """

    ui_queue_max_items: int
    refresh_min_interval_ms: int


@dataclass(frozen=True)
class IoConfig:
    """
    Purpose: Hold IO configuration settings.
    Ties: Used by shell and file utilities.
    Inputs: Maximum sizes for reads.
    Outputs: Immutable IO configuration.
    Side effects: None.
    Why: Bounds IO to prevent runaway reads.
    """

    pty_read_max_bytes: int
    file_read_max_bytes: int


@dataclass(frozen=True)
class ShutdownConfig:
    """
    Purpose: Hold graceful shutdown timing configuration.
    Ties: Used by shutdown manager to bound cleanup.
    Inputs: Graceful timeout and thread join timeout.
    Outputs: Immutable shutdown configuration.
    Side effects: None.
    Why: Ensures shutdown completes within a bounded time.
    """

    graceful_timeout_sec: int
    thread_join_timeout_sec: int


@dataclass(frozen=True)
class BenchmarkConfig:
    """
    Purpose: Hold benchmarking configuration values.
    Ties: Used by benchmarks and regression checks.
    Inputs: iterations, repeats, regression threshold.
    Outputs: Immutable benchmark configuration.
    Side effects: None.
    Why: Keeps benchmark runs deterministic and tunable.
    """

    iterations: int
    repeats: int
    max_regression: float


@dataclass(frozen=True)
class TimeoutConfig:
    """
    Purpose: Hold timeout configuration for diagnostics and caching.
    Ties: Used across diagnostics and shell utilities.
    Inputs: Cache TTLs and command timeouts.
    Outputs: Immutable timeout configuration.
    Side effects: None.
    Why: Ensures IO and caching are bounded consistently.
    """

    cache_ttl: int
    default_cmd_timeout: int
    snapshot_backend_timeout_sec: int
    smartctl_timeout: int
    sudo_pty_timeout: int
    powermetrics_timeout: int
    performance_cache_ttl: int
    network_quality_timeout: int
    network_cache_ttl: int
    display_cache_ttl: int
    power_sp_cache_ttl: int
    power_ioreg_cache_ttl: int
    istats_timeout: int
