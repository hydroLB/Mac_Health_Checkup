from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from mac_health_checkup.core.config.validation.primitives import require_int
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/io.py"
_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_CHECKOUT_MARKER_CONTENT = b"mac-health-checkup-source-checkout-v1\n"
_SOURCE_CHECKOUT_MARKER_PATH = _PACKAGE_ROOT.parent / ".mac-health-checkup-source"
_SOURCE_CHECKOUT_CONFIG_PATH = _PACKAGE_ROOT.parent / "config" / "config.json"
_PACKAGED_CONFIG_PATH = _PACKAGE_ROOT / "resources" / "default_config.json"


@lru_cache(maxsize=1)
def _has_source_checkout_marker() -> bool:
    """
    Summary
    Validate the project-specific marker beside an importable source checkout.

    Inputs
    None.

    Outputs
    `True` only when the marker exists with the exact expected bounded content.

    Side effects
    Reads at most the fixed marker payload plus one byte from disk on the first call in a process.

    Error handling
    Returns `False` when the marker is missing, inaccessible, or malformed.

    Ties to other methods
    Used by `resolve_config_path` before allowing a config adjacent to the package source tree.

    Why this exists
    Package location alone cannot distinguish a checkout from an installed wheel with an unrelated sibling config.
    The marker is immutable repository identity, so caching avoids a filesystem read on every config lookup.
    """
    try:
        with _SOURCE_CHECKOUT_MARKER_PATH.open("rb") as marker:
            return marker.read(len(_SOURCE_CHECKOUT_MARKER_CONTENT) + 1) == (_SOURCE_CHECKOUT_MARKER_CONTENT)
    except OSError:
        return False


@lru_cache(maxsize=1)
def _default_config_path() -> Path:
    """
    Summary
    Resolve and cache the immutable default path for this installation or checkout.

    Inputs
    None.

    Outputs
    Source-checkout config path when the project marker is valid; otherwise the packaged default path.

    Side effects
    Checks the source config path on the first call in a process.

    Error handling
    Propagates unexpected filesystem errors to `resolve_config_path` for contextual wrapping.

    Ties to other methods
    Used by `resolve_config_path` only when no explicit environment override is present.

    Why this exists
    Checkout identity does not change during a process, and repeated path syscalls distorted hot config lookups and
    parser benchmarks.
    """
    if _has_source_checkout_marker() and _SOURCE_CHECKOUT_CONFIG_PATH.is_file():
        return _SOURCE_CHECKOUT_CONFIG_PATH
    return _PACKAGED_CONFIG_PATH


def resolve_config_path() -> Path:
    """
    Summary
    Resolve the JSON config path from an explicit override, source checkout, or packaged default.

    Inputs
    None.

    Outputs
    `Path` to the selected config file, with the source checkout's config taking precedence over package data.

    Side effects
    Reads `MAC_HEALTH_CHECKUP_CONFIG` and checks for config adjacent to the importable source package.

    Error handling
    Raises `RuntimeError` with module and method context when path resolution fails.

    Ties to other methods
    Used by `load_raw_config` and `get_config` to determine whether cached values are still valid.

    Why this exists
    Keeps source-checkout overrides intact without implicitly trusting config files in an installed CLI's caller directory.
    """
    try:
        env_name = "MAC_HEALTH_CHECKUP_CONFIG"
        if env_name in os.environ:
            override = os.environ.get(env_name, "")
            if not override.strip():
                raise ValueError(
                    f"{env_name} is set but empty. Set it to a config file path or unset the variable."
                )
            return Path(override.strip()).expanduser()
        return _default_config_path()
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "resolve_config_path", "Failed to resolve config path", exc)
        ) from exc


def config_max_bytes() -> int:
    """
    Summary
    Resolve the max config size in bytes.

    Inputs
    None.

    Outputs
    Max size in bytes as an int.

    Side effects
    Reads `MAC_HEALTH_CHECKUP_CONFIG_MAX_BYTES`.

    Error handling
    Raises `RuntimeError` with module and method context when the value is invalid.

    Ties to other methods
    Used by `read_config_file` and `load_raw_config` to prevent oversized reads.

    Why this exists
    Avoids unbounded reads when a config path is misconfigured or points to an unexpected file.
    """
    try:
        env_name = "MAC_HEALTH_CHECKUP_CONFIG_MAX_BYTES"
        if env_name in os.environ:
            override = os.environ.get(env_name, "")
            if not override.strip():
                raise ValueError(
                    f"{env_name} is set but empty. Set it to an integer byte limit or unset the variable."
                )
            return require_int(1, 10_000_000)(override.strip())
        return 1_048_576
    except (TypeError, ValueError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "config_max_bytes", "Invalid size limit", exc)) from exc


def read_config_file(path: Path, max_bytes: int) -> str:
    """
    Summary
    Read a JSON config file with a size bound.

    Inputs
    path: File path to read.
    max_bytes: Maximum allowed file size.

    Outputs
    UTF-8 decoded file contents.

    Side effects
    Reads from disk.

    Error handling
    Raises `RuntimeError` with module and method context on file, size, or decoding errors.

    Ties to other methods
    Used by `load_raw_config` before JSON decoding.

    Why this exists
    Keeps config loading deterministic and safe even when input paths are user controlled.
    """
    try:
        if not path.exists():
            raise FileNotFoundError(f"config file not found at {path}")
        with path.open("rb") as config_file:
            data = config_file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"config file too large: {len(data)} bytes")
        return data.decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "read_config_file", "Failed to read config file", exc)
        ) from exc
