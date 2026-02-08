from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/core/config/models/runtime.py"


@dataclass(frozen=True)
class RetryConfig:
    """
    Summary
    Hold retry policy configuration.

    Inputs
    Enabled flag, max attempts, backoff factor, and jitter values.

    Outputs
    Immutable retry configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_retries` and consumed by IO boundary helpers.

    Why this exists
    Makes retry behavior tunable without code edits.
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
    Summary
    Hold UI rate limiting and backpressure settings.

    Inputs
    Max queue size and refresh interval.

    Outputs
    Immutable rate limit configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_rate_limits` and consumed by dashboard queueing logic.

    Why this exists
    Ensures UI refresh and background work stays bounded.
    """

    ui_queue_max_items: int
    refresh_min_interval_ms: int


@dataclass(frozen=True)
class IoConfig:
    """
    Summary
    Hold IO configuration settings.

    Inputs
    Maximum sizes for reads.

    Outputs
    Immutable IO configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_io` and used by shell and file utilities.

    Why this exists
    Bounds IO to prevent runaway reads.
    """

    pty_read_max_bytes: int
    file_read_max_bytes: int


@dataclass(frozen=True)
class ShutdownConfig:
    """
    Summary
    Hold graceful shutdown timing configuration.

    Inputs
    Graceful timeout and thread join timeout.

    Outputs
    Immutable shutdown configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_shutdown` and consumed by the shutdown manager.

    Why this exists
    Ensures shutdown completes within a bounded time.
    """

    graceful_timeout_sec: int
    thread_join_timeout_sec: int


@dataclass(frozen=True)
class BenchmarkConfig:
    """
    Summary
    Hold benchmarking configuration values.

    Inputs
    Iterations, repeats, and regression threshold.

    Outputs
    Immutable benchmark configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_benchmarks` and consumed by benchmarks and regression checks.

    Why this exists
    Keeps benchmark runs deterministic and tunable.
    """

    iterations: int
    repeats: int
    max_regression: float


@dataclass(frozen=True)
class TimeoutConfig:
    """
    Summary
    Hold timeout configuration for diagnostics and caching.

    Inputs
    Cache TTLs and command timeouts.

    Outputs
    Immutable timeout configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_timeouts` and consumed across diagnostics and shell utilities.

    Why this exists
    Ensures IO and caching are bounded consistently.
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
    softwareupdate_timeout: int
    softwareupdate_cache_ttl: int
