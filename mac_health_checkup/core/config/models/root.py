from __future__ import annotations

from dataclasses import dataclass

from mac_health_checkup.core.config.models.backend import ApiConfig, FansConfig
from mac_health_checkup.core.config.models.gui import DisplayTransportConfig, GuiConfig, ThresholdsConfig
from mac_health_checkup.core.config.models.observability import LoggingConfig
from mac_health_checkup.core.config.models.runtime import (
    BenchmarkConfig,
    IoConfig,
    RateLimitConfig,
    RetryConfig,
    ShutdownConfig,
    TimeoutConfig,
)
from mac_health_checkup.core.config.models.ui import ColorsConfig, FontsConfig, UiConfig

MODULE_PATH = "mac_health_checkup/core/config/models/root.py"


@dataclass(frozen=True)
class Config:
    """
    Purpose: Central typed config registry for all tunable settings.
    Ties: Used across the application to fetch config values.
    Inputs: Section configs parsed from JSON.
    Outputs: Immutable config container.
    Side effects: None.
    Why: Provides a single source of truth for configuration.
    """

    colors: ColorsConfig
    fonts: FontsConfig
    ui: UiConfig
    logging: LoggingConfig
    retries: RetryConfig
    rate_limits: RateLimitConfig
    io: IoConfig
    shutdown: ShutdownConfig
    benchmarks: BenchmarkConfig
    timeouts: TimeoutConfig
    api: ApiConfig
    fans: FansConfig
    thresholds: ThresholdsConfig
    gui: GuiConfig
    display_transport: DisplayTransportConfig
