from __future__ import annotations

import errno
from dataclasses import dataclass
from typing import Callable

import pytest

import mac_health_checkup.app.backend.server as srv
from mac_health_checkup.core.config import ApiConfig

MODULE_PATH = "tests/test_backend_server_unit.py"


def _build_api_config(*, tls_enabled: bool, bind_host: str = "127.0.0.1") -> ApiConfig:
    """
    Summary
    Execute `_build_api_config` for its module-level responsibility.

    Inputs
    tls_enabled: keyword-only `bool` parameter.
    bind_host: keyword-only `str` parameter with a default.

    Outputs
    Returns `ApiConfig`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_backend_server_unit.py:_build_api_config` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_backend_server_unit.py`.

    Why this exists
    Keeps `_build_api_config` explicit, testable, and maintainable.
    """
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
                """
                Summary
                Execute `__init__` for its module-level responsibility.

                Inputs
                addr: `tuple[str, int]` parameter from the function signature.
                _handler_factory: `object` parameter from the function signature.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_backend_server_unit.py:__init__` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_backend_server_unit.py`.

                Why this exists
                Keeps `__init__` explicit, testable, and maintainable.
                """
                attempts.append(int(addr[1]))
                if len(attempts) == 1:
                    raise in_use
                self.server_address = addr
                self.daemon_threads = False
                self.socket: object = object()

            def serve_forever(self) -> None:
                """
                Summary
                Execute `serve_forever` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_backend_server_unit.py:serve_forever` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_backend_server_unit.py`.

                Why this exists
                Keeps `serve_forever` explicit, testable, and maintainable.
                """
                return

            def shutdown(self) -> None:
                """
                Summary
                Execute `shutdown` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_backend_server_unit.py:shutdown` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_backend_server_unit.py`.

                Why this exists
                Keeps `shutdown` explicit, testable, and maintainable.
                """
                return

            def server_close(self) -> None:
                """
                Summary
                Execute `server_close` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_backend_server_unit.py:server_close` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_backend_server_unit.py`.

                Why this exists
                Keeps `server_close` explicit, testable, and maintainable.
                """
                return

        @dataclass
        class _StubThread:
            target: Callable[[], None]
            name: str
            daemon: bool
            started: bool = False
            joined: bool = False

            def start(self) -> None:
                """
                Summary
                Execute `start` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_backend_server_unit.py:start` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_backend_server_unit.py`.

                Why this exists
                Keeps `start` explicit, testable, and maintainable.
                """
                self.started = True

            def join(self, *, timeout: float | None = None) -> None:
                """
                Summary
                Execute `join` for its module-level responsibility.

                Inputs
                timeout: keyword-only `float | None` parameter with a default.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_backend_server_unit.py:join` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_backend_server_unit.py`.

                Why this exists
                Keeps `join` explicit, testable, and maintainable.
                """
                _ = timeout
                self.joined = True

        def _thread_factory(*, target: Callable[[], None], name: str, daemon: bool) -> _StubThread:
            """
            Summary
            Execute `_thread_factory` for its module-level responsibility.

            Inputs
            target: keyword-only `Callable[[], None]` parameter.
            name: keyword-only `str` parameter.
            daemon: keyword-only `bool` parameter.

            Outputs
            Returns `_StubThread`.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `tests/test_backend_server_unit.py:_thread_factory` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_backend_server_unit.py`.

            Why this exists
            Keeps `_thread_factory` explicit, testable, and maintainable.
            """
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
            f"{MODULE_PATH}:test_server_start_stop_uses_bind_retry_and_thread failed: {exc}"
        ) from exc


@pytest.mark.parametrize("failure_stage", ["tls", "thread"])
def test_server_start_failure_closes_socket_and_resets_state(
    monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    """
    Summary
    Ensure failures after binding close the HTTP server and leave lifecycle state uncommitted.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    failure_stage: Startup stage that raises after the server binds.

    Outputs
    None.

    Side effects
    Patches HTTP server, TLS context, and thread creation to avoid real sockets and threads.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises transactional cleanup in `SnapshotApiServer.start`.

    Why this exists
    TLS wrapping or thread startup can fail after a port is bound; those failures must not leak the socket or publish
    partially initialized lifecycle state.
    """
    try:
        api = _build_api_config(tls_enabled=failure_stage == "tls")
        server = srv.SnapshotApiServer({}, api)
        created_servers: list[_StubFailureHTTPD] = []

        class _StubFailureHTTPD:
            def __init__(self, addr: tuple[str, int], _handler_factory: object) -> None:
                """
                Summary
                Record a bound stub server for cleanup assertions.

                Inputs
                addr: Requested bind address. `_handler_factory`: Unused handler factory.

                Outputs
                None.

                Side effects
                Appends this instance to the test's server registry.

                Error handling
                None.

                Ties to other methods
                Replaces `_ReusableThreadingHTTPServer` in this test.

                Why this exists
                Startup cleanup needs observable socket ownership without opening a real port.
                """
                self.server_address = addr
                self.daemon_threads = False
                self.socket: object = object()
                self.closed = False
                created_servers.append(self)

            def serve_forever(self) -> None:
                """
                Summary
                Provide the server loop callback expected by the production thread.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None.

                Error handling
                None.

                Ties to other methods
                Passed to the stub thread during server startup.

                Why this exists
                The lifecycle test needs the server interface without serving requests.
                """
                return

            def server_close(self) -> None:
                """
                Summary
                Record that startup cleanup closed the bound server.

                Inputs
                None.

                Outputs
                None.

                Side effects
                Sets the observable closed flag.

                Error handling
                None.

                Ties to other methods
                Called by transactional startup cleanup.

                Why this exists
                The regression assertion must prove the socket ownership was released.
                """
                self.closed = True

        class _FailingTLSContext:
            def wrap_socket(self, _socket: object, *, server_side: bool) -> object:
                """
                Summary
                Inject a deterministic TLS wrapping failure.

                Inputs
                `_socket`: Bound socket placeholder. server_side: TLS role flag.

                Outputs
                Never returns.

                Side effects
                None.

                Error handling
                Always raises `OSError`.

                Ties to other methods
                Exercises the post-bind TLS failure path in `SnapshotApiServer.start`.

                Why this exists
                TLS setup can fail after a real socket has already been acquired.
                """
                _ = server_side
                raise OSError("TLS wrapping failed")

        @dataclass
        class _StubFailureThread:
            target: Callable[[], None]
            name: str
            daemon: bool

            def start(self) -> None:
                """
                Summary
                Inject a deterministic worker-thread start failure.

                Inputs
                None.

                Outputs
                Never returns.

                Side effects
                None.

                Error handling
                Always raises `RuntimeError`.

                Ties to other methods
                Exercises the final post-bind failure stage in `SnapshotApiServer.start`.

                Why this exists
                Thread creation can fail after TLS and socket setup have succeeded.
                """
                raise RuntimeError("thread start failed")

        def _thread_factory(*, target: Callable[[], None], name: str, daemon: bool) -> _StubFailureThread:
            """
            Summary
            Build the failing thread stub with the production constructor shape.

            Inputs
            target: Server loop callback. name: Thread name. daemon: Daemon flag.

            Outputs
            Configured `_StubFailureThread`.

            Side effects
            None.

            Error handling
            None.

            Ties to other methods
            Replaces `threading.Thread` in the thread-failure case.

            Why this exists
            The test must intercept thread startup without changing server construction code.
            """
            return _StubFailureThread(target=target, name=name, daemon=daemon)

        monkeypatch.setattr(srv, "_ReusableThreadingHTTPServer", _StubFailureHTTPD)
        monkeypatch.setattr(srv, "validate_api_config_for_server", lambda _api: None)
        monkeypatch.setattr(srv, "build_handler_factory", lambda _handlers, _api: object())
        monkeypatch.setattr(srv, "build_tls_server_context", lambda _cert, _key: _FailingTLSContext())
        monkeypatch.setattr("mac_health_checkup.app.backend.server.threading.Thread", _thread_factory)

        with pytest.raises(RuntimeError, match="Failed to start server"):
            server.start()

        assert len(created_servers) == 1
        assert created_servers[0].closed is True
        assert server._httpd is None
        assert server._thread is None
        assert server._bound_host is None
        assert server._bound_port is None
        assert server.url().endswith(f":{api.port}")
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
            f"{MODULE_PATH}:test_server_start_failure_closes_socket_and_resets_state failed: {exc}"
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
            """
            Summary
            Execute `_fake_time` for its module-level responsibility.

            Inputs
            None.

            Outputs
            Returns `float`.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `tests/test_backend_server_unit.py:_fake_time` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_backend_server_unit.py`.

            Why this exists
            Keeps `_fake_time` explicit, testable, and maintainable.
            """
            return times.pop(0) if times else 999.0

        attempts: list[int] = []

        class _Conn:
            def __enter__(self) -> "_Conn":
                """
                Summary
                Execute `__enter__` for its module-level responsibility.

                Inputs
                None.

                Outputs
                Returns `'_Conn'`.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_backend_server_unit.py:__enter__` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_backend_server_unit.py`.

                Why this exists
                Keeps `__enter__` explicit, testable, and maintainable.
                """
                return self

            def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                """
                Summary
                Execute `__exit__` for its module-level responsibility.

                Inputs
                exc_type: `object` parameter from the function signature.
                exc: `object` parameter from the function signature.
                tb: `object` parameter from the function signature.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_backend_server_unit.py:__exit__` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_backend_server_unit.py`.

                Why this exists
                Keeps `__exit__` explicit, testable, and maintainable.
                """
                _ = exc_type
                _ = exc
                _ = tb
                return

        def _fake_create_connection(addr: tuple[str, int], timeout: float) -> _Conn:
            """
            Summary
            Execute `_fake_create_connection` for its module-level responsibility.

            Inputs
            addr: `tuple[str, int]` parameter from the function signature.
            timeout: `float` parameter from the function signature.

            Outputs
            Returns `_Conn`.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `tests/test_backend_server_unit.py:_fake_create_connection` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_backend_server_unit.py`.

            Why this exists
            Keeps `_fake_create_connection` explicit, testable, and maintainable.
            """
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
        raise AssertionError(f"{MODULE_PATH}:test_wait_until_ready_uses_bounded_retry failed: {exc}") from exc
