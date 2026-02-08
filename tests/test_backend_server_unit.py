from __future__ import annotations

import errno
from dataclasses import dataclass
from typing import Callable

import pytest

import mac_health_checkup.app.backend.server as srv
from mac_health_checkup.core.config import ApiConfig

MODULE_PATH = "tests/test_backend_server_unit.py"


def _build_api_config(*, tls_enabled: bool, bind_host: str = "127.0.0.1") -> ApiConfig:
    return ApiConfig(
        enabled=True,
        bind_host=bind_host,
        port=7878,
        allow_lan=False,
        allow_insecure_http_lan=False,
        tls_enabled=tls_enabled,
        tls_cert_path="~/.local/test-cert.pem",
        tls_key_path="~/.local/test-key.pem",
        auth_token="test-token-000000000000000000000000",
        min_auth_token_length=24,
        blocked_auth_tokens=[],
        rate_limit_requests_per_minute=60,
        max_auth_failures_per_minute=5,
        auth_ban_seconds=5,
        request_timeout_sec=5,
        pairing_qr_enabled=False,
    )


def test_url_normalizes_wildcard_host_and_tls_scheme() -> None:
    """
    Summary
    Ensure server URL rendering uses localhost for wildcard binds and chooses scheme from TLS.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `SnapshotApiServer.url`.

    Why this exists
    Pairing instructions should be safe and deterministic even when binding to 0.0.0.0.
    """
    try:
        http_server = srv.SnapshotApiServer({}, _build_api_config(tls_enabled=False, bind_host="0.0.0.0"))
        assert http_server.url().startswith("http://127.0.0.1:")

        https_server = srv.SnapshotApiServer({}, _build_api_config(tls_enabled=True, bind_host="127.0.0.1"))
        assert https_server.url().startswith("https://127.0.0.1:")
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_url_normalizes_wildcard_host_and_tls_scheme failed: {exc}"
        ) from exc


def test_tls_fingerprint_is_none_when_tls_disabled() -> None:
    """
    Summary
    Ensure fingerprint helper returns None when TLS is disabled.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `SnapshotApiServer.tls_certificate_fingerprint_sha256`.

    Why this exists
    Call sites should not need to special-case TLS disabled state.
    """
    try:
        api = _build_api_config(tls_enabled=False)
        server = srv.SnapshotApiServer({}, api)
        assert server.tls_certificate_fingerprint_sha256() is None
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_tls_fingerprint_is_none_when_tls_disabled failed: {exc}"
        ) from exc


def test_server_start_stop_uses_bind_retry_and_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure server start retries on EADDRINUSE and stop clears state without binding a real socket.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches HTTP server and thread creation to avoid network and background loops.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `SnapshotApiServer.start` and `SnapshotApiServer.stop`.

    Why this exists
    Start/stop behavior is central to serve mode reliability and must be testable without privileged binds.
    """
    try:
        api = _build_api_config(tls_enabled=False)
        server = srv.SnapshotApiServer({}, api)

        class _BindInUse(OSError):
            pass

        in_use = _BindInUse("in use")
        in_use.errno = errno.EADDRINUSE

        attempts: list[int] = []

        class _StubHTTPD:
            def __init__(self, addr: tuple[str, int], _handler_factory: object) -> None:
                attempts.append(int(addr[1]))
                if len(attempts) == 1:
                    raise in_use
                self.server_address = addr
                self.daemon_threads = False
                self.socket: object = object()

            def serve_forever(self) -> None:
                return

            def shutdown(self) -> None:
                return

            def server_close(self) -> None:
                return

        @dataclass
        class _StubThread:
            target: Callable[[], None]
            name: str
            daemon: bool
            started: bool = False
            joined: bool = False

            def start(self) -> None:
                self.started = True

            def join(self, *, timeout: float | None = None) -> None:
                _ = timeout
                self.joined = True

        def _thread_factory(*, target: Callable[[], None], name: str, daemon: bool) -> _StubThread:
            return _StubThread(target=target, name=name, daemon=daemon)

        monkeypatch.setattr(srv, "_ReusableThreadingHTTPServer", _StubHTTPD)
        monkeypatch.setattr("mac_health_checkup.app.backend.server.threading.Thread", _thread_factory)
        monkeypatch.setattr(srv, "validate_api_config_for_server", lambda _api: None)
        monkeypatch.setattr(srv, "build_handler_factory", lambda _handlers, _api: object())

        server.start()
        assert attempts[0] == api.port
        assert attempts[1] == api.port + 1
        assert server.url().endswith(f":{api.port + 1}")

        server.stop()
        assert server.url().endswith(f":{api.port}")
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_server_start_stop_uses_bind_retry_and_thread failed: {exc}"
        ) from exc


def test_wait_until_ready_uses_bounded_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure wait_until_ready returns true when the socket becomes reachable before the deadline.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches time and socket.create_connection to avoid real networking.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `wait_until_ready`.

    Why this exists
    Readiness waits should be deterministic and should not hang indefinitely in tests or automation.
    """
    try:
        times = [0.0, 0.05, 0.10, 0.15, 0.20]

        def _fake_time() -> float:
            return times.pop(0) if times else 999.0

        attempts: list[int] = []

        class _Conn:
            def __enter__(self) -> "_Conn":
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                _ = exc_type
                _ = exc
                _ = tb
                return

        def _fake_create_connection(addr: tuple[str, int], timeout: float) -> _Conn:
            _ = timeout
            attempts.append(addr[1])
            if len(attempts) < 3:
                raise OSError("not ready")
            return _Conn()

        monkeypatch.setattr("mac_health_checkup.app.backend.server.time.time", _fake_time)
        monkeypatch.setattr("mac_health_checkup.app.backend.server.time.sleep", lambda _s: None)
        monkeypatch.setattr(
            "mac_health_checkup.app.backend.server.socket.create_connection", _fake_create_connection
        )

        assert srv.wait_until_ready("http://127.0.0.1:1234", timeout_sec=1) is True
        assert len(attempts) == 3
    except Exception as exc:
        raise AssertionError(f"{MODULE_PATH}:test_wait_until_ready_uses_bounded_retry failed: {exc}") from exc
