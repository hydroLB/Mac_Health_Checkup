from __future__ import annotations

import hmac
from typing import Optional

from mac_health_checkup.core.config import ApiConfig
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/backend/security/auth.py"


def auth_ok(authorization: Optional[str], api: ApiConfig) -> bool:
    """
    Summary
    Validate Bearer token authorization for snapshot access.

    Inputs
    authorization: Authorization header value.
    api: API config containing the expected token.

    Outputs
    True when authorized, else false.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when validation fails unexpectedly.

    Ties to other methods
    Used by the HTTP handler for `/v1/snapshot` and `/v1/section`.

    Why this exists
    Prevents unauthenticated access on the local network and keeps token handling consistent.
    """
    try:
        if not api.enabled:
            return False
        if not authorization or not isinstance(authorization, str):
            return False
        prefix = "Bearer "
        if not authorization.startswith(prefix):
            return False
        token = authorization[len(prefix) :]
        return hmac.compare_digest(token, api.auth_token)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "auth_ok", "Failed to validate auth", exc)) from exc
