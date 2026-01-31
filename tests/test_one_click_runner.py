from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from mac_health_checkup.app.backend.one_click import _build_config_with_api_overrides
from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_one_click_runner.py"


def test_build_config_with_api_overrides_preserves_base_sections(tmp_path: Path) -> None:
    """
    Purpose: Ensure one-click config overlay only changes the api section.
    Ties: Exercises _build_config_with_api_overrides.
    Inputs: Minimal base config dict and api overrides.
    Outputs: Assertions on merged shape.
    Side effects: Writes a temp file for realistic JSON round-trip.
    Why: The one-click runner must not require users to maintain a separate full config file by hand.
    """
    try:
        base = {
            "colors": {
                "bg": "#000000",
                "fg": "#ffffff",
                "ok": "#00ff00",
                "warn": "#ffff00",
                "bad": "#ff0000",
                "section": "#339af0",
                "label": "#f1c40f",
                "field": "#daf6ff",
                "banner_good": "#28a745",
                "banner_warn": "#ffc107",
                "banner_bad": "#dc3545",
            },
            "fonts": {
                "family_default": "Helvetica",
                "family_mono": "Menlo",
                "size_section": 16,
                "size_banner": 18,
                "size_field": 13,
                "size_tooltip": 10,
                "weight_bold": "bold",
                "weight_normal": "normal",
                "tooltip_bg": "#111111",
                "tooltip_fg": "#eeeeee",
            },
            "ui": {"window_size": "820x1180", "window_title": "Mac Health Checkup"},
            "logging": {
                "max_lines": 500,
                "prefix": "[{timestamp} {level}{context}]",
                "truncate_len": 1000,
                "format": "json",
                "redact_keys": [],
                "redact_replacement": "[REDACTED]",
                "correlation_id_field": "corr_id",
                "event_field": "event",
                "component_field": "component",
            },
            "retries": {
                "enabled": True,
                "max_attempts": 2,
                "base_delay_ms": 150,
                "max_delay_ms": 1000,
                "backoff_factor": 2.0,
                "jitter_ms": 75,
            },
            "rate_limits": {"ui_queue_max_items": 200, "refresh_min_interval_ms": 200},
            "io": {"pty_read_max_bytes": 65536, "file_read_max_bytes": 1048576},
            "shutdown": {"graceful_timeout_sec": 2, "thread_join_timeout_sec": 1},
            "benchmarks": {"iterations": 200, "repeats": 5, "max_regression": 0.3},
            "timeouts": {
                "cache_ttl": 30,
                "default_cmd_timeout": 10,
                "smartctl_timeout": 10,
                "sudo_pty_timeout": 10,
                "powermetrics_timeout": 8,
                "performance_cache_ttl": 5,
                "network_quality_timeout": 15,
                "network_cache_ttl": 12,
                "display_cache_ttl": 8,
                "power_sp_cache_ttl": 8,
                "power_ioreg_cache_ttl": 5,
                "istats_timeout": 5,
            },
            "api": {
                "enabled": False,
                "bind_host": "127.0.0.1",
                "port": 7878,
                "allow_lan": False,
                "allow_insecure_http_lan": False,
                "tls_enabled": False,
                "tls_cert_path": ".local/tls/agent-cert.pem",
                "tls_key_path": ".local/tls/agent-key.pem",
                "auth_token": "change-me",
                "min_auth_token_length": 24,
                "blocked_auth_tokens": ["change-me"],
                "rate_limit_requests_per_minute": 120,
                "max_auth_failures_per_minute": 10,
                "auth_ban_seconds": 120,
                "request_timeout_sec": 15,
            },
            "fans": {"use_sudo": False},
            "gui": {
                "section_rows": [["A", "B", "a"]],
                "scrollable_rows": {},
                "peripheral_skip_keywords": [],
                "peripheral_allow_keywords": [],
                "peripheral_max_name_len": 28,
                "max_devices_lines": 80,
                "indent_spaces": 4,
                "ssd_text_min_lines": 5,
                "ssd_text_max_lines": 10,
                "bytes_per_du": 512000.0,
                "display_headers": ["Name"],
                "devices_headers": ["Bus", "Device"],
                "display_name_keywords": [],
                "token_norm_map": {},
                "skip_display_noise": [],
                "refresh_helper_timeout_sec": 4,
                "refresh_helper_sample_secs": 1.0,
                "refresh_helper_max_samples": 600,
                "refresh_helper_target_samples": 5,
                "disp_body_min_rows": 8,
                "disp_body_max_rows": 16,
                "card_bg": "#1b2027",
                "card_border": "#2a313c",
                "section_padx": 4,
                "section_pady": 3,
                "content_wrap": 760,
                "card_max_height": 420,
                "card_relaxed_height": 520,
                "window_max_width": 1150,
                "window_max_height": 1300,
                "auto_refresh_ms": 1000,
                "ui_queue_poll_ms": 50,
                "layout_breakpoint_width": 760,
                "layout_min_width": 50,
                "layout_retry_ms": 50,
                "drag_scroll_divisor": 12,
                "table_row_height": 22,
                "table_max_visible_rows": 3,
                "table_min_col_width": 80,
            },
            "display_transport": {"overhead_factor": 1.15, "default_bpp": 24},
        }
        base_path = tmp_path / "base.json"
        base_path.write_text(json.dumps(base), encoding="utf-8")
        loaded = json.loads(base_path.read_text(encoding="utf-8"))

        derived = _build_config_with_api_overrides(cast(JsonDict, loaded), {"enabled": True, "port": 9999})
        assert derived["ui"] == base["ui"]
        api = cast(JsonDict, derived["api"])
        assert api["enabled"] is True
        assert api["port"] == 9999
        assert api["bind_host"] == "127.0.0.1"
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_build_config_with_api_overrides_preserves_base_sections failed: {exc}"
        ) from exc


def test_build_config_with_api_overrides_requires_api_section() -> None:
    """
    Purpose: Ensure missing api section yields a clear failure.
    Ties: Exercises _build_config_with_api_overrides.
    Inputs: Base config dict without api section.
    Outputs: Assertion that it raises.
    Side effects: None.
    Why: Keeps failures actionable when the base config is corrupted.
    """
    try:
        with pytest.raises(RuntimeError):
            _build_config_with_api_overrides({"not_api": {}}, {"enabled": True})
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_build_config_with_api_overrides_requires_api_section failed: {exc}"
        ) from exc
