from __future__ import annotations

from pathlib import Path

from mac_health_checkup.app.backend.tls import certificate_sha256_fingerprint_from_pem
from mac_health_checkup.core.config import ApiConfig
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/backend/security/validation.py"


def validate_api_config_for_server(api: ApiConfig) -> None:
    """
    Summary
    Validate API configuration at the server boundary.

    Inputs
    api: API config value.

    Outputs
    None.

    Side effects
    Reads TLS certificate files when TLS is enabled.

    Error handling
    Raises `RuntimeError` with module and method context when the API config is invalid or unsafe.

    Ties to other methods
    Called by `SnapshotApiServer.start` to fail early with actionable errors.

    Why this exists
    Prevents accidental unsafe exposure when the agent API is enabled.
    """
    try:
        if not api.enabled:
            raise ValueError("api.enabled must be true to start the API server")
        host = (api.bind_host or "").strip()
        if not host:
            raise ValueError("api.bind_host must be non-empty")
        token = (api.auth_token or "").strip()
        if not token:
            raise ValueError("api.auth_token must be non-empty")
        if len(token) < api.min_auth_token_length:
            raise ValueError(f"api.auth_token too short. min_len={api.min_auth_token_length}")
        blocked = {item.strip().lower() for item in api.blocked_auth_tokens if item.strip()}
        if token.lower() in blocked:
            raise ValueError("api.auth_token is a blocked placeholder value")

        is_loopback = host in ("127.0.0.1", "localhost") or host.startswith("127.")
        if not is_loopback and not api.allow_lan:
            raise ValueError("api.allow_lan must be true when binding to a non-loopback address")
        if api.allow_lan and len(token) < max(32, api.min_auth_token_length):
            raise ValueError("api.auth_token must be at least 32 characters when api.allow_lan is true")
        if api.allow_lan and not api.tls_enabled and not api.allow_insecure_http_lan:
            raise ValueError(
                "TLS is required for LAN mode. Set api.tls_enabled=true or explicitly opt out with api.allow_insecure_http_lan=true"
            )
        if api.tls_enabled:
            cert = Path(api.tls_cert_path).expanduser()
            key = Path(api.tls_key_path).expanduser()
            if not cert.is_file():
                raise ValueError(f"api.tls_cert_path not found: {cert}")
            if not key.is_file():
                raise ValueError(f"api.tls_key_path not found: {key}")
            _ = certificate_sha256_fingerprint_from_pem(cert)
        if api.request_timeout_sec < 1 or api.request_timeout_sec > 120:
            raise ValueError("api.request_timeout_sec out of range")
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "validate_api_config_for_server", "Invalid API config", exc)
        ) from exc
