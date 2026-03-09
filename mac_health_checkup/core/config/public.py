from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
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
_CACHE_LOCK = Lock()
_STARTUP_ENV_OVERRIDES: tuple[str, ...] = (
    "MAC_HEALTH_CHECKUP_CONFIG",
    "MAC_HEALTH_CHECKUP_CONFIG_MAX_BYTES",
    "MAC_HEALTH_CHECKUP_API_AUTH_TOKEN",
    "MAC_HEALTH_CHECKUP_API_BIND_HOST",
    "MAC_HEALTH_CHECKUP_API_PORT",
    "MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL",
)


@dataclass(frozen=True)
class StartupConfigValidationReport:
    """
    Summary
    Capture startup config validation details for deterministic observability.

    Inputs
    config_path: Resolved config file path.
    config_max_bytes: Active max file-size limit.
    env_overrides: Environment override variable names present at startup.
    api_enabled: Effective API enabled flag.
    api_bind_host: Effective API bind host.
    api_port: Effective API port.

    Outputs
    Immutable startup validation report.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `build_startup_config_validation_report` and logged by startup entrypoints.

    Why this exists
    Gives operators a safe, structured report proving which config contract was validated at startup.
    """

    config_path: str
    config_max_bytes: int
    env_overrides: tuple[str, ...]
    api_enabled: bool
    api_bind_host: str
    api_port: int

    def to_log_payload(self) -> JsonDict:
        """
        Summary
        Convert the report into a structured JSON payload for logging.

        Inputs
        None.

        Outputs
        `JsonDict` payload.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when payload serialization fails unexpectedly.

        Ties to other methods
        Used by startup entrypoints when writing the `startup_config_validated` event.

        Why this exists
        Keeps report logging deterministic and free from ad-hoc dictionary assembly.
        """
        try:
            return {
                "config_path": self.config_path,
                "config_max_bytes": self.config_max_bytes,
                "env_overrides": list(self.env_overrides),
                "api_enabled": self.api_enabled,
                "api_bind_host": self.api_bind_host,
                "api_port": self.api_port,
            }
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "StartupConfigValidationReport.to_log_payload",
                    "Failed to convert report to payload",
                    exc,
                )
            ) from exc


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
        with _CACHE_LOCK:
            _CONFIG_CACHE = None
            _RAW_CACHE = None
            _RAW_CACHE_PATH = None
            _CONFIG_CACHE_PATH = None
    except (RuntimeError, NameError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "reset_config_cache", "Failed to reset cache", exc)
        ) from exc


def build_startup_config_validation_report(config: Config) -> StartupConfigValidationReport:
    """
    Summary
    Build a startup config validation report from the active typed config.

    Inputs
    config: Parsed typed config instance used by the running process.

    Outputs
    `StartupConfigValidationReport`.

    Side effects
    Reads environment variables and config path metadata.

    Error handling
    Raises `RuntimeError` with module and method context when report assembly fails.

    Ties to other methods
    Called by application entrypoints after `get_config` succeeds.

    Why this exists
    Startup should emit one machine-readable proof that config/env contract validation passed.
    """
    try:
        config_path = resolve_config_path()
        max_bytes = config_max_bytes()
        active_overrides = tuple(name for name in _STARTUP_ENV_OVERRIDES if name in os.environ)
        return StartupConfigValidationReport(
            config_path=str(config_path),
            config_max_bytes=max_bytes,
            env_overrides=active_overrides,
            api_enabled=bool(config.api.enabled),
            api_bind_host=str(config.api.bind_host),
            api_port=int(config.api.port),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "build_startup_config_validation_report",
                "Failed to build startup config validation report",
                exc,
            )
        ) from exc


@overload
def get_config_value(path: str, default: bool, validator: Callable[[JsonValue], bool] | None = None) -> bool:
    """
    Summary
    Execute `get_config_value` for its module-level responsibility.

    Inputs
    path: `str` parameter from the function signature.
    default: `bool` parameter from the function signature.
    validator: `Callable[[JsonValue], bool] | None` parameter from the function signature with a default.

    Outputs
    Returns `bool`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/core/config/public.py:get_config_value` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/core/config/public.py`.

    Why this exists
    Keeps `get_config_value` explicit, testable, and maintainable.
    """
    ...


@overload
def get_config_value(path: str, default: int, validator: Callable[[JsonValue], int] | None = None) -> int:
    """
    Summary
    Execute `get_config_value` for its module-level responsibility.

    Inputs
    path: `str` parameter from the function signature.
    default: `int` parameter from the function signature.
    validator: `Callable[[JsonValue], int] | None` parameter from the function signature with a default.

    Outputs
    Returns `int`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/core/config/public.py:get_config_value` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/core/config/public.py`.

    Why this exists
    Keeps `get_config_value` explicit, testable, and maintainable.
    """
    ...


@overload
def get_config_value(
    path: str, default: float, validator: Callable[[JsonValue], float] | None = None
) -> float:
    """
    Summary
    Execute `get_config_value` for its module-level responsibility.

    Inputs
    path: `str` parameter from the function signature.
    default: `float` parameter from the function signature.
    validator: `Callable[[JsonValue], float] | None` parameter from the function signature with a default.

    Outputs
    Returns `float`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/core/config/public.py:get_config_value` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/core/config/public.py`.

    Why this exists
    Keeps `get_config_value` explicit, testable, and maintainable.
    """
    ...


@overload
def get_config_value(path: str, default: str, validator: Callable[[JsonValue], str] | None = None) -> str:
    """
    Summary
    Execute `get_config_value` for its module-level responsibility.

    Inputs
    path: `str` parameter from the function signature.
    default: `str` parameter from the function signature.
    validator: `Callable[[JsonValue], str] | None` parameter from the function signature with a default.

    Outputs
    Returns `str`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/core/config/public.py:get_config_value` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/core/config/public.py`.

    Why this exists
    Keeps `get_config_value` explicit, testable, and maintainable.
    """
    ...


@overload
def get_config_value(
    path: str, default: list[JsonValue], validator: Callable[[JsonValue], list[JsonValue]] | None = None
) -> list[JsonValue]:
    """
    Summary
    Execute `get_config_value` for its module-level responsibility.

    Inputs
    path: `str` parameter from the function signature.
    default: `list[JsonValue]` parameter from the function signature.
    validator: `Callable[[JsonValue], list[JsonValue]] | None` parameter from the function signature with a default.

    Outputs
    Returns `list[JsonValue]`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/core/config/public.py:get_config_value` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/core/config/public.py`.

    Why this exists
    Keeps `get_config_value` explicit, testable, and maintainable.
    """
    ...


@overload
def get_config_value(
    path: str,
    default: dict[str, JsonValue],
    validator: Callable[[JsonValue], dict[str, JsonValue]] | None = None,
) -> dict[str, JsonValue]:
    """
    Summary
    Execute `get_config_value` for its module-level responsibility.

    Inputs
    path: `str` parameter from the function signature.
    default: `dict[str, JsonValue]` parameter from the function signature.
    validator: `Callable[[JsonValue], dict[str, JsonValue]] | None` parameter from the function signature with a default.

    Outputs
    Returns `dict[str, JsonValue]`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/core/config/public.py:get_config_value` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/core/config/public.py`.

    Why this exists
    Keeps `get_config_value` explicit, testable, and maintainable.
    """
    ...


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
        with _CACHE_LOCK:
            cached = _CONFIG_CACHE
            cached_path = _CONFIG_CACHE_PATH
        if cached is not None and cached_path == config_path:
            return cached

        raw = _load_raw_config_for_path(config_path)
        parsed = parse_config(raw)
        with _CACHE_LOCK:
            _CONFIG_CACHE = parsed
            _CONFIG_CACHE_PATH = config_path
        return parsed
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
        config_path = resolve_config_path()
        return _load_raw_config_for_path(config_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "load_raw_config", "Failed to load config", exc)
        ) from exc


def _load_raw_config_for_path(config_path: Path) -> JsonDict:
    """
    Summary
    Load raw config JSON for a specific resolved config path with caching.

    Inputs
    config_path: Resolved config path.

    Outputs
    Raw config dict decoded from JSON.

    Side effects
    Reads from disk and updates the raw config cache for the given path.

    Error handling
    Raises `RuntimeError` with module and method context when reading or decoding fails.

    Ties to other methods
    Used by `get_config` and `load_raw_config` to ensure both caches stay consistent under concurrency.

    Why this exists
    `ThreadingHTTPServer` and UI refresh loops can access config concurrently; caching must be thread-safe.
    """
    try:
        global _RAW_CACHE, _RAW_CACHE_PATH
        with _CACHE_LOCK:
            cached = _RAW_CACHE
            cached_path = _RAW_CACHE_PATH
        if cached is not None and cached_path == config_path:
            return cached

        max_bytes = config_max_bytes()
        raw_text = read_config_file(config_path, max_bytes)
        data = json.loads(raw_text)
        if not isinstance(data, dict):
            raise ValueError("config root must be object")
        with _CACHE_LOCK:
            _RAW_CACHE = data
            _RAW_CACHE_PATH = config_path
        return data
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_load_raw_config_for_path", "Failed to load raw config for path", exc)
        ) from exc
