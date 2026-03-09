from __future__ import annotations

from pathlib import Path

import pytest

from mac_health_checkup.app.backend.security.throttling import RequestThrottler
from mac_health_checkup.app.backend.security.validation import validate_api_config_for_server
from mac_health_checkup.core.config import ApiConfig

MODULE_PATH = "tests/test_api_security.py"


def _api_config(**overrides: object) -> ApiConfig:
    """
    Summary
    Build a baseline ApiConfig for unit tests with secure defaults.

    Inputs
    overrides apply on top of the baseline config.

    Outputs
    ApiConfig instance.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and helper context when object construction fails.

    Ties to other methods
    Used by tests in this module.

    Why this exists
    Keeps tests compact and deterministic while exercising validation behavior.
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
            pairing_qr_enabled=True,
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
    Summary
    Ensure enabling the API with a placeholder token fails fast.

    Inputs
    ApiConfig with a blocked placeholder token.

    Outputs
    Assertion that validation raises.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    Prevents accidental insecure exposure when users forget to set a token.
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
    Summary
    Ensure binding to non-loopback requires explicit LAN opt-in.

    Inputs
    ApiConfig binding to 0.0.0.0 without allow_lan.

    Outputs
    Assertion that validation raises.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    Makes unsafe exposure a deliberate action instead of an accident.
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
    Summary
    Ensure LAN exposure requires a stronger token baseline.

    Inputs
    allow_lan enabled with a short token.

    Outputs
    Assertion that validation raises.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    Reduces the chance that a weak token can be guessed on shared networks.
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
    Summary
    Ensure repeated auth failures trigger a temporary ban.

    Inputs
    Multiple auth failure records for the same IP.

    Outputs
    Assertion that allow_request denies after threshold is reached.

    Side effects
    Mutates the throttler's in-memory state.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `RequestThrottler.record_auth_failure` and `RequestThrottler.allow_request`.

    Why this exists
    Protects the API from brute-force guessing and reduces noisy retries.
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
    Summary
    Ensure TLS cannot be enabled without valid certificate and key files.

    Inputs
    ApiConfig with tls_enabled and non-existent paths.

    Outputs
    Assertion that validation raises.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    Prevents accidental misconfiguration that would otherwise fall back to insecure HTTP.
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


def test_validate_api_config_rejects_disabled_api() -> None:
    """
    Summary
    Ensure validation fails fast when the API server is not enabled.

    Inputs
    ApiConfig with `enabled=False`.

    Outputs
    Assertion that validation raises.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    Server startup should never proceed with contradictory configuration.
    """
    try:
        api = _api_config(enabled=False)
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
        raise AssertionError(f"{MODULE_PATH}:test_validate_api_config_rejects_disabled_api failed: {exc}") from exc


def test_validate_api_config_rejects_blank_bind_host() -> None:
    """
    Summary
    Ensure an empty bind host is rejected.

    Inputs
    ApiConfig with whitespace-only `bind_host`.

    Outputs
    Assertion that validation raises.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    A missing bind host should fail with an actionable error before socket setup.
    """
    try:
        api = _api_config(bind_host="   ")
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
        raise AssertionError(f"{MODULE_PATH}:test_validate_api_config_rejects_blank_bind_host failed: {exc}") from exc


def test_validate_api_config_rejects_blank_auth_token() -> None:
    """
    Summary
    Ensure an empty auth token is rejected.

    Inputs
    ApiConfig with whitespace-only `auth_token`.

    Outputs
    Assertion that validation raises.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    The auth boundary should fail closed when credentials are missing.
    """
    try:
        api = _api_config(auth_token=" ")
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
        raise AssertionError(f"{MODULE_PATH}:test_validate_api_config_rejects_blank_auth_token failed: {exc}") from exc


def test_validate_api_config_requires_tls_or_explicit_insecure_lan() -> None:
    """
    Summary
    Ensure LAN exposure requires TLS or an explicit insecure override.

    Inputs
    ApiConfig with LAN enabled, TLS disabled, and insecure-LAN override disabled.

    Outputs
    Assertion that validation raises.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    Avoids accidental plaintext exposure on local networks.
    """
    try:
        api = _api_config(
            bind_host="0.0.0.0",
            allow_lan=True,
            tls_enabled=False,
            allow_insecure_http_lan=False,
            auth_token="x" * 40,
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
            f"{MODULE_PATH}:test_validate_api_config_requires_tls_or_explicit_insecure_lan failed: {exc}"
        ) from exc


def test_validate_api_config_rejects_tls_enabled_missing_key_after_existing_cert(tmp_path: Path) -> None:
    """
    Summary
    Ensure key-path validation runs when the certificate file exists.

    Inputs
    Temporary cert file and missing key file path.

    Outputs
    Assertion that validation raises.

    Side effects
    Writes a temporary certificate file.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    Both TLS paths should be validated independently with clear failures.
    """
    try:
        cert_path = tmp_path / "cert.pem"
        cert_path.write_text("dummy-cert", encoding="utf-8")
        api = _api_config(
            tls_enabled=True,
            tls_cert_path=str(cert_path),
            tls_key_path=str(tmp_path / "missing-key.pem"),
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
            f"{MODULE_PATH}:test_validate_api_config_rejects_tls_enabled_missing_key_after_existing_cert failed: {exc}"
        ) from exc


def test_validate_api_config_tls_enabled_uses_certificate_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Summary
    Ensure TLS validation reads certificate fingerprint when cert and key files exist.

    Inputs
    Temporary cert and key files with a monkeypatched fingerprint helper.

    Outputs
    Assertion that validation succeeds and helper is called once.

    Side effects
    Writes temporary TLS files and monkeypatches helper behavior.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    Startup should verify TLS material before accepting traffic.
    """
    try:
        cert_path = tmp_path / "cert.pem"
        key_path = tmp_path / "key.pem"
        cert_path.write_text("dummy-cert", encoding="utf-8")
        key_path.write_text("dummy-key", encoding="utf-8")
        calls: list[str] = []

        def _fingerprint(path: object) -> str:
            calls.append(str(path))
            return "aa:bb"

        monkeypatch.setattr(
            "mac_health_checkup.app.backend.security.validation.certificate_sha256_fingerprint_from_pem",
            _fingerprint,
        )

        api = _api_config(
            tls_enabled=True,
            tls_cert_path=str(cert_path),
            tls_key_path=str(key_path),
        )
        validate_api_config_for_server(api)
        assert calls == [str(cert_path)]
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
            f"{MODULE_PATH}:test_validate_api_config_tls_enabled_uses_certificate_fingerprint failed: {exc}"
        ) from exc


@pytest.mark.parametrize("timeout_sec", [0, 121])
def test_validate_api_config_rejects_out_of_range_request_timeout(timeout_sec: int) -> None:
    """
    Summary
    Ensure request timeout bounds are enforced.

    Inputs
    `timeout_sec` outside the accepted range.

    Outputs
    Assertion that validation raises.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `validate_api_config_for_server`.

    Why this exists
    Request timeout bounds protect API responsiveness and avoid hangs.
    """
    try:
        api = _api_config(request_timeout_sec=timeout_sec)
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
            f"{MODULE_PATH}:test_validate_api_config_rejects_out_of_range_request_timeout failed: {exc}"
        ) from exc


def test_throttler_rate_limit_returns_retry_and_recovers_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure rate limiting returns retry hints and recovers after the sliding window.

    Inputs
    Deterministic monotonic timestamps and low request-rate limits.

    Outputs
    Assertions on allow/deny decisions and retry timing.

    Side effects
    Monkeypatches monotonic time source.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `RequestThrottler.allow_request` and window-pruning logic.

    Why this exists
    Retry behavior should be deterministic for clients and operational tooling.
    """
    try:
        api = _api_config(rate_limit_requests_per_minute=2)
        throttler = RequestThrottler(api)
        ticks = iter([100.0, 101.0, 102.0, 161.0])
        monkeypatch.setattr(
            "mac_health_checkup.app.backend.security.throttling.time.monotonic",
            lambda: next(ticks),
        )

        allowed_1, retry_1 = throttler.allow_request("192.0.2.30")
        allowed_2, retry_2 = throttler.allow_request("192.0.2.30")
        allowed_3, retry_3 = throttler.allow_request("192.0.2.30")
        allowed_4, retry_4 = throttler.allow_request("192.0.2.30")

        assert allowed_1 is True and retry_1 == 0
        assert allowed_2 is True and retry_2 == 0
        assert allowed_3 is False and retry_3 >= 1
        assert allowed_4 is True and retry_4 == 0
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
            f"{MODULE_PATH}:test_throttler_rate_limit_returns_retry_and_recovers_after_window failed: {exc}"
        ) from exc
