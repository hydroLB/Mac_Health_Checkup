import json
from pathlib import Path
from typing import cast

import pytest

from mac_health_checkup.core.config import (
    build_startup_config_validation_report,
    get_config,
    get_config_value,
    require_int,
    reset_config_cache,
)
from mac_health_checkup.core.config.io import config_max_bytes, resolve_config_path
from mac_health_checkup.core.config.parsing.features import parse_api, parse_network, parse_thresholds
from mac_health_checkup.core.config.parsing.ui import parse_ui
from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_config.py"


def test_network_capacity_test_is_opt_in() -> None:
    """
    Summary
    Verify outbound capacity testing is disabled unless the config explicitly enables it.

    Inputs
    None.

    Outputs
    Assertions on parsed network configuration.

    Side effects
    None.

    Error handling
    Raises `AssertionError` when safe-default or opt-in behavior regresses.

    Ties to other methods
    Exercises `parse_network` for absent and explicit settings.

    Why this exists
    Routine dashboard refreshes must not send bandwidth-test traffic by default.
    """
    assert parse_network({}).capacity_test_enabled is False
    parsed = parse_network({"network": {"capacity_test_enabled": True}})
    assert parsed.capacity_test_enabled is True
    assert parsed.capacity_test_cache_ttl == 3600


def _raw_with_api(**overrides: object) -> JsonDict:
    """
    Summary
    Build a minimal raw config payload containing the `api` section.

    Inputs
    `overrides`: API field overrides for focused test setup.

    Outputs
    Raw config dict with one `api` section.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and helper context when payload assembly fails.

    Ties to other methods
    Used by `parse_api` boundary tests in this module.

    Why this exists
    Keeps config-boundary tests concise and deterministic.
    """
    try:
        base: dict[str, object] = {
            "enabled": True,
            "bind_host": "127.0.0.1",
            "port": 7878,
            "allow_lan": False,
            "allow_insecure_http_lan": False,
            "tls_enabled": False,
            "tls_cert_path": ".local/tls/agent-cert.pem",
            "tls_key_path": ".local/tls/agent-key.pem",
            "auth_token": "unit-test-token-0123456789-abcdefghijklmnopqrstuvwxyz",
            "min_auth_token_length": 24,
            "blocked_auth_tokens": ["change-me", "changeme", "password", "token"],
            "rate_limit_requests_per_minute": 120,
            "max_auth_failures_per_minute": 10,
            "auth_ban_seconds": 60,
            "request_timeout_sec": 5,
            "pairing_qr_enabled": True,
        }
        base.update(overrides)
        return cast(JsonDict, {"api": base})
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
        raise AssertionError(f"{MODULE_PATH}:_raw_with_api failed: {exc}") from exc


def test_get_config_value_reads_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify config overrides are loaded from the environment path.

    Inputs
    Temporary config file and monkeypatched env var.

    Outputs
    Assertions on override and fallback values.

    Side effects
    Writes a temp file and updates env vars.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `get_config_value` and `reset_config_cache`.

    Why this exists
    Ensures config lookup respects explicit config files.
    """
    try:
        payload = {"logging": {"max_lines": 900}}
        config_path = tmp_path / "config.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")

        monkeypatch.setenv("MAC_HEALTH_CHECKUP_CONFIG", str(config_path))
        reset_config_cache()

        assert get_config_value("logging.max_lines", 500, require_int(1, 2000)) == 900
        assert get_config_value("logging.truncate_len", 1000, require_int(100, 5000)) == 1000
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
        raise AssertionError(f"{MODULE_PATH}:test_get_config_value_reads_override failed: {exc}") from exc


def test_resolve_config_path_rejects_empty_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify an explicitly empty config-path env override fails fast with a contextual error.

    Inputs
    Monkeypatched `MAC_HEALTH_CHECKUP_CONFIG` environment variable.

    Outputs
    Assertion that `resolve_config_path` raises `RuntimeError`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `resolve_config_path` strict environment contract.

    Why this exists
    Empty overrides should never silently fall back to defaults because that hides deploy misconfiguration.
    """
    try:
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_CONFIG", "   ")
        with pytest.raises(RuntimeError) as exc_info:
            resolve_config_path()
        assert "MAC_HEALTH_CHECKUP_CONFIG is set but empty" in str(exc_info.value)
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
            f"{MODULE_PATH}:test_resolve_config_path_rejects_empty_env_override failed: {exc}"
        ) from exc


def test_config_max_bytes_rejects_empty_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify an explicitly empty config-size env override fails fast with a contextual error.

    Inputs
    Monkeypatched `MAC_HEALTH_CHECKUP_CONFIG_MAX_BYTES` environment variable.

    Outputs
    Assertion that `config_max_bytes` raises `RuntimeError`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `config_max_bytes` strict environment contract.

    Why this exists
    Size-limit overrides should fail closed when misconfigured so startup behavior stays deterministic.
    """
    try:
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_CONFIG_MAX_BYTES", "  ")
        with pytest.raises(RuntimeError) as exc_info:
            config_max_bytes()
        assert "MAC_HEALTH_CHECKUP_CONFIG_MAX_BYTES is set but empty" in str(exc_info.value)
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
            f"{MODULE_PATH}:test_config_max_bytes_rejects_empty_env_override failed: {exc}"
        ) from exc


def test_build_startup_config_validation_report_lists_active_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Summary
    Verify startup config report includes active env override keys and effective API values.

    Inputs
    Monkeypatched env overrides and the default typed config.

    Outputs
    Assertions on `StartupConfigValidationReport` fields and log payload shape.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `build_startup_config_validation_report` and `StartupConfigValidationReport.to_log_payload`.

    Why this exists
    Startup observability should prove which env overrides were active when config validation succeeded.
    """
    try:
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_API_AUTH_TOKEN", "runtime-token-for-startup-test")
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_API_PORT", "0")
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL", "https://example.test:7878")
        reset_config_cache()
        cfg = get_config()
        report = build_startup_config_validation_report(cfg)
        payload = report.to_log_payload()
        env_overrides = payload.get("env_overrides")
        assert isinstance(env_overrides, list)
        assert "MAC_HEALTH_CHECKUP_API_AUTH_TOKEN" in env_overrides
        assert "MAC_HEALTH_CHECKUP_API_PORT" in env_overrides
        assert "MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL" in env_overrides
        assert cfg.api.auth_token == "runtime-token-for-startup-test"
        assert payload["api_enabled"] == cfg.api.enabled
        assert payload["api_bind_host"] == cfg.api.bind_host
        assert payload["api_port"] == cfg.api.port
        reset_config_cache()
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
            f"{MODULE_PATH}:test_build_startup_config_validation_report_lists_active_env_overrides failed: {exc}"
        ) from exc


def test_api_port_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify the API port can be overridden via env var and supports ephemeral port 0.

    Inputs
    Monkeypatched env var and a minimal raw config dict.

    Outputs
    Assertions on the parsed ApiConfig port value.

    Side effects
    Updates environment variables for the duration of the test.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_api` env override logic.

    Why this exists
    Prevents port-collision issues and enables safe ephemeral port binding in dev and tests.
    """
    try:
        raw = {
            "api": {
                "enabled": True,
                "bind_host": "127.0.0.1",
                "port": 7878,
                "allow_lan": False,
                "allow_insecure_http_lan": False,
                "tls_enabled": False,
                "tls_cert_path": ".local/tls/agent-cert.pem",
                "tls_key_path": ".local/tls/agent-key.pem",
                "auth_token": "unit-test-token-0123456789-abcdefghijklmnopqrstuvwxyz",
                "min_auth_token_length": 24,
                "blocked_auth_tokens": ["change-me", "changeme", "password", "token"],
                "rate_limit_requests_per_minute": 120,
                "max_auth_failures_per_minute": 10,
                "auth_ban_seconds": 60,
                "request_timeout_sec": 5,
                "pairing_qr_enabled": True,
            }
        }

        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_PORT", raising=False)
        api = parse_api(cast(JsonDict, raw))
        assert api.port == 7878

        monkeypatch.setenv("MAC_HEALTH_CHECKUP_API_PORT", "0")
        api2 = parse_api(cast(JsonDict, raw))
        assert api2.port == 0
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
        raise AssertionError(f"{MODULE_PATH}:test_api_port_env_override failed: {exc}") from exc


def test_parse_api_bind_host_env_override_applies(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify `MAC_HEALTH_CHECKUP_API_BIND_HOST` overrides bind host parsing.

    Inputs
    Monkeypatched bind-host env var and raw API config.

    Outputs
    Assertion on parsed `bind_host`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_api` environment override boundary.

    Why this exists
    Ops workflows rely on deterministic host overrides in dev and CI.
    """
    try:
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_API_BIND_HOST", "0.0.0.0")
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_PORT", raising=False)
        parsed = parse_api(_raw_with_api())
        assert parsed.bind_host == "0.0.0.0"
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
            f"{MODULE_PATH}:test_parse_api_bind_host_env_override_applies failed: {exc}"
        ) from exc


def test_parse_api_auth_token_env_override_applies(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify `MAC_HEALTH_CHECKUP_API_AUTH_TOKEN` overrides config token parsing.

    Inputs
    Monkeypatched auth-token env var and raw API config.

    Outputs
    Assertion on parsed `auth_token`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_api` secret-friendly environment override logic.

    Why this exists
    Production tokens should come from runtime secret injection rather than committed config files.
    """
    try:
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_API_AUTH_TOKEN", "runtime-token-from-environment")
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_BIND_HOST", raising=False)
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_PORT", raising=False)
        parsed = parse_api(_raw_with_api(auth_token="change-me"))
        assert parsed.auth_token == "runtime-token-from-environment"
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
            f"{MODULE_PATH}:test_parse_api_auth_token_env_override_applies failed: {exc}"
        ) from exc


def test_parse_api_invalid_port_env_override_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify invalid API port env override fails with contextual parsing error.

    Inputs
    Non-numeric `MAC_HEALTH_CHECKUP_API_PORT` value.

    Outputs
    Assertion that `parse_api` raises `RuntimeError`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_api` env override validation path.

    Why this exists
    Misconfigured CI or launch scripts should fail fast with actionable messages.
    """
    try:
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_API_PORT", "not-a-port")
        with pytest.raises(RuntimeError) as exc_info:
            parse_api(_raw_with_api())
        assert "Invalid MAC_HEALTH_CHECKUP_API_PORT override" in str(exc_info.value)
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
            f"{MODULE_PATH}:test_parse_api_invalid_port_env_override_raises_runtime_error failed: {exc}"
        ) from exc


def test_parse_api_empty_bind_host_env_override_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify empty bind-host env override fails fast instead of silently falling back.

    Inputs
    Empty `MAC_HEALTH_CHECKUP_API_BIND_HOST` value.

    Outputs
    Assertion that `parse_api` raises `RuntimeError`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_api` environment override validation path.

    Why this exists
    Hidden fallback behavior makes deployments nondeterministic and harder to debug.
    """
    try:
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_API_BIND_HOST", "  ")
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_PORT", raising=False)
        with pytest.raises(RuntimeError) as exc_info:
            parse_api(_raw_with_api())
        assert "MAC_HEALTH_CHECKUP_API_BIND_HOST is set but empty" in str(exc_info.value)
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
            f"{MODULE_PATH}:test_parse_api_empty_bind_host_env_override_raises_runtime_error failed: {exc}"
        ) from exc


def test_parse_api_empty_port_env_override_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify empty API port env override fails fast with an actionable error.

    Inputs
    Empty `MAC_HEALTH_CHECKUP_API_PORT` value.

    Outputs
    Assertion that `parse_api` raises `RuntimeError`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_api` strict environment override validation.

    Why this exists
    Startup should fail immediately when critical network configuration is malformed.
    """
    try:
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_BIND_HOST", raising=False)
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_API_PORT", "   ")
        with pytest.raises(RuntimeError) as exc_info:
            parse_api(_raw_with_api())
        assert "MAC_HEALTH_CHECKUP_API_PORT is set but empty" in str(exc_info.value)
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
            f"{MODULE_PATH}:test_parse_api_empty_port_env_override_raises_runtime_error failed: {exc}"
        ) from exc


def test_parse_api_empty_auth_token_env_override_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Summary
    Verify empty auth-token env override fails fast with an actionable error.

    Inputs
    Empty `MAC_HEALTH_CHECKUP_API_AUTH_TOKEN` value.

    Outputs
    Assertion that `parse_api` raises `RuntimeError`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_api` strict secret override validation.

    Why this exists
    Secret injection mistakes should fail closed instead of silently falling back to insecure defaults.
    """
    try:
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_BIND_HOST", raising=False)
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_PORT", raising=False)
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_API_AUTH_TOKEN", "   ")
        with pytest.raises(RuntimeError) as exc_info:
            parse_api(_raw_with_api())
        assert "MAC_HEALTH_CHECKUP_API_AUTH_TOKEN is set but empty" in str(exc_info.value)
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
            f"{MODULE_PATH}:test_parse_api_empty_auth_token_env_override_raises_runtime_error failed: {exc}"
        ) from exc


def test_parse_api_defaults_blocked_tokens_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify blocked token list defaults to empty when config value is omitted.

    Inputs
    Raw API config with `blocked_auth_tokens` set to null.

    Outputs
    Assertion on parsed `blocked_auth_tokens`.

    Side effects
    Clears API env overrides to isolate parser behavior.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_api` optional-list default behavior.

    Why this exists
    Optional config knobs should remain ergonomic while preserving deterministic parsing.
    """
    try:
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_BIND_HOST", raising=False)
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_PORT", raising=False)
        parsed = parse_api(_raw_with_api(blocked_auth_tokens=None))
        assert parsed.blocked_auth_tokens == []
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
            f"{MODULE_PATH}:test_parse_api_defaults_blocked_tokens_when_missing failed: {exc}"
        ) from exc


def test_parse_api_rejects_invalid_blocked_tokens_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify blocked-token list validation rejects malformed values.

    Inputs
    Raw API config with non-string entries in `blocked_auth_tokens`.

    Outputs
    Assertion that `parse_api` raises `RuntimeError`.

    Side effects
    Clears API env overrides to isolate parser behavior.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `_require_list_str_default` strict validation path through `parse_api`.

    Why this exists
    Security policy inputs should fail closed when malformed.
    """
    try:
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_BIND_HOST", raising=False)
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_API_PORT", raising=False)
        with pytest.raises(RuntimeError):
            parse_api(_raw_with_api(blocked_auth_tokens=["ok", 3]))
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
            f"{MODULE_PATH}:test_parse_api_rejects_invalid_blocked_tokens_shape failed: {exc}"
        ) from exc


def test_parse_ui_color_mode_defaults_and_validation() -> None:
    """
    Summary
    Verify `ui.color_mode` defaults to `auto` and rejects unsupported values.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_ui`.

    Why this exists
    Color-mode behavior should stay explicit and deterministic across config changes.
    """
    try:
        default_ui = parse_ui(
            cast(JsonDict, {"ui": {"window_size": "820x1180", "window_title": "Mac Health"}})
        )
        assert default_ui.color_mode == "auto"

        dark_ui = parse_ui(
            cast(
                JsonDict,
                {"ui": {"window_size": "820x1180", "window_title": "Mac Health", "color_mode": "dark"}},
            )
        )
        assert dark_ui.color_mode == "dark"

        with pytest.raises(RuntimeError):
            parse_ui(
                cast(
                    JsonDict,
                    {"ui": {"window_size": "820x1180", "window_title": "Mac Health", "color_mode": "sepia"}},
                )
            )
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
            f"{MODULE_PATH}:test_parse_ui_color_mode_defaults_and_validation failed: {exc}"
        ) from exc


def test_parse_thresholds_accepts_health_and_ssd_policy_knobs() -> None:
    """
    Summary
    Verify threshold parsing includes configurable battery and SSD policy cutoffs.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_thresholds`.

    Why this exists
    Remaining mac-health policy values should stay config-driven, validated, and deterministic.
    """
    try:
        payload = cast(
            JsonDict,
            {
                "thresholds": {
                    "temp_warn_c": 75.0,
                    "temp_bad_c": 90.0,
                    "rssi_warn_dbm": -70,
                    "rssi_bad_dbm": -80,
                    "disk_free_warn_percent": 15.0,
                    "disk_free_bad_percent": 5.0,
                    "memory_free_warn_percent": 20.0,
                    "memory_free_bad_percent": 10.0,
                    "backup_warn_days": 7,
                    "backup_bad_days": 30,
                    "health_excellent_min_percent": 92.0,
                    "health_good_min_percent": 81.0,
                    "health_fair_min_percent": 66.0,
                    "ssd_unsafe_shutdowns_warn_count": 2,
                    "ssd_media_errors_bad_count": 3,
                }
            },
        )
        parsed = parse_thresholds(payload)
        assert parsed.health_excellent_min_percent == pytest.approx(92.0)
        assert parsed.health_good_min_percent == pytest.approx(81.0)
        assert parsed.health_fair_min_percent == pytest.approx(66.0)
        assert parsed.ssd_unsafe_shutdowns_warn_count == 2
        assert parsed.ssd_media_errors_bad_count == 3
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
            f"{MODULE_PATH}:test_parse_thresholds_accepts_health_and_ssd_policy_knobs failed: {exc}"
        ) from exc


def test_parse_thresholds_rejects_invalid_health_band_ordering() -> None:
    """
    Summary
    Verify threshold parsing rejects non-descending health bands.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `parse_thresholds`.

    Why this exists
    Health labels must remain logically ordered for deterministic classification.
    """
    try:
        payload = cast(
            JsonDict,
            {
                "thresholds": {
                    "temp_warn_c": 75.0,
                    "temp_bad_c": 90.0,
                    "rssi_warn_dbm": -70,
                    "rssi_bad_dbm": -80,
                    "disk_free_warn_percent": 15.0,
                    "disk_free_bad_percent": 5.0,
                    "memory_free_warn_percent": 20.0,
                    "memory_free_bad_percent": 10.0,
                    "backup_warn_days": 7,
                    "backup_bad_days": 30,
                    "health_excellent_min_percent": 80.0,
                    "health_good_min_percent": 80.0,
                    "health_fair_min_percent": 60.0,
                    "ssd_unsafe_shutdowns_warn_count": 1,
                    "ssd_media_errors_bad_count": 1,
                }
            },
        )
        with pytest.raises(RuntimeError):
            parse_thresholds(payload)
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
            f"{MODULE_PATH}:test_parse_thresholds_rejects_invalid_health_band_ordering failed: {exc}"
        ) from exc
