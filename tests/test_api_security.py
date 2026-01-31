from __future__ import annotations

import pytest

from mac_health_checkup.app.backend.security.throttling import RequestThrottler
from mac_health_checkup.app.backend.security.validation import validate_api_config_for_server
from mac_health_checkup.core.config import ApiConfig

MODULE_PATH = "tests/test_api_security.py"


def _api_config(**overrides: object) -> ApiConfig:
    """
    Purpose: Build a baseline ApiConfig for unit tests with secure defaults.
    Ties: Used by tests in this module.
    Inputs: overrides apply on top of the baseline config.
    Outputs: ApiConfig instance.
    Side effects: None.
    Why: Keeps tests compact and deterministic while exercising validation behavior.
    """
    try:
        base = ApiConfig(
            enabled=True,
            bind_host="127.0.0.1",
            port=7878,
            allow_lan=False,
            allow_insecure_http_lan=False,
            tls_enabled=False,
            tls_cert_path=".local/tls/agent-cert.pem",
            tls_key_path=".local/tls/agent-key.pem",
            auth_token="unit-test-token-0123456789-abcdefghijklmnopqrstuvwxyz",
            min_auth_token_length=24,
            blocked_auth_tokens=["change-me", "changeme", "password", "token"],
            rate_limit_requests_per_minute=120,
            max_auth_failures_per_minute=10,
            auth_ban_seconds=60,
            request_timeout_sec=10,
        )
        data = base.__dict__ | dict(overrides)
        return ApiConfig(**data)
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
        raise AssertionError(f"{MODULE_PATH}:_api_config failed: {exc}") from exc


def test_validate_api_config_rejects_placeholder_token() -> None:
    """
    Purpose: Ensure enabling the API with a placeholder token fails fast.
    Ties: Exercises validate_api_config_for_server.
    Inputs: ApiConfig with a blocked placeholder token.
    Outputs: Assertion that validation raises.
    Side effects: None.
    Why: Prevents accidental insecure exposure when users forget to set a token.
    """
    try:
        api = _api_config(auth_token="change-me")
        with pytest.raises(RuntimeError):
            validate_api_config_for_server(api)
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
            f"{MODULE_PATH}:test_validate_api_config_rejects_placeholder_token failed: {exc}"
        ) from exc


def test_validate_api_config_requires_allow_lan_for_non_loopback() -> None:
    """
    Purpose: Ensure binding to non-loopback requires explicit LAN opt-in.
    Ties: Exercises validate_api_config_for_server.
    Inputs: ApiConfig binding to 0.0.0.0 without allow_lan.
    Outputs: Assertion that validation raises.
    Side effects: None.
    Why: Makes unsafe exposure a deliberate action instead of an accident.
    """
    try:
        api = _api_config(bind_host="0.0.0.0", allow_lan=False)
        with pytest.raises(RuntimeError):
            validate_api_config_for_server(api)
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
            f"{MODULE_PATH}:test_validate_api_config_requires_allow_lan_for_non_loopback failed: {exc}"
        ) from exc


def test_validate_api_config_requires_strong_token_for_lan() -> None:
    """
    Purpose: Ensure LAN exposure requires a stronger token baseline.
    Ties: Exercises validate_api_config_for_server.
    Inputs: allow_lan enabled with a short token.
    Outputs: Assertion that validation raises.
    Side effects: None.
    Why: Reduces the chance that a weak token can be guessed on shared networks.
    """
    try:
        api = _api_config(
            bind_host="0.0.0.0",
            allow_lan=True,
            allow_insecure_http_lan=True,
            auth_token="x" * 24,
        )
        with pytest.raises(RuntimeError):
            validate_api_config_for_server(api)
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
            f"{MODULE_PATH}:test_validate_api_config_requires_strong_token_for_lan failed: {exc}"
        ) from exc


def test_throttler_bans_after_failed_auths() -> None:
    """
    Purpose: Ensure repeated auth failures trigger a temporary ban.
    Ties: Exercises RequestThrottler.record_auth_failure and allow_request.
    Inputs: Multiple auth failure records for the same IP.
    Outputs: Assertion that allow_request denies after threshold is reached.
    Side effects: Mutates the throttler's in-memory state.
    Why: Protects the API from brute-force guessing and reduces noisy retries.
    """
    try:
        api = _api_config(
            rate_limit_requests_per_minute=10_000, max_auth_failures_per_minute=3, auth_ban_seconds=5
        )
        throttler = RequestThrottler(api)
        client_ip = "192.0.2.10"

        ok, retry = throttler.allow_request(client_ip)
        assert ok and retry == 0

        throttler.record_auth_failure(client_ip)
        throttler.record_auth_failure(client_ip)
        throttler.record_auth_failure(client_ip)

        ok, retry = throttler.allow_request(client_ip)
        assert not ok
        assert retry >= 1
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
        raise AssertionError(f"{MODULE_PATH}:test_throttler_bans_after_failed_auths failed: {exc}") from exc


def test_validate_api_config_rejects_tls_enabled_without_files() -> None:
    """
    Purpose: Ensure TLS cannot be enabled without valid certificate and key files.
    Ties: Exercises validate_api_config_for_server.
    Inputs: ApiConfig with tls_enabled and non-existent paths.
    Outputs: Assertion that validation raises.
    Side effects: None.
    Why: Prevents accidental misconfiguration that would otherwise fall back to insecure HTTP.
    """
    try:
        api = _api_config(
            tls_enabled=True,
            tls_cert_path=".local/tls/missing-cert.pem",
            tls_key_path=".local/tls/missing-key.pem",
        )
        with pytest.raises(RuntimeError):
            validate_api_config_for_server(api)
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
            f"{MODULE_PATH}:test_validate_api_config_rejects_tls_enabled_without_files failed: {exc}"
        ) from exc
