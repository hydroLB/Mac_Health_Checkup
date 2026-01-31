from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/core/config/models/gui.py"


@dataclass(frozen=True)
class ThresholdsConfig:
    """
    Purpose: Hold health threshold values for classifying metrics.
    Ties: Used by diagnostics collectors to map raw values to ok/warn/bad.
    Inputs: Temperature thresholds in Celsius and Wi-Fi RSSI thresholds in dBm.
    Outputs: Immutable thresholds configuration.
    Side effects: None.
    Why: Keeps status bucketing consistent and centrally tunable.
    """

    temp_warn_c: float
    temp_bad_c: float
    rssi_warn_dbm: int
    rssi_bad_dbm: int


@dataclass(frozen=True)
class GuiConfig:
    """
    Purpose: Hold detailed GUI configuration.
    Ties: Used across GUI sections and layout management.
    Inputs: Section layout, rendering limits, and helper tunables.
    Outputs: Immutable GUI configuration.
    Side effects: None.
    Why: Keeps UI behavior fully configurable.
    """

    section_rows: list[tuple[str, str, str]]
    scrollable_rows: dict[str, int]
    peripheral_skip_keywords: list[str]
    peripheral_allow_keywords: list[str]
    peripheral_max_name_len: int
    max_devices_lines: int
    indent_spaces: int
    ssd_text_min_lines: int
    ssd_text_max_lines: int
    bytes_per_du: float
    display_headers: list[str]
    devices_headers: list[str]
    display_name_keywords: list[str]
    token_norm_map: dict[str, str]
    skip_display_noise: list[str]
    refresh_helper_timeout_sec: int
    refresh_helper_sample_secs: float
    refresh_helper_max_samples: int
    refresh_helper_target_samples: int
    disp_body_min_rows: int
    disp_body_max_rows: int
    card_bg: str
    card_border: str
    section_padx: int
    section_pady: int
    content_wrap: int
    card_max_height: int
    card_relaxed_height: int
    window_max_width: int
    window_max_height: int
    auto_refresh_ms: int
    fans_refresh_ms: int
    ui_queue_poll_ms: int
    layout_breakpoint_width: int
    layout_min_width: int
    layout_retry_ms: int
    drag_scroll_divisor: int
    table_row_height: int
    table_max_visible_rows: int
    table_min_col_width: int


@dataclass(frozen=True)
class DisplayTransportConfig:
    """
    Purpose: Hold display transport estimation configuration.
    Ties: Used by display transport diagnostics.
    Inputs: Overhead factor and default bits per pixel.
    Outputs: Immutable display transport configuration.
    Side effects: None.
    Why: Makes transport estimation tunable and testable.
    """

    overhead_factor: float
    default_bpp: int
