from __future__ import annotations

import io
import json
from dataclasses import dataclass
from http import HTTPStatus
from typing import Protocol, cast

import pytest

import mac_health_checkup.app.backend.http.handler_factory as hf
from mac_health_checkup.core.config import ApiConfig
from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_backend_http_handler_factory_unit.py"


@dataclass
class _CapturedResponse:
    status: int | None
    headers: list[tuple[str, str]]
    body: bytes


class _DummyConnection:
    def __init__(self) -> None:
        """
        Summary
        Execute `__init__` for its module-level responsibility.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:__init__` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `__init__` explicit, testable, and maintainable.
        """
        self.timeouts: list[float] = []

    def settimeout(self, value: float) -> None:
        """
        Summary
        Execute `settimeout` for its module-level responsibility.

        Inputs
        value: `float` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:settimeout` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `settimeout` explicit, testable, and maintainable.
        """
        self.timeouts.append(float(value))


class _StubThrottler:
    def __init__(self, _api: ApiConfig) -> None:
        """
        Summary
        Execute `__init__` for its module-level responsibility.

        Inputs
        _api: `ApiConfig` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:__init__` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `__init__` explicit, testable, and maintainable.
        """
        self.allowed: bool = True
        self.retry_after: int = 0
        self.auth_failures: int = 0
        self.auth_successes: int = 0

    def allow_request(self, _client_ip: str) -> tuple[bool, int]:
        """
        Summary
        Execute `allow_request` for its module-level responsibility.

        Inputs
        _client_ip: `str` parameter from the function signature.

        Outputs
        Returns `tuple[bool, int]`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:allow_request` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `allow_request` explicit, testable, and maintainable.
        """
        return self.allowed, int(self.retry_after)

    def record_auth_failure(self, _client_ip: str) -> None:
        """
        Summary
        Execute `record_auth_failure` for its module-level responsibility.

        Inputs
        _client_ip: `str` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:record_auth_failure` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `record_auth_failure` explicit, testable, and maintainable.
        """
        self.auth_failures += 1

    def record_auth_success(self, _client_ip: str) -> None:
        """
        Summary
        Execute `record_auth_success` for its module-level responsibility.

        Inputs
        _client_ip: `str` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:record_auth_success` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `record_auth_success` explicit, testable, and maintainable.
        """
        self.auth_successes += 1


class _MutableHandler(Protocol):
    client_address: tuple[str, int]
    connection: _DummyConnection
    path: str
    headers: dict[str, str]
    wfile: io.BytesIO

    send_response: object
    send_header: object
    end_headers: object

    def do_GET(self) -> None:
        """
        Summary
        Execute `do_GET` for its module-level responsibility.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:do_GET` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `do_GET` explicit, testable, and maintainable.
        """
        ...


def _build_api_config() -> ApiConfig:
    """
    Summary
    Execute `_build_api_config` for its module-level responsibility.

    Inputs
    None.

    Outputs
    Returns `ApiConfig`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:_build_api_config` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

    Why this exists
    Keeps `_build_api_config` explicit, testable, and maintainable.
    """
    return ApiConfig(
        enabled=True,
        bind_host="127.0.0.1",
        port=0,
        allow_lan=False,
        allow_insecure_http_lan=False,
        tls_enabled=False,
        tls_cert_path="",
        tls_key_path="",
        auth_token="test-token-000000000000000000000000",
        min_auth_token_length=24,
        blocked_auth_tokens=[],
        rate_limit_requests_per_minute=60,
        max_auth_failures_per_minute=5,
        auth_ban_seconds=5,
        request_timeout_sec=5,
        pairing_qr_enabled=False,
    )


def _new_handler_instance(
    handler_cls: type[object], *, path: str, authorization: str | None
) -> tuple[_MutableHandler, _CapturedResponse]:
    """
    Summary
    Execute `_new_handler_instance` for its module-level responsibility.

    Inputs
    handler_cls: `type[object]` parameter from the function signature.
    path: keyword-only `str` parameter.
    authorization: keyword-only `str | None` parameter.

    Outputs
    Returns `tuple[_MutableHandler, _CapturedResponse]`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:_new_handler_instance` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

    Why this exists
    Keeps `_new_handler_instance` explicit, testable, and maintainable.
    """
    captured = _CapturedResponse(status=None, headers=[], body=b"")

    handler_obj = object.__new__(handler_cls)
    handler = cast(_MutableHandler, handler_obj)
    handler.client_address = ("127.0.0.1", 12345)
    handler.connection = _DummyConnection()
    handler.path = path
    handler.headers = {"Authorization": authorization} if authorization is not None else {}
    handler.wfile = io.BytesIO()

    def _send_response(status: int | HTTPStatus) -> None:
        """
        Summary
        Execute `_send_response` for its module-level responsibility.

        Inputs
        status: `int | HTTPStatus` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:_send_response` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `_send_response` explicit, testable, and maintainable.
        """
        captured.status = int(status)

    def _send_header(key: str, value: str) -> None:
        """
        Summary
        Execute `_send_header` for its module-level responsibility.

        Inputs
        key: `str` parameter from the function signature.
        value: `str` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:_send_header` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `_send_header` explicit, testable, and maintainable.
        """
        captured.headers.append((str(key), str(value)))

    def _end_headers() -> None:
        """
        Summary
        Execute `_end_headers` for its module-level responsibility.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:_end_headers` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

        Why this exists
        Keeps `_end_headers` explicit, testable, and maintainable.
        """
        return

    handler.send_response = _send_response
    handler.send_header = _send_header
    handler.end_headers = _end_headers
    return handler, captured


def _body_json(handler: _MutableHandler) -> JsonDict:
    """
    Summary
    Execute `_body_json` for its module-level responsibility.

    Inputs
    handler: `_MutableHandler` parameter from the function signature.

    Outputs
    Returns `JsonDict`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:_body_json` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

    Why this exists
    Keeps `_body_json` explicit, testable, and maintainable.
    """
    raw = handler.wfile.getvalue().decode("utf-8")
    return cast(JsonDict, json.loads(raw))


def test_is_client_disconnect_detects_common_errors() -> None:
    """
    Summary
    Ensure client disconnect detection covers common pipe/reset errors.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `mac_health_checkup.app.backend.http.handler_factory._is_client_disconnect`.

    Why this exists
    The handler must not attempt to send a second response after a broken pipe.
    """
    try:
        assert hf._is_client_disconnect(BrokenPipeError()) is True
        assert hf._is_client_disconnect(ConnectionResetError()) is True
        assert hf._is_client_disconnect(ValueError("x")) is False
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
            f"{MODULE_PATH}:test_is_client_disconnect_detects_common_errors failed: {exc}"
        ) from exc


def test_handler_health_endpoint_returns_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure `/v1/health` returns a JSON ok payload.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches RequestThrottler to avoid time-based state.

    Error handling
    Raises AssertionError with context on failures.

    Ties to other methods
    Exercises `build_handler_factory` and `do_GET` for `/v1/health`.

    Why this exists
    The health endpoint is used for readiness checks and should be stable.
    """
    try:
        api = _build_api_config()
        stub = _StubThrottler(api)

        monkeypatch.setattr(hf, "RequestThrottler", lambda _api: stub)
        handler_cls = hf.build_handler_factory({}, api)
        handler, captured = _new_handler_instance(handler_cls, path="/v1/health", authorization=None)
        handler.do_GET()

        assert captured.status == int(HTTPStatus.OK)
        payload = _body_json(handler)
        assert payload.get("ok") is True
        assert payload.get("service") == "mac-health-checkup"
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
        raise AssertionError(f"{MODULE_PATH}:test_handler_health_endpoint_returns_ok failed: {exc}") from exc


def test_handler_rate_limits_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure rate limiting returns 429 and includes Retry-After header.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches RequestThrottler to force a deny decision.

    Error handling
    Raises AssertionError with context on failures.

    Ties to other methods
    Exercises `do_GET` throttling gate.

    Why this exists
    Rate limiting is a primary safety control for LAN usage.
    """
    try:
        api = _build_api_config()
        stub = _StubThrottler(api)
        stub.allowed = False
        stub.retry_after = 7

        monkeypatch.setattr(hf, "RequestThrottler", lambda _api: stub)
        handler_cls = hf.build_handler_factory({}, api)
        handler, captured = _new_handler_instance(handler_cls, path="/v1/health", authorization=None)
        handler.do_GET()

        assert captured.status == int(HTTPStatus.TOO_MANY_REQUESTS)
        assert ("Retry-After", "7") in captured.headers
        payload = _body_json(handler)
        assert payload.get("error") == "rate_limited"
        assert payload.get("error_code") == "rate_limited"
        assert payload.get("retry_after_sec") == 7
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
        raise AssertionError(f"{MODULE_PATH}:test_handler_rate_limits_requests failed: {exc}") from exc


def test_handler_snapshot_requires_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure `/v1/snapshot` returns 401 when Authorization fails.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches auth_ok to always deny.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `do_GET` for `/v1/snapshot` auth path.

    Why this exists
    Snapshot payloads can include sensitive metadata; access must be gated by a token.
    """
    try:
        api = _build_api_config()
        stub = _StubThrottler(api)
        monkeypatch.setattr(hf, "RequestThrottler", lambda _api: stub)
        monkeypatch.setattr(hf, "auth_ok", lambda _auth, _api: False)

        handler_cls = hf.build_handler_factory({}, api)
        handler, captured = _new_handler_instance(
            handler_cls, path="/v1/snapshot", authorization="Bearer wrong"
        )
        handler.do_GET()

        assert captured.status == int(HTTPStatus.UNAUTHORIZED)
        payload = _body_json(handler)
        assert payload.get("error") == "unauthorized"
        assert payload.get("error_code") == "auth_failed"
        assert stub.auth_failures == 1
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
        raise AssertionError(f"{MODULE_PATH}:test_handler_snapshot_requires_auth failed: {exc}") from exc


def test_handler_snapshot_writes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure `/v1/snapshot` emits JSON body and exit code header when authorized.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches auth_ok and emit_snapshot_json to avoid IO.

    Error handling
    Raises AssertionError with context on failures.

    Ties to other methods
    Exercises `/v1/snapshot` happy path.

    Why this exists
    Native clients rely on headers and deterministic JSON emission for error handling.
    """
    try:
        api = _build_api_config()
        stub = _StubThrottler(api)
        monkeypatch.setattr(hf, "RequestThrottler", lambda _api: stub)
        monkeypatch.setattr(hf, "auth_ok", lambda _auth, _api: True)
        monkeypatch.setattr(hf, "emit_snapshot_json", lambda _handlers, pretty: (0, '{"ok":true}'))

        handler_cls = hf.build_handler_factory({}, api)
        handler, captured = _new_handler_instance(
            handler_cls, path="/v1/snapshot", authorization="Bearer test"
        )
        handler.do_GET()

        assert captured.status == int(HTTPStatus.OK)
        assert ("X-Snapshot-Exit-Code", "0") in captured.headers
        raw = handler.wfile.getvalue().decode("utf-8")
        assert json.loads(raw).get("ok") is True
        assert stub.auth_successes == 1
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
        raise AssertionError(f"{MODULE_PATH}:test_handler_snapshot_writes_json failed: {exc}") from exc


def test_handler_section_missing_key_is_bad_request(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure `/v1/section` returns 400 when key is missing.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches auth_ok to allow the request.

    Error handling
    Raises AssertionError with context on failures.

    Ties to other methods
    Exercises `/v1/section` parameter validation.

    Why this exists
    Parameter validation should fail fast with a clear machine-readable error.
    """
    try:
        api = _build_api_config()
        stub = _StubThrottler(api)
        monkeypatch.setattr(hf, "RequestThrottler", lambda _api: stub)
        monkeypatch.setattr(hf, "auth_ok", lambda _auth, _api: True)

        handler_cls = hf.build_handler_factory({}, api)
        handler, captured = _new_handler_instance(
            handler_cls, path="/v1/section", authorization="Bearer test"
        )
        handler.do_GET()

        assert captured.status == int(HTTPStatus.BAD_REQUEST)
        payload = _body_json(handler)
        assert payload.get("error") == "missing_section_key"
        assert payload.get("error_code") == "input_invalid"
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
            f"{MODULE_PATH}:test_handler_section_missing_key_is_bad_request failed: {exc}"
        ) from exc


def test_handler_section_writes_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure `/v1/section?key=...` emits the section JSON body when authorized.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches auth_ok and emit_section_json to avoid collector IO.

    Error handling
    Raises AssertionError with context on failures.

    Ties to other methods
    Exercises `/v1/section` happy path.

    Why this exists
    The iOS client fetches per-section data for incremental updates.
    """
    try:
        api = _build_api_config()
        stub = _StubThrottler(api)
        monkeypatch.setattr(hf, "RequestThrottler", lambda _api: stub)
        monkeypatch.setattr(hf, "auth_ok", lambda _auth, _api: True)
        monkeypatch.setattr(
            hf, "emit_section_json", lambda _handlers, section_key, pretty: (0, '{"ok":true}')
        )

        handler_cls = hf.build_handler_factory({}, api)
        handler, captured = _new_handler_instance(
            handler_cls, path="/v1/section?key=general", authorization="Bearer test"
        )
        handler.do_GET()

        assert captured.status == int(HTTPStatus.OK)
        assert ("X-Snapshot-Exit-Code", "0") in captured.headers
        assert json.loads(handler.wfile.getvalue().decode("utf-8")).get("ok") is True
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
        raise AssertionError(f"{MODULE_PATH}:test_handler_section_writes_json failed: {exc}") from exc


def test_handler_snapshot_unexpected_error_uses_standardized_internal_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Summary
    Ensure unexpected snapshot errors return standardized internal error payload metadata.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches snapshot emission to raise a deterministic runtime error.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `do_GET` unexpected failure mapping path for `/v1/snapshot`.

    Why this exists
    Boundary failures must expose stable machine-readable error codes rather than ad-hoc exception strings.
    """
    try:
        api = _build_api_config()
        stub = _StubThrottler(api)
        monkeypatch.setattr(hf, "RequestThrottler", lambda _api: stub)
        monkeypatch.setattr(hf, "auth_ok", lambda _auth, _api: True)
        monkeypatch.setattr(
            hf,
            "emit_snapshot_json",
            lambda _handlers, pretty: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        handler_cls = hf.build_handler_factory({}, api)
        handler, captured = _new_handler_instance(
            handler_cls, path="/v1/snapshot", authorization="Bearer test"
        )
        handler.do_GET()

        assert captured.status == int(HTTPStatus.INTERNAL_SERVER_ERROR)
        assert ("X-Error-Code", "internal_error") in captured.headers
        payload = _body_json(handler)
        assert payload.get("error") == "internal_error"
        assert payload.get("error_code") == "internal_error"
        assert payload.get("message") == "Unexpected internal error."
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
            f"{MODULE_PATH}:test_handler_snapshot_unexpected_error_uses_standardized_internal_payload failed: {exc}"
        ) from exc


def test_handler_snapshot_client_disconnect_is_silenced(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure a BrokenPipe during body write does not raise and does not attempt a second response.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Replaces wfile with a writer that raises BrokenPipeError.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_is_client_disconnect` integration in `/v1/snapshot`.

    Why this exists
    Mobile clients may cancel in-flight requests; server code should not produce noisy nested failures.
    """
    try:
        api = _build_api_config()
        stub = _StubThrottler(api)
        monkeypatch.setattr(hf, "RequestThrottler", lambda _api: stub)
        monkeypatch.setattr(hf, "auth_ok", lambda _auth, _api: True)
        monkeypatch.setattr(hf, "emit_snapshot_json", lambda _handlers, pretty: (0, '{"ok":true}'))

        handler_cls = hf.build_handler_factory({}, api)
        handler, captured = _new_handler_instance(
            handler_cls, path="/v1/snapshot", authorization="Bearer test"
        )

        class _BrokenWriter(io.BytesIO):
            def write(self, _b: bytes) -> int:  # type: ignore[override]
                """
                Summary
                Execute `write` for its module-level responsibility.

                Inputs
                _b: `bytes` parameter from the function signature.

                Outputs
                Returns `int`.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_backend_http_handler_factory_unit.py:write` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_backend_http_handler_factory_unit.py`.

                Why this exists
                Keeps `write` explicit, testable, and maintainable.
                """
                raise BrokenPipeError()

        handler.wfile = _BrokenWriter()
        handler.do_GET()

        assert captured.status == int(HTTPStatus.OK)
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
            f"{MODULE_PATH}:test_handler_snapshot_client_disconnect_is_silenced failed: {exc}"
        ) from exc
