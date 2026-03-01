from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import fmt_bytes, fmt_percent
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils import health_from_percent
from mac_health_checkup.core.utils import (
    regex_extract_float,
    regex_extract_int,
    regex_extract_str,
)
from mac_health_checkup.core.utils import safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/ssd.py"


class SSDDiagnostics:
    """
    Summary
    Collect SSD health and lifetime details.

    Inputs
    None. Executes smartctl.

    Outputs
    Dict with SSD health and telemetry fields.

    Side effects
    Executes smartctl and may use sudo (depending on config and tool behavior).

    Error handling
    Returns fallback values when smartctl output is missing; raises `RuntimeError` with module and method context
    when parsing fails unexpectedly.

    Ties to other methods
    Used by the SSD section in the GUI.

    Why this exists
    Provides SSD health insight and lifetime estimates.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch SSD details with caching.

        Inputs
        None.

        Outputs
        Dict with SSD fields and summary.

        Side effects
        Executes smartctl when the cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by the SSD section handler.

        Why this exists
        Keeps SSD details fresh while avoiding repeated IO.
        """
        try:
            return cached_fetch(SSDDiagnostics._cache, "ssd", SSDDiagnostics._fetch_uncached)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SSDDiagnostics.fetch", "Failed to fetch SSD", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch SSD details without caching.

        Inputs
        None.

        Outputs
        Dict with SSD fields and summary.

        Side effects
        Executes smartctl.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Separates IO from caching logic for testing.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("SSDDiagnostics")
            allow_sudo = get_config().fans.use_sudo
            out, err = safe_run(
                ["smartctl", "-a", "/dev/disk0"],
                context="ssd",
                allow_sudo=allow_sudo,
                timeout=get_config().timeouts.smartctl_timeout,
            )
            if not out:
                logger.warning(
                    "smartctl returned no output",
                    event="ssd_empty",
                    context=context,
                    payload={"error": err or ""},
                )
                return {"health_text": "SSD not accessible", "raw": ""}
            percent_used = regex_extract_int(out, r"Percentage Used:\s*(\d+)%")
            percent_left = 100.0 - float(percent_used) if percent_used is not None else None
            written_tb = regex_extract_float(out, r"Data Units Written:\s+[\d,]+\s*\[([0-9.]+) TB\]")
            read_tb = regex_extract_float(out, r"Data Units Read:\s+[\d,]+\s*\[([0-9.]+) TB\]")
            firmware = regex_extract_str(out, re.escape("Firmware Version") + r":\s+([^\n]+)")
            power_cycles = regex_extract_int(out, re.escape("Power Cycles") + r":\s+([^\n]+)")
            power_on_hours = regex_extract_int(out, re.escape("Power On Hours") + r":\s+([^\n]+)")
            unsafe_shutdowns = regex_extract_int(out, re.escape("Unsafe Shutdowns") + r":\s+([^\n]+)")
            media_errors = regex_extract_int(
                out, re.escape("Media and Data Integrity Errors") + r":\s+([^\n]+)"
            )
            thresholds = get_config().thresholds
            health_label = (
                health_from_percent(
                    percent_left,
                    excellent_min=thresholds.health_excellent_min_percent,
                    good_min=thresholds.health_good_min_percent,
                    fair_min=thresholds.health_fair_min_percent,
                )
                if percent_left is not None
                else "unknown"
            )
            summary = "SSD health unavailable"
            if percent_left is not None:
                summary = f"{fmt_percent(percent_left)} left | {fmt_bytes((written_tb or 0.0) * 1e12)} written | {health_label}"
            return {
                "percent_left": percent_left,
                "data_written": written_tb,
                "data_read": read_tb,
                "firmware": firmware,
                "power_cycles": power_cycles,
                "power_on_hours": power_on_hours,
                "unsafe_shutdowns": unsafe_shutdowns,
                "media_errors": media_errors,
                "health_text": summary,
                "raw": out,
            }
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SSDDiagnostics._fetch_uncached", "SSD parsing failed", exc)
            ) from exc
