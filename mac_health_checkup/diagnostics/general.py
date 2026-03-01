from __future__ import annotations

import platform

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils import regex_extract_str
from mac_health_checkup.core.utils import system_profiler_out
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/general.py"


class GeneralDiagnostics:
    """
    Summary
    Collect general system information for display.

    Inputs
    None. Reads system_profiler output.

    Outputs
    Dict with model, chip, os, serial, and raw data.

    Side effects
    Executes system_profiler.

    Error handling
    Returns fallback identity values when system_profiler output is missing.

    Ties to other methods
    Used by the General section in the GUI.

    Why this exists
    Provides core identity data for the dashboard.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch general system details with caching.

        Inputs
        None.

        Outputs
        Dict with model, chip, os, serial, raw.

        Side effects
        Reads system_profiler output when the cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Called by the General section handler.

        Why this exists
        Provides core machine information for the UI.
        """
        try:
            return cached_fetch(GeneralDiagnostics._cache, "general", GeneralDiagnostics._fetch_uncached)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "GeneralDiagnostics.fetch", "Failed to fetch general info", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch general system details without caching.

        Inputs
        None.

        Outputs
        Dict with model, chip, os, serial, raw.

        Side effects
        Executes system_profiler.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Separates IO from caching logic for testing.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("GeneralDiagnostics")
            raw, err = system_profiler_out("SPHardwareDataType", context="general")
            if not raw:
                logger.warning(
                    "system_profiler returned no output",
                    event="general_empty",
                    context=context,
                    payload={"error": err or ""},
                )
                return {
                    "model": "Unknown",
                    "chip": "Unknown",
                    "os": platform.mac_ver()[0],
                    "serial": "Unknown",
                    "raw": "",
                }
            model = regex_extract_str(raw, r"Model Name:\s*(.+)") or "Unknown"
            chip = (
                regex_extract_str(raw, r"Chip:\s*(.+)")
                or regex_extract_str(raw, r"Processor Name:\s*(.+)")
                or "Unknown"
            )
            serial = regex_extract_str(raw, r"Serial Number \(system\):\s*(.+)") or "Unknown"
            os_version = platform.mac_ver()[0]
            return {"model": model, "chip": chip, "os": os_version, "serial": serial, "raw": raw}
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "GeneralDiagnostics._fetch_uncached", "Failed to parse general info", exc
                )
            ) from exc
