from __future__ import annotations

import os
from urllib.parse import urlparse

from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/entrypoint.py"


def resolve_public_base_url(*, default_url: str) -> str:
    """
    Summary
    Resolve and validate the optional public base URL environment override.

    Inputs
    default_url: Fallback URL from the running server bind.

    Outputs
    Validated public base URL string.

    Side effects
    Reads `MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL` from environment.

    Error handling
    Raises `RuntimeError` with module and method context when the override is present but invalid.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._resolve_public_base_url` in serve mode.

    Why this exists
    Invalid public URLs should fail fast with actionable guidance instead of silently emitting unusable pairing data.
    """
    try:
        override = _read_public_base_url_override()
        if override is None:
            return default_url
        _validate_public_base_url(candidate=override)
        return override
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_resolve_public_base_url", "Invalid public base URL override", exc)
        ) from exc


def _read_public_base_url_override() -> str | None:
    """
    Summary
    Read and normalize the public base URL environment override.

    Inputs
    None.

    Outputs
    Stripped URL override or `None` when unset.

    Side effects
    Reads an environment variable.

    Error handling
    Raises `ValueError` when the variable is set but empty.

    Ties to other methods
    Used by `resolve_public_base_url`.

    Why this exists
    Empty environment overrides are configuration mistakes and should be reported clearly.
    """
    override = os.getenv("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL")
    if override is None:
        return None
    candidate = override.strip()
    if not candidate:
        raise ValueError(
            "MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL is set but empty. "
            "Set it to an absolute http(s) URL or unset the variable."
        )
    return candidate


def _validate_public_base_url(*, candidate: str) -> None:
    """
    Summary
    Validate the structure of a public base URL override.

    Inputs
    candidate: URL string to validate.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the URL is invalid.

    Ties to other methods
    Used by `resolve_public_base_url`.

    Why this exists
    Pairing payloads depend on a strict base URL shape and should reject malformed values early.
    """
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            f"MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL must start with http:// or https:// (received {candidate!r})"
        )
    if not parsed.netloc:
        raise ValueError(
            "MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL must include host[:port], "
            f"for example https://example.test:7878 (received {candidate!r})"
        )
    if parsed.path not in ("", "/") or parsed.params or parsed.query or parsed.fragment:
        raise ValueError(
            "MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL must not include path, query, or fragment. "
            f"Use only scheme://host[:port] (received {candidate!r})"
        )
