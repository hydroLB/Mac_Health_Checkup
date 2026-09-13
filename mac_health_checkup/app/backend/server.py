from __future__ import annotations

import errno
import ipaddress
import socket
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Mapping

from mac_health_checkup.app.backend.http.handler_factory import build_handler_factory
from mac_health_checkup.app.backend.security.validation import validate_api_config_for_server
from mac_health_checkup.app.backend.tls import (
    build_tls_server_context,
    certificate_sha256_fingerprint_from_pem,
)
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import ApiConfig
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/backend/server.py"
_BIND_ALL_INTERFACES_V4 = str(ipaddress.IPv4Address(0))

SectionHandler = Callable[[SectionHost], JsonDict]


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    """
    Summary
    ThreadingHTTPServer with safer socket reuse defaults.

    Inputs
    Same as ThreadingHTTPServer.

    Outputs
    HTTP server instance.

    Side effects
    Sets SO_REUSEADDR to allow quick restarts during development and tests.

    Error handling
    Inherits from ThreadingHTTPServer.

    Ties to other methods
    Used by `SnapshotApiServer.start`.

    Why this exists
    The agent is frequently restarted while iterating; socket reuse prevents transient bind failures.
    """

    allow_reuse_address = True


class SnapshotApiServer:
    """
    Summary
    Run an HTTP server that exposes snapshot JSON for native clients.

    Inputs
    handlers: Mapping of section keys to handler callables.
    api: API config.

    Outputs
    Serves HTTP responses.

    Side effects
    Binds a TCP port and spawns server threads.

    Error handling
    Methods raise `RuntimeError` with module and method context when server lifecycle operations fail.

    Ties to other methods
    Used by the entrypoint `--serve` mode for the iOS app.

    Why this exists
    Provides a simple agent API so a proper iOS app can render Mac diagnostics remotely.
    """

    def __init__(self, handlers: Mapping[str, SectionHandler], api: ApiConfig) -> None:
        """
        Summary
        Initialize the API server and request handler factory.

        Inputs
        handlers: Mapping of section keys to handler callables.
        api: API config.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when initialization fails unexpectedly.

        Ties to other methods
        Used by `start` and tests.

        Why this exists
        Keeps server setup explicit and testable.
        """
        try:
            self._handlers = dict(handlers)
            self._api = api
            self._httpd: ThreadingHTTPServer | None = None
            self._thread: threading.Thread | None = None
            self._bound_host: str | None = None
            self._bound_port: int | None = None
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SnapshotApiServer.__init__", "Failed to init server", exc)
            ) from exc

    def start(self) -> None:
        """
        Summary
        Start the HTTP server in a background thread.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Binds the configured port and starts serving.

        Error handling
        Raises `RuntimeError` with module and method context when binding or TLS setup fails.

        Ties to other methods
        Used by entrypoint serve mode.

        Why this exists
        Keeps the main thread available for signal handling.
        """
        httpd: ThreadingHTTPServer | None = None
        try:
            if self._httpd is not None:
                return
            validate_api_config_for_server(self._api)
            handler_factory = build_handler_factory(self._handlers, self._api)
            host = self._api.bind_host
            preferred_port = int(self._api.port)
            max_attempts = 20 if preferred_port != 0 else 1
            last_exc: OSError | None = None

            for attempt in range(max_attempts):
                port = preferred_port if preferred_port == 0 else preferred_port + attempt
                if port > 65535:
                    break
                try:
                    httpd = _ReusableThreadingHTTPServer((host, port), handler_factory)
                    break
                except OSError as exc:
                    last_exc = exc
                    if preferred_port == 0:
                        break
                    if getattr(exc, "errno", None) != errno.EADDRINUSE:
                        break

            if httpd is None:
                detail = f"Failed to bind server at {host}:{preferred_port}"
                if preferred_port != 0:
                    last_port = min(65535, preferred_port + max_attempts - 1)
                    detail = f"{detail} (tried {preferred_port}-{last_port})"
                if last_exc is not None:
                    detail = f"{detail}: {last_exc}"
                raise OSError(detail)

            httpd.daemon_threads = True
            if self._api.tls_enabled:
                cert_path = Path(self._api.tls_cert_path).expanduser()
                key_path = Path(self._api.tls_key_path).expanduser()
                context = build_tls_server_context(cert_path, key_path)
                httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
            bound_host, bound_port = httpd.server_address[:2]
            resolved_host = str(bound_host)
            resolved_port = int(bound_port)
            thread = threading.Thread(target=httpd.serve_forever, name="snapshot-api", daemon=True)
            thread.start()

            self._httpd = httpd
            self._thread = thread
            self._bound_host = resolved_host
            self._bound_port = resolved_port
            httpd = None
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            if httpd is not None:
                try:
                    httpd.server_close()
                except (OSError, RuntimeError, ValueError, TypeError):
                    pass
            self._httpd = None
            self._thread = None
            self._bound_host = None
            self._bound_port = None
            raise RuntimeError(
                format_error(MODULE_PATH, "SnapshotApiServer.start", "Failed to start server", exc)
            ) from exc

    def stop(self) -> None:
        """
        Summary
        Stop the HTTP server and join its thread.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Shuts down the server and closes the socket.

        Error handling
        Raises `RuntimeError` with module and method context when shutdown fails unexpectedly.

        Ties to other methods
        Used by entrypoint shutdown and tests.

        Why this exists
        Ensures the agent stops cleanly without leaked threads.
        """
        try:
            if self._httpd is None:
                return
            self._httpd.shutdown()
            self._httpd.server_close()
            if self._thread is not None:
                self._thread.join(timeout=2.0)
            self._httpd = None
            self._thread = None
            self._bound_host = None
            self._bound_port = None
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SnapshotApiServer.stop", "Failed to stop server", exc)
            ) from exc

    def url(self) -> str:
        """
        Summary
        Return the base URL for the server.

        Inputs
        None.

        Outputs
        URL string.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when URL construction fails unexpectedly.

        Ties to other methods
        Used by CLI output in serve mode.

        Why this exists
        Makes pairing instructions deterministic.
        """
        try:
            host = self._bound_host or self._api.bind_host
            if host == _BIND_ALL_INTERFACES_V4:
                host = "127.0.0.1"
            port = self._bound_port if self._bound_port is not None else int(self._api.port)
            scheme = "https" if self._api.tls_enabled else "http"
            return f"{scheme}://{host}:{port}"
        except (RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SnapshotApiServer.url", "Failed to build URL", exc)
            ) from exc

    def tls_certificate_fingerprint_sha256(self) -> str | None:
        """
        Summary
        Return the configured TLS certificate fingerprint for pinning, when TLS is enabled.

        Inputs
        None.

        Outputs
        Lowercase hex SHA-256 fingerprint, or None when TLS is disabled.

        Side effects
        Reads the configured certificate file from disk when enabled.

        Error handling
        Raises `RuntimeError` with module and method context when fingerprint computation fails.

        Ties to other methods
        Used by the entrypoint to print pairing information for iOS certificate pinning.

        Why this exists
        Pinning prevents token sniffing on untrusted LANs by ensuring the iOS client talks to the expected server.
        """
        try:
            if not self._api.tls_enabled:
                return None
            cert_path = Path(self._api.tls_cert_path).expanduser()
            return certificate_sha256_fingerprint_from_pem(cert_path)
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "SnapshotApiServer.tls_certificate_fingerprint_sha256",
                    "Failed to compute fingerprint",
                    exc,
                )
            ) from exc


def pick_free_port(bind_host: str) -> int:
    """
    Summary
    Pick a free TCP port for temporary server usage.

    Inputs
    bind_host: Bind host for the socket bind.

    Outputs
    An available port integer.

    Side effects
    Binds and closes a temporary socket.

    Error handling
    Raises `RuntimeError` with module and method context when port selection fails.

    Ties to other methods
    Used by tests and optional serve mode helpers.

    Why this exists
    Allows deterministic tests without hard-coded ports.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((bind_host, 0))
            return int(sock.getsockname()[1])
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "pick_free_port", "Failed to pick free port", exc)
        ) from exc


def wait_until_ready(url: str, *, timeout_sec: int) -> bool:
    """
    Summary
    Wait until the server becomes reachable.

    Inputs
    url: Base URL.
    timeout_sec: Timeout seconds.

    Outputs
    True when the server becomes reachable.

    Side effects
    Performs network connections.

    Error handling
    Never raises for connection failures; returns false after timeout. Raises `RuntimeError` with module and method
    context when input parsing fails unexpectedly.

    Ties to other methods
    Used by tests to avoid race conditions.

    Why this exists
    Ensures tests do not depend on timing.
    """
    try:
        deadline = time.time() + max(1, int(timeout_sec))
        while time.time() < deadline:
            try:
                host_port = url.split("://", 1)[1]
                host, port_str = host_port.split(":", 1)
                port = int(port_str)
                with socket.create_connection((host, port), timeout=0.2):
                    return True
            except OSError:
                time.sleep(0.05)
        return False
    except (RuntimeError, ValueError, TypeError, IndexError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "wait_until_ready", "Failed waiting for readiness", exc)
        ) from exc
