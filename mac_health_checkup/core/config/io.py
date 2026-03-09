from __future__ import annotations

import os
from pathlib import Path

from mac_health_checkup.core.config.validation.primitives import require_int
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/io.py"


def resolve_config_path() -> Path:
    """
    Summary
    Resolve the JSON config path from environment or defaults.

    Inputs
    None.

    Outputs
    `Path` to the config file.

    Side effects
    Reads `MAC_HEALTH_CHECKUP_CONFIG`.

    Error handling
    Raises `RuntimeError` with module and method context when path resolution fails.

    Ties to other methods
    Used by `load_raw_config` and `get_config` to determine whether cached values are still valid.

    Why this exists
    Allows operators to point the tool at different config files without code edits.
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
        return Path("config") / "config.json"
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
        data = path.read_bytes()
        if len(data) > max_bytes:
            raise ValueError(f"config file too large: {len(data)} bytes")
        return data.decode("utf-8")
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "read_config_file", "Failed to read config file", exc)
        ) from exc
