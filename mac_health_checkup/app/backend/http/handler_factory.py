from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Callable, Mapping
from urllib.parse import parse_qs, urlparse

from mac_health_checkup.app.backend.security.auth import auth_ok
from mac_health_checkup.app.backend.security.throttling import RequestThrottler
from mac_health_checkup.app.backend.snapshot import emit_section_json, emit_snapshot_json
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import ApiConfig
from mac_health_checkup.core.types import JsonDict, JsonValue
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils.error_boundary import (
    ErrorBoundary,
    ErrorCode,
    is_client_disconnect_exception,
    map_boundary_exception,
)

MODULE_PATH = "mac_health_checkup/app/backend/http/handler_factory.py"

SectionHandler = Callable[[SectionHost], JsonDict]


def _is_client_disconnect(exc: BaseException) -> bool:
    """
    Summary
    Determine whether an exception is a normal client disconnect during response writes.

    Inputs
    exc: Exception raised while reading or writing the connection.

    Outputs
    True when the error indicates the client closed the connection, else false.

    Side effects
    None.

    Error handling
    Never raises; returns false on unexpected inputs.

    Ties to other methods
    Used by the HTTP handler to avoid attempting a second response after a client disconnect.

    Why this exists
    Broken pipes are normal when clients cancel requests; treating them as server errors causes noisy logs and
    can trigger nested exception loops in error handlers.
    """
    try:
        return bool(is_client_disconnect_exception(exc))
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError):
        return False


def build_handler_factory(
    handlers: Mapping[str, SectionHandler], api: ApiConfig
) -> type[BaseHTTPRequestHandler]:
    """
    Summary
    Build a request handler class bound to handlers and config.

    Inputs
    handlers: Mapping of section keys to handler callables.
    api: API config.

    Outputs
    `BaseHTTPRequestHandler` subclass for `ThreadingHTTPServer`.

    Side effects
    Creates an in-memory throttler bound to config.

    Error handling
    Raises `RuntimeError` with module and method context when handler creation fails.

    Ties to other methods
    Used by `SnapshotApiServer.start` to inject section handlers for deterministic tests.

    Why this exists
    Keeps the HTTP handler logic isolated from server threading and TLS wiring.
    """
    try:
        throttler = RequestThrottler(api)

        class _Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                """
                Summary
                Execute `log_message` for its module-level responsibility.

                Inputs
                format: `str` parameter from the function signature.
                *args: variadic `object` parameters.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `mac_health_checkup/app/backend/http/handler_factory.py:log_message` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `mac_health_checkup/app/backend/http/handler_factory.py`.

                Why this exists
                Keeps `log_message` explicit, testable, and maintainable.
                """
                _ = format
                _ = args
                return

            def do_GET(self) -> None:  # noqa: N802
                """
                Summary
                Handle GET requests for health and snapshot endpoints.

                Inputs
                HTTP request data via BaseHTTPRequestHandler.

                Outputs
                Writes an HTTP response.

                Side effects
                Writes to the network socket.

                Error handling
                Best-effort responds with JSON error bodies. Returns silently when the client disconnects.

                Ties to other methods
                Served by `SnapshotApiServer`.

                Why this exists
                Exposes read-only diagnostics snapshots for native clients.
                """
                try:
                    client_ip = str(self.client_address[0]) if self.client_address else "unknown"
                    self.connection.settimeout(float(api.request_timeout_sec))
                    allowed, retry_after = throttler.allow_request(client_ip)
                    if not allowed:
                        self._respond_api_error(
                            HTTPStatus.TOO_MANY_REQUESTS,
                            error=ErrorCode.RATE_LIMITED.value,
                            error_code=ErrorCode.RATE_LIMITED.value,
                            message="Request rate limit exceeded.",
                            extra_payload={"retry_after_sec": retry_after},
                            headers={"Retry-After": str(retry_after)},
                        )
                        return
                    parsed = urlparse(self.path or "")
                    path = parsed.path
                    query = parse_qs(parsed.query)

                    if path == "/v1/health":
                        self._respond_json(HTTPStatus.OK, {"ok": True, "service": "mac-health-checkup"})
                        return
                    if path == "/v1/snapshot":
                        if not auth_ok(self.headers.get("Authorization"), api):
                            throttler.record_auth_failure(client_ip)
                            self._respond_api_error(
                                HTTPStatus.UNAUTHORIZED,
                                error="unauthorized",
                                error_code=ErrorCode.AUTH_FAILED.value,
                                message="Authentication failed.",
                            )
                            return
                        throttler.record_auth_success(client_ip)
                        code, snapshot_json = emit_snapshot_json(handlers, pretty=False)
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.send_header("X-Snapshot-Exit-Code", str(int(code)))
                        self.send_header("Content-Length", str(len(snapshot_json.encode("utf-8"))))
                        self.end_headers()
                        try:
                            self.wfile.write(snapshot_json.encode("utf-8"))
                        except OSError as write_exc:
                            if _is_client_disconnect(write_exc):
                                return
                            raise
                        return
                    if path == "/v1/section":
                        if not auth_ok(self.headers.get("Authorization"), api):
                            throttler.record_auth_failure(client_ip)
                            self._respond_api_error(
                                HTTPStatus.UNAUTHORIZED,
                                error="unauthorized",
                                error_code=ErrorCode.AUTH_FAILED.value,
                                message="Authentication failed.",
                            )
                            return
                        throttler.record_auth_success(client_ip)
                        key_values = query.get("key", [])
                        key = key_values[0] if key_values else ""
                        if not isinstance(key, str) or not key.strip():
                            self._respond_api_error(
                                HTTPStatus.BAD_REQUEST,
                                error="missing_section_key",
                                error_code=ErrorCode.INPUT_INVALID.value,
                                message="Section key is required.",
                            )
                            return
                        code, section_json = emit_section_json(
                            handlers, section_key=key.strip(), pretty=False
                        )
                        self.send_response(HTTPStatus.OK)
                        self.send_header("Content-Type", "application/json; charset=utf-8")
                        self.send_header("Cache-Control", "no-store")
                        self.send_header("X-Content-Type-Options", "nosniff")
                        self.send_header("X-Snapshot-Exit-Code", str(int(code)))
                        self.send_header("Content-Length", str(len(section_json.encode("utf-8"))))
                        self.end_headers()
                        try:
                            self.wfile.write(section_json.encode("utf-8"))
                        except OSError as write_exc:
                            if _is_client_disconnect(write_exc):
                                return
                            raise
                        return
                    self._respond_api_error(
                        HTTPStatus.NOT_FOUND,
                        error="not_found",
                        error_code=ErrorCode.NOT_FOUND.value,
                        message="Requested resource was not found.",
                    )
                except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
                    if _is_client_disconnect(exc):
                        return
                    try:
                        mapped = map_boundary_exception(
                            exc,
                            boundary=ErrorBoundary.API,
                            default_message="Request handling failed",
                        )
                        self._respond_api_error(
                            mapped.http_status,
                            error=mapped.code.value,
                            error_code=mapped.code.value,
                            message=mapped.user_message,
                            headers={"X-Error-Code": mapped.code.value},
                        )
                    except OSError as write_exc:
                        if _is_client_disconnect(write_exc):
                            return
                        raise

            def _respond_json(
                self, status: int | HTTPStatus, payload: JsonDict, *, headers: Mapping[str, str] | None = None
            ) -> None:
                """
                Summary
                Write a JSON response with headers.

                Inputs
                status: HTTP status code.
                payload: JSON-serializable dict.
                headers: Optional additional response headers.

                Outputs
                Writes the HTTP response.

                Side effects
                Writes to the socket.

                Error handling
                Raises `RuntimeError` with module and method context when response writing fails.

                Ties to other methods
                Used by `do_GET` for structured responses.

                Why this exists
                Keeps response formatting consistent.
                """
                try:
                    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.send_header("Content-Length", str(len(body)))
                    if headers is not None:
                        for key, value in headers.items():
                            self.send_header(key, value)
                    self.end_headers()
                    try:
                        self.wfile.write(body)
                    except OSError as write_exc:
                        if _is_client_disconnect(write_exc):
                            return
                        raise
                except (OSError, RuntimeError, ValueError, TypeError) as exc:
                    raise RuntimeError(
                        format_error(MODULE_PATH, "_Handler._respond_json", "Failed to write response", exc)
                    ) from exc

            def _respond_api_error(
                self,
                status: int | HTTPStatus,
                *,
                error: str,
                error_code: str,
                message: str,
                extra_payload: Mapping[str, JsonValue] | None = None,
                headers: Mapping[str, str] | None = None,
            ) -> None:
                """
                Summary
                Write a standardized API error response.

                Inputs
                status: HTTP status code.
                error: Backward-compatible API error string.
                error_code: Standardized typed error code.
                message: Human-readable error message.
                extra_payload: Optional extra payload fields merged into the response body.
                headers: Optional response headers.

                Outputs
                Writes the HTTP response.

                Side effects
                Writes to the socket.

                Error handling
                Raises `RuntimeError` with module and method context when response writing fails.

                Ties to other methods
                Used by `do_GET` for auth, validation, and unexpected-failure paths.

                Why this exists
                API clients should receive one consistent failure payload shape.
                """
                try:
                    payload: JsonDict = {
                        "ok": False,
                        "error": error,
                        "error_code": error_code,
                        "message": message,
                    }
                    if extra_payload is not None:
                        for key, value in extra_payload.items():
                            payload[str(key)] = value
                    self._respond_json(status, payload, headers=headers)
                except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
                    raise RuntimeError(
                        format_error(MODULE_PATH, "_Handler._respond_api_error", "Failed to write API error", exc)
                    ) from exc

        return _Handler
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "build_handler_factory", "Failed to build handler", exc)
        ) from exc
