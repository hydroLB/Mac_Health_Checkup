from __future__ import annotations

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
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/backend/server.py"

SectionHandler = Callable[[SectionHost], JsonDict]


class SnapshotApiServer:
    """
    Purpose: Run an HTTP server that exposes snapshot JSON for native clients.
    Ties: Used by the entrypoint `--serve` mode for the iOS app.
    Inputs: handlers mapping and API config.
    Outputs: Serves HTTP responses.
    Side effects: Binds a TCP port and spawns server threads.
    Why: Provides a simple agent API so a proper iOS app can render Mac diagnostics remotely.
    """

    def __init__(self, handlers: Mapping[str, SectionHandler], api: ApiConfig) -> None:
        """
        Purpose: Initialize the API server and request handler factory.
        Ties: Used by `start` and tests.
        Inputs: handlers mapping and API config.
        Outputs: None.
        Side effects: None.
        Why: Keeps server setup explicit and testable.
        """
        try:
            self._handlers = dict(handlers)
            self._api = api
            self._httpd: ThreadingHTTPServer | None = None
            self._thread: threading.Thread | None = None
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SnapshotApiServer.__init__", "Failed to init server", exc)
            ) from exc

    def start(self) -> None:
        """
        Purpose: Start the HTTP server in a background thread.
        Ties: Used by entrypoint serve mode.
        Inputs: None.
        Outputs: None.
        Side effects: Binds the configured port and starts serving.
        Why: Keeps the main thread available for signal handling.
        """
        try:
            if self._httpd is not None:
                return
            validate_api_config_for_server(self._api)
            handler_factory = build_handler_factory(self._handlers, self._api)
            httpd = ThreadingHTTPServer((self._api.bind_host, self._api.port), handler_factory)
            httpd.daemon_threads = True
            if self._api.tls_enabled:
                cert_path = Path(self._api.tls_cert_path).expanduser()
                key_path = Path(self._api.tls_key_path).expanduser()
                context = build_tls_server_context(cert_path, key_path)
                httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
            self._httpd = httpd
            self._thread = threading.Thread(target=httpd.serve_forever, name="snapshot-api", daemon=True)
            self._thread.start()
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SnapshotApiServer.start", "Failed to start server", exc)
            ) from exc

    def stop(self) -> None:
        """
        Purpose: Stop the HTTP server and join its thread.
        Ties: Used by entrypoint shutdown and tests.
        Inputs: None.
        Outputs: None.
        Side effects: Shuts down the server and closes the socket.
        Why: Ensures the agent stops cleanly without leaked threads.
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
        except (OSError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SnapshotApiServer.stop", "Failed to stop server", exc)
            ) from exc

    def url(self) -> str:
        """
        Purpose: Return the base URL for the server.
        Ties: Used by CLI output in serve mode.
        Inputs: None.
        Outputs: URL string.
        Side effects: None.
        Why: Makes pairing instructions deterministic.
        """
        try:
            host = self._api.bind_host
            if host == "0.0.0.0":
                host = "127.0.0.1"
            scheme = "https" if self._api.tls_enabled else "http"
            return f"{scheme}://{host}:{self._api.port}"
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
    Purpose: Pick a free TCP port for temporary server usage.
    Ties: Used by tests and optional serve mode helpers.
    Inputs: bind_host for the socket bind.
    Outputs: An available port integer.
    Side effects: Binds and closes a temporary socket.
    Why: Allows deterministic tests without hard-coded ports.
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
    Purpose: Wait until the server becomes reachable.
    Ties: Used by tests to avoid race conditions.
    Inputs: base url and timeout seconds.
    Outputs: True when health endpoint responds.
    Side effects: Performs network connections.
    Why: Ensures tests do not depend on timing.
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
