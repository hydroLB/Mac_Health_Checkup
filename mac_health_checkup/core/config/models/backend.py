from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/core/config/models/backend.py"


@dataclass(frozen=True)
class ApiConfig:
    """
    Purpose: Hold backend API server configuration for native frontends.
    Ties: Used by the Python backend server to expose snapshot endpoints.
    Inputs: enabled flag, bind host, port, allow_lan, auth token, and rate limit knobs.
    Outputs: Immutable API configuration.
    Side effects: None.
    Why: Keeps API behavior tunable and centrally validated.
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


@dataclass(frozen=True)
class FansConfig:
    """
    Purpose: Hold fan diagnostics configuration.
    Ties: Used by SSD and fan diagnostics for sudo behavior.
    Inputs: use_sudo flag and use_admin_prompt toggle.
    Outputs: Immutable fan configuration.
    Side effects: None.
    Why: Controls when sudo escalation is allowed.
    """

    use_sudo: bool
    use_admin_prompt: bool
