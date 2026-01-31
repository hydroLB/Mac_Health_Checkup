from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, overload

from mac_health_checkup.core.config.io import config_max_bytes, read_config_file, resolve_config_path
from mac_health_checkup.core.config.lookup import coerce_value, get_nested_value
from mac_health_checkup.core.config.models.root import Config
from mac_health_checkup.core.config.parsing.root import parse_config
from mac_health_checkup.core.types import JsonDict, JsonValue
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/public.py"

_CONFIG_CACHE: Config | None = None
_RAW_CACHE: JsonDict | None = None
_RAW_CACHE_PATH: Path | None = None
_CONFIG_CACHE_PATH: Path | None = None


def reset_config_cache() -> None:
    """
    Summary
    Clear cached raw and parsed config data.

    Inputs
    None.

    Outputs
    None.

    Side effects
    Clears in-memory caches used by `get_config` and `get_config_value`.

    Error handling
    Raises `RuntimeError` with module and method context when cache reset fails unexpectedly.

    Ties to other methods
    Used by tests that monkeypatch config environment variables.

    Why this exists
    Ensures config changes are reloaded deterministically without requiring process restarts.
    """
    try:
        global _CONFIG_CACHE, _RAW_CACHE, _RAW_CACHE_PATH, _CONFIG_CACHE_PATH
        _CONFIG_CACHE = None
        _RAW_CACHE = None
        _RAW_CACHE_PATH = None
        _CONFIG_CACHE_PATH = None
    except (RuntimeError, NameError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "reset_config_cache", "Failed to reset cache", exc)
        ) from exc


@overload
def get_config_value(
    path: str, default: bool, validator: Callable[[JsonValue], bool] | None = None
) -> bool: ...


@overload
def get_config_value(path: str, default: int, validator: Callable[[JsonValue], int] | None = None) -> int: ...


@overload
def get_config_value(
    path: str, default: float, validator: Callable[[JsonValue], float] | None = None
) -> float: ...


@overload
def get_config_value(path: str, default: str, validator: Callable[[JsonValue], str] | None = None) -> str: ...


@overload
def get_config_value(
    path: str, default: list[JsonValue], validator: Callable[[JsonValue], list[JsonValue]] | None = None
) -> list[JsonValue]: ...


@overload
def get_config_value(
    path: str,
    default: dict[str, JsonValue],
    validator: Callable[[JsonValue], dict[str, JsonValue]] | None = None,
) -> dict[str, JsonValue]: ...


def get_config_value(
    path: str, default: JsonValue, validator: Callable[[JsonValue], JsonValue] | None = None
) -> JsonValue:
    """
    Summary
    Retrieve a config override by dotted path with safe fallback.

    Inputs
    path: Dotted path such as `logging.max_lines`.
    default: Default value when the path is missing or invalid.
    validator: Optional validator that returns a typed value or raises `ValueError`.

    Outputs
    Config value when present and valid, otherwise the provided default.

    Side effects
    Reads and caches config JSON from disk.

    Error handling
    Raises `RuntimeError` with module and method context when config loading fails.

    Ties to other methods
    Uses `load_raw_config` and `get_nested_value` for retrieval, and `coerce_value` when no validator is supplied.

    Why this exists
    Supports small targeted config lookups without forcing every consumer to depend on the full typed registry.
    """
    try:
        raw = load_raw_config()
        value = get_nested_value(raw, path)
        if value is None:
            return default
        if validator is not None:
            try:
                return validator(value)
            except ValueError:
                return default
        return coerce_value(default, value)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "get_config_value", "Failed to read config value", exc)
        ) from exc


def get_config() -> Config:
    """
    Summary
    Return the parsed typed config registry.

    Inputs
    None.

    Outputs
    `Config` instance.

    Side effects
    Caches the parsed config and reads config JSON from disk when needed.

    Error handling
    Raises `RuntimeError` with module and method context when config parsing fails.

    Ties to other methods
    Calls `resolve_config_path`, `load_raw_config`, and `parse_config`.

    Why this exists
    Provides a single source of truth for validated, strongly typed configuration across the application.
    """
    try:
        global _CONFIG_CACHE, _CONFIG_CACHE_PATH
        config_path = resolve_config_path()
        if _CONFIG_CACHE is not None and _CONFIG_CACHE_PATH == config_path:
            return _CONFIG_CACHE
        raw = load_raw_config()
        _CONFIG_CACHE = parse_config(raw)
        _CONFIG_CACHE_PATH = config_path
        return _CONFIG_CACHE
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "get_config", "Failed to build config", exc)) from exc


def load_raw_config() -> JsonDict:
    """
    Summary
    Load raw config JSON from disk with caching and bounds.

    Inputs
    None.

    Outputs
    Raw config dict decoded from JSON.

    Side effects
    Reads from disk and caches the decoded JSON dict.

    Error handling
    Raises `RuntimeError` with module and method context when the config cannot be loaded or decoded.

    Ties to other methods
    Uses `resolve_config_path`, `config_max_bytes`, and `read_config_file`.

    Why this exists
    Provides one bounded IO entrypoint for all config reads, reducing the chance of inconsistent cache behavior.
    """
    try:
        global _RAW_CACHE, _RAW_CACHE_PATH
        config_path = resolve_config_path()
        if _RAW_CACHE is not None and _RAW_CACHE_PATH == config_path:
            return _RAW_CACHE
        max_bytes = config_max_bytes()
        raw_text = read_config_file(config_path, max_bytes)
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("config root must be object")
        _RAW_CACHE = data
        _RAW_CACHE_PATH = config_path
        return data
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "load_raw_config", "Failed to load config", exc)
        ) from exc
