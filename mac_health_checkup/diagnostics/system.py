from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils import safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/system.py"

_DF_USE_RE = re.compile(r"(\d+)%")
_MEM_FREE_RE = re.compile(r"System-wide memory free percentage:\s*([0-9.]+)%", re.IGNORECASE)


class SystemPressureDiagnostics:
    """
    Summary
    Collect system pressure signals (storage and memory) using read-only commands.

    Inputs
    None.

    Outputs
    Dict containing disk free percentage and memory free percentage.

    Side effects
    Executes `df` and `memory_pressure`.

    Error handling
    Returns `ok=false` when neither disk nor memory signals can be collected.

    Ties to other methods
    Used by the System section (`mac_health_checkup/app/gui/sections/system.py`).

    Why this exists
    Storage and memory pressure are common causes of degraded performance and instability. A lightweight, read-only
    summary makes the dashboard more actionable.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch system pressure signals with caching.

        Inputs
        None.

        Outputs
        Diagnostics dict with disk/memory pressure values and raw outputs.

        Side effects
        Executes bounded commands when cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching logic fails unexpectedly.

        Ties to other methods
        Used by System section refresh loops.

        Why this exists
        Prevents frequent `df` and `memory_pressure` calls during UI refreshes.
        """
        try:
            return cached_fetch(
                SystemPressureDiagnostics._cache, "system_pressure", SystemPressureDiagnostics._fetch_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "SystemPressureDiagnostics.fetch", "Failed to fetch system pressure", exc
                )
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch system pressure signals without caching.

        Inputs
        None.

        Outputs
        Diagnostics dict.

        Side effects
        Executes `df` and `memory_pressure`.

        Error handling
        Never raises for command failures; returns partial results when available.

        Ties to other methods
        Wrapped by `fetch` via `cached_fetch`.

        Why this exists
        Systems vary in tool availability; partial results are still useful.
        """
        logger = get_diagnostics_logger()
        context = new_context("SystemPressureDiagnostics")
        try:
            timeout = int(get_config().timeouts.default_cmd_timeout)

            df_out, df_err = safe_run(["df", "-k", "/"], context="df_root", allow_sudo=False, timeout=timeout)
            disk = _parse_df_root(df_out or "")

            mp_out, mp_err = safe_run(
                ["memory_pressure"], context="memory_pressure", allow_sudo=False, timeout=timeout
            )
            memory = _parse_memory_pressure(mp_out or "")

            ok_any = disk.get("free_percent") is not None or memory.get("free_percent") is not None
            if not ok_any:
                logger.warning(
                    "system pressure unavailable",
                    event="system_pressure_unavailable",
                    context=context,
                    payload={"df_error": df_err or "", "memory_pressure_error": mp_err or ""},
                )
            return {
                "ok": ok_any,
                "disk": {**disk, "raw": df_out or "", "error": df_err or ""},
                "memory": {**memory, "raw": mp_out or "", "error": mp_err or ""},
            }
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError) as exc:
            logger.warning(
                "system pressure collection failed",
                event="system_pressure_error",
                context=context,
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            return {
                "ok": False,
                "error": format_error(
                    MODULE_PATH,
                    "SystemPressureDiagnostics._fetch_uncached",
                    "Failed to collect system pressure",
                    exc,
                ),
            }


def _parse_df_root(text: str) -> JsonDict:
    """
    Summary
    Parse `df -k /` output and compute free percentage.

    Inputs
    text: Raw df output.

    Outputs
    Dict with `used_percent` and `free_percent` floats or None.

    Side effects
    None.

    Error handling
    Never raises; returns unknown values on malformed input.

    Ties to other methods
    Used by `SystemPressureDiagnostics._fetch_uncached`.

    Why this exists
    Disk pressure is best represented by percent free, independent of disk size.
    """
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if len(lines) < 2:
        return {"used_percent": None, "free_percent": None}
    data_line = lines[-1]
    parts = [p for p in data_line.split() if p]
    if len(parts) < 5:
        return {"used_percent": None, "free_percent": None}
    # Typical: Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted on
    cap = parts[4]
    match = _DF_USE_RE.search(cap)
    if not match:
        return {"used_percent": None, "free_percent": None}
    try:
        used = float(match.group(1))
    except ValueError:
        return {"used_percent": None, "free_percent": None}
    used = max(0.0, min(100.0, used))
    return {"used_percent": used, "free_percent": 100.0 - used}


def _parse_memory_pressure(text: str) -> JsonDict:
    """
    Summary
    Parse `memory_pressure` output and extract system-wide free percentage when available.

    Inputs
    text: Raw memory_pressure output.

    Outputs
    Dict with `free_percent` float or None.

    Side effects
    None.

    Error handling
    Never raises; returns unknown values on malformed input.

    Ties to other methods
    Used by `SystemPressureDiagnostics._fetch_uncached`.

    Why this exists
    The built-in tool provides a stable signal without requiring privileged access.
    """
    match = _MEM_FREE_RE.search(text or "")
    if not match:
        return {"free_percent": None}
    try:
        value = float(match.group(1))
    except ValueError:
        return {"free_percent": None}
    value = max(0.0, min(100.0, value))
    return {"free_percent": value}
