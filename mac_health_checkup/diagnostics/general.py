from __future__ import annotations

import platform

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.regex_utils import regex_extract_str
from mac_health_checkup.core.utils.shell import system_profiler_out
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/general.py"


class GeneralDiagnostics:
    """
    Purpose: Collect general system information for display.
    Ties: Used by the General section in the GUI.
    Inputs: None. Reads system_profiler output.
    Outputs: Dict with model, chip, os, serial, and raw data.
    Side effects: Executes system_profiler.
    Why: Provides core identity data for the dashboard.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Purpose: Fetch general system details with caching.
        Ties: Called by General section handler.
        Inputs: None.
        Outputs: Dict with model, chip, os, serial, raw.
        Side effects: Reads system_profiler output.
        Why: Provides core machine information for the UI.
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
        Purpose: Fetch general system details without caching.
        Ties: Used by cached_fetch.
        Inputs: None.
        Outputs: Dict with model, chip, os, serial, raw.
        Side effects: Executes system_profiler.
        Why: Separates IO from caching logic for testing.
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
