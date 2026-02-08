import json
from pathlib import Path
from typing import cast

import pytest

from mac_health_checkup.core.config import get_config_value, require_int, reset_config_cache
from mac_health_checkup.core.config.parsing.features import parse_api
from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_config.py"


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
