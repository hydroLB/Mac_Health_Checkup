from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/core/config/models/backend.py"


@dataclass(frozen=True)
class ApiConfig:
    """
    Summary
    Hold backend API server configuration for native frontends.

    Inputs
    Enabled flag, bind host, port, LAN access, TLS settings, auth token, and request throttling knobs.

    Outputs
    Immutable API configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_api` and consumed by the backend server and entrypoint.

    Why this exists
    Keeps API behavior tunable and centrally validated.
    """

    enabled: bool
    bind_host: str
    port: int
    allow_lan: bool
    allow_insecure_http_lan: bool
    tls_enabled: bool
    tls_cert_path: str
    tls_key_path: str
    auth_token: str
    min_auth_token_length: int
    blocked_auth_tokens: list[str]
    rate_limit_requests_per_minute: int
    max_auth_failures_per_minute: int
    auth_ban_seconds: int
    request_timeout_sec: int
    pairing_qr_enabled: bool


@dataclass(frozen=True)
class FansConfig:
    """
    Summary
    Hold fan diagnostics configuration.

    Inputs
    use_sudo: Whether collectors may attempt sudo escalation when supported.

    Outputs
    Immutable fan configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_fans` and consumed by fan and SSD diagnostics.

    Why this exists
    Controls when sudo escalation is allowed.
    """

    use_sudo: bool
