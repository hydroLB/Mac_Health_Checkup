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
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.thermals import authorize_temperature_sensors

MODULE_PATH = "mac_health_checkup/app/backend/http/handler_factory.py"

SectionHandler = Callable[[SectionHost], JsonDict]


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
                _ = format
                _ = args
                return

            def do_GET(self) -> None:  # noqa: N802
                """
                Purpose: Handle GET requests for health and snapshot endpoints.
                Ties: Served by SnapshotApiServer.
                Inputs: HTTP request data via BaseHTTPRequestHandler.
                Outputs: Writes an HTTP response.
                Side effects: Writes to network socket.
                Why: Exposes read-only diagnostics snapshots for native clients.
                """
                try:
                    client_ip = str(self.client_address[0]) if self.client_address else "unknown"
                    self.connection.settimeout(float(api.request_timeout_sec))
                    allowed, retry_after = throttler.allow_request(client_ip)
                    if not allowed:
                        self._respond_json(
                            HTTPStatus.TOO_MANY_REQUESTS,
                            {"ok": False, "error": "rate_limited", "retry_after_sec": retry_after},
                            headers={"Retry-After": str(retry_after)},
                        )
                        return
                    parsed = urlparse(self.path or "")
                    path = parsed.path
                    query = parse_qs(parsed.query)

                    if path == "/v1/health":
                        self._respond_json(HTTPStatus.OK, {"ok": True, "service": "mac-health-checkup"})
                        return
                    if path == "/v1/authorize/thermals":
                        if not auth_ok(self.headers.get("Authorization"), api):
                            throttler.record_auth_failure(client_ip)
                            self._respond_json(
                                HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"}
                            )
                            return
                        throttler.record_auth_success(client_ip)
                        auth_payload = authorize_temperature_sensors(force=True)
                        self._respond_json(HTTPStatus.OK, auth_payload)
                        return
                    if path == "/v1/snapshot":
                        if not auth_ok(self.headers.get("Authorization"), api):
                            throttler.record_auth_failure(client_ip)
                            self._respond_json(
                                HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"}
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
                        self.wfile.write(snapshot_json.encode("utf-8"))
                        return
                    if path == "/v1/section":
                        if not auth_ok(self.headers.get("Authorization"), api):
                            throttler.record_auth_failure(client_ip)
                            self._respond_json(
                                HTTPStatus.UNAUTHORIZED, {"ok": False, "error": "unauthorized"}
                            )
                            return
                        throttler.record_auth_success(client_ip)
                        key_values = query.get("key", [])
                        key = key_values[0] if key_values else ""
                        if not isinstance(key, str) or not key.strip():
                            self._respond_json(
                                HTTPStatus.BAD_REQUEST,
                                {"ok": False, "error": "missing_section_key"},
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
                        self.wfile.write(section_json.encode("utf-8"))
                        return
                    self._respond_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})
                except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
                    self._respond_json(
                        HTTPStatus.INTERNAL_SERVER_ERROR,
                        {
                            "ok": False,
                            "error": format_error(MODULE_PATH, "_Handler.do_GET", "Request failed", exc),
                        },
                    )

            def _respond_json(
                self, status: HTTPStatus, payload: JsonDict, *, headers: Mapping[str, str] | None = None
            ) -> None:
                """
                Purpose: Write a JSON response with headers.
                Ties: Used by do_GET for structured responses.
                Inputs: status code and JSON payload.
                Outputs: Writes the HTTP response.
                Side effects: Writes to the socket.
                Why: Keeps response formatting consistent.
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
                    self.wfile.write(body)
                except (OSError, RuntimeError, ValueError, TypeError) as exc:
                    raise RuntimeError(
                        format_error(MODULE_PATH, "_Handler._respond_json", "Failed to write response", exc)
                    ) from exc

        return _Handler
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "build_handler_factory", "Failed to build handler", exc)
        ) from exc
