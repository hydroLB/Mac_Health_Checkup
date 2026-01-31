from __future__ import annotations

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.shell import safe_run, system_profiler_out
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/display.py"


class DisplayDiagnostics:
    """
    Purpose: Collect raw display information.
    Ties: Used by display parsing in the GUI.
    Inputs: None. Executes system_profiler.
    Outputs: Dict with raw display output.
    Side effects: Executes system_profiler.
    Why: Provides the raw source used for parsing display details.
    """

    _cache = Cache(get_config().timeouts.display_cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Purpose: Fetch display output with caching.
        Ties: Used by display section handler.
        Inputs: None.
        Outputs: Dict with raw display output.
        Side effects: Executes system_profiler.
        Why: Avoids repeated display queries while keeping data fresh.
        """
        try:
            return cached_fetch(DisplayDiagnostics._cache, "display", DisplayDiagnostics._fetch_uncached)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DisplayDiagnostics.fetch", "Failed to fetch display", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Purpose: Fetch display output without caching.
        Ties: Used by cached_fetch.
        Inputs: None.
        Outputs: Dict with raw display output.
        Side effects: Executes system_profiler.
        Why: Separates IO from caching logic for testing.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("DisplayDiagnostics")
            out, err = system_profiler_out("SPDisplaysDataType", context="display")
            if not out:
                logger.warning(
                    "display output empty",
                    event="display_empty",
                    context=context,
                    payload={"error": err or ""},
                )
            raw = out or ""
            payload: JsonDict = {"raw": raw}
            if not _looks_like_display_inventory(raw):
                ioreg_out, ioreg_err = safe_run(
                    ["ioreg", "-lw0", "-r", "-c", "IOMobileFramebufferShim"],
                    context="display_ioreg",
                    allow_sudo=False,
                    timeout=max(3, get_config().timeouts.default_cmd_timeout),
                )
                if not ioreg_out:
                    logger.warning(
                        "display ioreg empty",
                        event="display_ioreg_empty",
                        context=context,
                        payload={"error": ioreg_err or ""},
                    )
                    payload["raw_ioreg"] = ""
                    payload["raw_ioreg_error"] = ioreg_err or ""
                else:
                    payload["raw_ioreg"] = ioreg_out
            return payload
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DisplayDiagnostics._fetch_uncached", "Display fetch failed", exc)
            ) from exc


def _looks_like_display_inventory(raw: str) -> bool:
    """
    Purpose: Decide whether system_profiler output contains per-display inventory details.
    Ties: Used by DisplayDiagnostics to decide when to fall back to IORegistry parsing.
    Inputs: raw is system_profiler output.
    Outputs: True when the output appears to include at least one display block.
    Side effects: None.
    Why: Newer macOS builds can omit display blocks from SPDisplaysDataType; IORegistry provides a reliable fallback.
    """
    try:
        if not raw:
            return False
        lower = raw.lower()
        return "resolution:" in lower or "refresh rate:" in lower or "connection type:" in lower
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH, "_looks_like_display_inventory", "Failed to check display inventory", exc
            )
        ) from exc
