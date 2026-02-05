from __future__ import annotations

import os

from mac_health_checkup.core.config.models.backend import ApiConfig, FansConfig
from mac_health_checkup.core.config.models.gui import DisplayTransportConfig, GuiConfig, ThresholdsConfig
from mac_health_checkup.core.config.parsing.base import get_section
from mac_health_checkup.core.config.validation.collections import (
    require_dict_str_int,
    require_dict_str_str,
    require_list_str,
)
from mac_health_checkup.core.config.validation.primitives import (
    require_bool,
    require_float,
    require_int,
    require_str,
)
from mac_health_checkup.core.types import JsonDict, JsonValue
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/parsing/features.py"


def parse_api(raw: JsonDict) -> ApiConfig:
    """
    Summary
    Parse the `api` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `ApiConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by `SnapshotApiServer` to bind and secure the agent API.

    Why this exists
    Makes agent API security knobs explicit and centrally validated.
    """
    try:
        section = get_section(raw, "api")
        bind_host = require_str(section.get("bind_host"))
        bind_override = os.getenv("MAC_HEALTH_CHECKUP_API_BIND_HOST")
        if bind_override is not None and bind_override.strip():
            bind_host = require_str(bind_override.strip())

        port = require_int(0, 65535)(section.get("port"))
        port_override = os.getenv("MAC_HEALTH_CHECKUP_API_PORT")
        if port_override is not None and port_override.strip():
            try:
                port = require_int(0, 65535)(port_override.strip())
            except ValueError as exc:
                raise ValueError(
                    f"Invalid MAC_HEALTH_CHECKUP_API_PORT override: {port_override!r} (expected 0-65535)"
                ) from exc

        return ApiConfig(
            enabled=require_bool(section.get("enabled")),
            bind_host=bind_host,
            port=port,
            allow_lan=require_bool(section.get("allow_lan")),
            allow_insecure_http_lan=require_bool(section.get("allow_insecure_http_lan")),
            tls_enabled=require_bool(section.get("tls_enabled")),
            tls_cert_path=require_str(section.get("tls_cert_path")),
            tls_key_path=require_str(section.get("tls_key_path")),
            auth_token=require_str(section.get("auth_token")),
            min_auth_token_length=require_int(1, 256)(section.get("min_auth_token_length")),
            blocked_auth_tokens=_require_list_str_default(section.get("blocked_auth_tokens"), default=[]),
            rate_limit_requests_per_minute=require_int(1, 10_000)(
                section.get("rate_limit_requests_per_minute")
            ),
            max_auth_failures_per_minute=require_int(1, 10_000)(section.get("max_auth_failures_per_minute")),
            auth_ban_seconds=require_int(1, 86_400)(section.get("auth_ban_seconds")),
            request_timeout_sec=require_int(1, 120)(section.get("request_timeout_sec")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "parse_api", "Failed to parse api", exc)) from exc


def _require_list_str_default(value: JsonValue | None, *, default: list[str]) -> list[str]:
    """
    Summary
    Parse an optional list of strings, returning a default when the value is missing.

    Inputs
    value: Raw JSON value.
    default: Fallback list when the value is missing or null.

    Outputs
    List of strings.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context when the input is present but malformed.

    Ties to other methods
    Used by `parse_api` to keep optional list settings ergonomic.

    Why this exists
    Avoids sprinkling `None` checks throughout section parsers while keeping validation strict.
    """
    try:
        if value is None:
            return default
        return require_list_str(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            format_error(MODULE_PATH, "_require_list_str_default", "Invalid list[str] value", exc)
        ) from exc


def parse_fans(raw: JsonDict) -> FansConfig:
    """
    Summary
    Parse the `fans` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `FansConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by fan and thermals diagnostics to decide whether sudo escalation is allowed.

    Why this exists
    Keeps privilege boundaries explicit and centrally controlled.
    """
    try:
        section = get_section(raw, "fans")
        return FansConfig(
            use_sudo=require_bool(section.get("use_sudo")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "parse_fans", "Failed to parse fans", exc)) from exc


def parse_thresholds(raw: JsonDict) -> ThresholdsConfig:
    """
    Summary
    Parse the `thresholds` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `ThresholdsConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by health bucketing utilities to map numeric metrics into ok, warn, bad statuses.

    Why this exists
    Ensures thresholds are consistent and validated across all diagnostics.
    """
    try:
        section = get_section(raw, "thresholds")
        temp_warn_c = require_float(-50.0, 200.0)(section.get("temp_warn_c"))
        temp_bad_c = require_float(-50.0, 250.0)(section.get("temp_bad_c"))
        if temp_bad_c <= temp_warn_c:
            raise ValueError("thresholds.temp_bad_c must be greater than thresholds.temp_warn_c")
        rssi_warn_dbm = require_int(-120, 0)(section.get("rssi_warn_dbm"))
        rssi_bad_dbm = require_int(-120, 0)(section.get("rssi_bad_dbm"))
        if rssi_bad_dbm >= rssi_warn_dbm:
            raise ValueError("thresholds.rssi_bad_dbm must be less than thresholds.rssi_warn_dbm")
        return ThresholdsConfig(
            temp_warn_c=temp_warn_c,
            temp_bad_c=temp_bad_c,
            rssi_warn_dbm=rssi_warn_dbm,
            rssi_bad_dbm=rssi_bad_dbm,
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "parse_thresholds", "Failed to parse thresholds", exc)
        ) from exc


def parse_gui(raw: JsonDict) -> GuiConfig:
    """
    Summary
    Parse the `gui` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `GuiConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by Tk layout and section renderers to size widgets, tables, and refresh behavior.

    Why this exists
    Keeps UI behavior tunable while validating shapes and bounds of complex nested settings.
    """
    try:
        section = get_section(raw, "gui")
        section_rows_raw = section.get("section_rows")
        if not isinstance(section_rows_raw, list):
            raise ValueError("section_rows must be list")
        section_rows: list[tuple[str, str, str]] = []
        for row in section_rows_raw:
            if not isinstance(row, list) or len(row) != 3:
                raise ValueError("section row must be list of three strings")
            if not all(isinstance(item, str) for item in row):
                raise ValueError("section row items must be strings")
            section_rows.append((require_str(row[0]), require_str(row[1]), require_str(row[2])))

        return GuiConfig(
            section_rows=section_rows,
            scrollable_rows=require_dict_str_int(section.get("scrollable_rows")),
            peripheral_skip_keywords=require_list_str(section.get("peripheral_skip_keywords")),
            peripheral_allow_keywords=require_list_str(section.get("peripheral_allow_keywords")),
            peripheral_max_name_len=require_int(1, 200)(section.get("peripheral_max_name_len")),
            max_devices_lines=require_int(1, 200)(section.get("max_devices_lines")),
            indent_spaces=require_int(0, 16)(section.get("indent_spaces")),
            ssd_text_min_lines=require_int(1, 200)(section.get("ssd_text_min_lines")),
            ssd_text_max_lines=require_int(1, 200)(section.get("ssd_text_max_lines")),
            bytes_per_du=require_float(1.0, 1_000_000_000.0)(section.get("bytes_per_du")),
            display_headers=require_list_str(section.get("display_headers")),
            devices_headers=require_list_str(section.get("devices_headers")),
            display_name_keywords=require_list_str(section.get("display_name_keywords")),
            token_norm_map=require_dict_str_str(section.get("token_norm_map")),
            skip_display_noise=require_list_str(section.get("skip_display_noise")),
            refresh_helper_timeout_sec=require_int(1, 120)(section.get("refresh_helper_timeout_sec")),
            refresh_helper_sample_secs=require_float(0.1, 60.0)(section.get("refresh_helper_sample_secs")),
            refresh_helper_max_samples=require_int(1, 10_000)(section.get("refresh_helper_max_samples")),
            refresh_helper_target_samples=require_int(1, 10_000)(
                section.get("refresh_helper_target_samples")
            ),
            disp_body_min_rows=require_int(1, 200)(section.get("disp_body_min_rows")),
            disp_body_max_rows=require_int(1, 200)(section.get("disp_body_max_rows")),
            card_bg=require_str(section.get("card_bg")),
            card_border=require_str(section.get("card_border")),
            section_padx=require_int(0, 200)(section.get("section_padx")),
            section_pady=require_int(0, 200)(section.get("section_pady")),
            content_wrap=require_int(100, 5000)(section.get("content_wrap")),
            card_max_height=require_int(100, 5000)(section.get("card_max_height")),
            card_relaxed_height=require_int(100, 5000)(section.get("card_relaxed_height")),
            window_max_width=require_int(100, 5000)(section.get("window_max_width")),
            window_max_height=require_int(100, 5000)(section.get("window_max_height")),
            auto_refresh_ms=require_int(100, 60_000)(section.get("auto_refresh_ms")),
            fans_refresh_ms=require_int(100, 60_000)(section.get("fans_refresh_ms", 5000)),
            ui_queue_poll_ms=require_int(10, 10_000)(section.get("ui_queue_poll_ms")),
            layout_breakpoint_width=require_int(100, 10_000)(section.get("layout_breakpoint_width")),
            layout_min_width=require_int(10, 5000)(section.get("layout_min_width")),
            layout_retry_ms=require_int(10, 10_000)(section.get("layout_retry_ms")),
            drag_scroll_divisor=require_int(1, 100)(section.get("drag_scroll_divisor")),
            table_row_height=require_int(10, 200)(section.get("table_row_height")),
            table_max_visible_rows=require_int(1, 50)(section.get("table_max_visible_rows")),
            table_min_col_width=require_int(10, 500)(section.get("table_min_col_width")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "parse_gui", "Failed to parse gui", exc)) from exc


def parse_display_transport(raw: JsonDict) -> DisplayTransportConfig:
    """
    Summary
    Parse the `display_transport` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `DisplayTransportConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by display transport diagnostics to tune estimation behavior.

    Why this exists
    Keeps transport estimation tunables explicit and testable.
    """
    try:
        section = get_section(raw, "display_transport")
        return DisplayTransportConfig(
            overhead_factor=require_float(1.0, 10.0)(section.get("overhead_factor")),
            default_bpp=require_int(8, 120)(section.get("default_bpp")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "parse_display_transport", "Failed to parse display transport", exc)
        ) from exc
