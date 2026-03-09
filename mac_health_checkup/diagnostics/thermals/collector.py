from __future__ import annotations

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context
from mac_health_checkup.diagnostics.thermals.hid_event_system import collect_temperature_readings

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/collector.py"


class ThermalSensorsDiagnostics:
    """
    Summary
    Collect temperature sensor readings using IOHIDEventSystemClient.

    Inputs
    None.

    Outputs
    Dict with sensors and raw debug lines.

    Side effects
    Calls into CoreFoundation and IOKit via ctypes.

    Error handling
    Returns `ok=false` with an error string when sensors cannot be collected.

    Ties to other methods
    Used by the Performance section (`mac_health_checkup/app/gui/sections/performance.py`).

    Why this exists
    `powermetrics` is increasingly restricted on newer macOS builds. IOHID temperature sensors can often be queried without sudo and provide stable per-sensor values.
    """

    _cache = Cache(get_config().timeouts.performance_cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch temperature sensor readings with caching.

        Inputs
        None.

        Outputs
        Diagnostics dict with `ok`, `sensors`, and `raw`.

        Side effects
        May call IOHID temperature sensors if cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching logic fails unexpectedly.

        Ties to other methods
        Used by section handlers to avoid repeated low-level calls in refresh loops.

        Why this exists
        Keeps the UI responsive while still updating sensor values frequently.
        """
        try:
            return cached_fetch(
                ThermalSensorsDiagnostics._cache,
                "thermal_sensors",
                ThermalSensorsDiagnostics._fetch_uncached,
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "ThermalSensorsDiagnostics.fetch", "Failed to fetch thermal sensors", exc
                )
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch temperature sensor readings without caching.

        Inputs
        None.

        Outputs
        Diagnostics dict.

        Side effects
        Queries IOHID services and reads temperature events.

        Error handling
        Never raises for IOHID failures; returns `ok=false` with guidance instead.

        Ties to other methods
        Wrapped by `fetch` via `cached_fetch`.

        Why this exists
        Snapshot building should be resilient: temperature sensors are optional and availability varies by macOS build.
        """
        logger = get_diagnostics_logger()
        context = new_context("ThermalSensorsDiagnostics")
        try:
            result = collect_temperature_readings()
            raw_text = "\n".join(line for line in result.raw_lines if line.strip())
            ok = bool(result.readings)
            if not ok:
                logger.warning(
                    "no temperature sensors returned data",
                    event="thermals_empty",
                    context=context,
                    payload={"error": result.error or "", "raw_lines": len(result.raw_lines)},
                )
            guidance: str | None = None
            error: str | None = None
            if not ok:
                error = result.error or "no_sensors"
                guidance = (
                    "No temperature sensors returned data. On some macOS builds, Apple restricts low-level sensors. "
                    "If this persists, compare against a privileged helper tool (example: Mac Fan Control) to confirm availability."
                )
            return {
                "ok": ok,
                "sensors": [reading.__dict__ for reading in result.readings],
                "fans": [],
                "source": "iohid_event_system",
                "raw": raw_text,
                "permission_required": False,
                "error": error,
                "guidance": guidance,
            }
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError) as exc:
            logger.warning(
                "temperature sensor collection failed",
                event="thermals_error",
                context=context,
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            return {
                "ok": False,
                "sensors": [],
                "fans": [],
                "source": "iohid_event_system",
                "raw": "",
                "permission_required": False,
                "error": format_error(
                    MODULE_PATH,
                    "ThermalSensorsDiagnostics._fetch_uncached",
                    "Failed to collect temperature sensors",
                    exc,
                ),
                "guidance": "Temperature sensors are unavailable due to an unexpected error. Open Error Details for specifics.",
            }
