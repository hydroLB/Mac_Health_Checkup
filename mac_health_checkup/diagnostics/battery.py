from __future__ import annotations

from dataclasses import dataclass

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import (
    fmt_percent,
    fmt_temp_c,
    format_error,
    health_from_percent,
    regex_extract_int,
    safe_int,
    safe_run,
)
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/battery.py"


@dataclass(frozen=True)
class BatteryStats:
    """
    Summary
    Store parsed battery statistics.

    Inputs
    Raw integer values from ioreg.

    Outputs
    Immutable stats container.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `BatteryDiagnostics` for formatting.

    Why this exists
    Keeps parsed battery data strongly typed.
    """

    design_capacity: int
    max_capacity: int
    current_capacity: int | None
    cycle_count: int | None
    voltage_mv: int | None
    temperature_raw: int | None

    def percent_health(self) -> float:
        """
        Summary
        Calculate battery health percent.

        Inputs
        None.

        Outputs
        Health percent as float.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when computation fails (for example, division by zero).

        Ties to other methods
        Used by `BatteryDiagnostics` formatting.

        Why this exists
        Makes health computation explicit and testable.
        """
        try:
            return (self.max_capacity / self.design_capacity) * 100.0
        except (ZeroDivisionError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "BatteryStats.percent_health", "Failed to compute percent", exc)
            ) from exc

    def temperature_c(self) -> float | None:
        """
        Summary
        Convert raw temperature units to Celsius.

        Inputs
        None.

        Outputs
        Celsius temperature or None.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when conversion fails unexpectedly.

        Ties to other methods
        Used by `BatteryDiagnostics` formatting.

        Why this exists
        Keeps temperature conversion consistent.
        """
        try:
            if self.temperature_raw is None:
                return None
            return self.temperature_raw / 100.0
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "BatteryStats.temperature_c", "Failed to convert temp", exc)
            ) from exc


class BatteryDiagnostics:
    """
    Summary
    Collect battery health and usage details.

    Inputs
    None. Reads ioreg output.

    Outputs
    Dict with battery stats and summary text.

    Side effects
    Executes ioreg command.

    Error handling
    Returns fallback values when ioreg output is missing; raises `RuntimeError` with module and method context when
    parsing fails unexpectedly.

    Ties to other methods
    Used by the Battery section in the GUI.

    Why this exists
    Provides battery health and status in a single view.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch battery details with caching.

        Inputs
        None.

        Outputs
        Dict with battery fields and summary.

        Side effects
        Executes ioreg when the cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by the Battery section handler.

        Why this exists
        Keeps battery details fresh while avoiding repeated IO.
        """
        try:
            return cached_fetch(BatteryDiagnostics._cache, "battery", BatteryDiagnostics._fetch_uncached)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "BatteryDiagnostics.fetch", "Failed to fetch battery", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch battery details without caching.

        Inputs
        None.

        Outputs
        Dict with battery fields and summary.

        Side effects
        Executes ioreg.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Separates IO from cache logic for testing.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("BatteryDiagnostics")
            out, err = safe_run(
                ["ioreg", "-r", "-c", "AppleSmartBattery"], context="battery", allow_sudo=False
            )
            if not out:
                logger.warning(
                    "ioreg returned no output",
                    event="battery_empty",
                    context=context,
                    payload={"error": err or ""},
                )
                return {"present": False, "health_text": "Battery not accessible", "raw": ""}
            stats = BatteryDiagnostics._parse_stats(out)
            if stats is None:
                logger.warning("battery stats missing", event="battery_missing", context=context, payload={})
                return {"present": False, "health_text": "Battery info incomplete", "raw": out}
            thresholds = get_config().thresholds
            percent = stats.percent_health()
            temp_c = stats.temperature_c()
            health = health_from_percent(
                percent,
                excellent_min=thresholds.health_excellent_min_percent,
                good_min=thresholds.health_good_min_percent,
                fair_min=thresholds.health_fair_min_percent,
            )
            summary = f"{fmt_percent(percent)} health | Cycles: {stats.cycle_count or '?'} | {fmt_temp_c(temp_c)} | {health}"
            return {
                "present": True,
                "percent_health": percent,
                "design_capacity": stats.design_capacity,
                "max_capacity": stats.max_capacity,
                "current_capacity": stats.current_capacity,
                "cycle_count": stats.cycle_count,
                "temperature_c": temp_c,
                "voltage_mv": stats.voltage_mv,
                "health_text": summary,
                "raw": out,
            }
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "BatteryDiagnostics._fetch_uncached", "Battery parsing failed", exc)
            ) from exc

    @staticmethod
    def _parse_stats(raw: str) -> BatteryStats | None:
        """
        Summary
        Parse battery stats from ioreg output.

        Inputs
        raw: ioreg output string.

        Outputs
        BatteryStats or None when required fields are missing.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `_fetch_uncached`.

        Why this exists
        Centralizes battery parsing logic.
        """
        try:
            design_capacity = regex_extract_int(raw, r"\"DesignCapacity\"\s*=\s*(\d+)")
            max_capacity = regex_extract_int(
                raw, r"\"AppleRawMaxCapacity\"\s*=\s*(\d+)"
            ) or regex_extract_int(raw, r"\"MaxCapacity\"\s*=\s*(\d+)")
            if design_capacity is None or max_capacity is None:
                return None
            current_capacity = regex_extract_int(raw, r"\"AppleRawCurrentCapacity\"\s*=\s*(\d+)")
            if current_capacity is None:
                current_capacity = regex_extract_int(raw, r"\"CurrentCapacity\"\s*=\s*(\d+)")
            cycle_count = regex_extract_int(raw, r"\"CycleCount\"\s*=\s*(\d+)")
            voltage_mv = regex_extract_int(raw, r"\"Voltage\"\s*=\s*(\d+)")
            temperature_raw = regex_extract_int(raw, r"\"Temperature\"\s*=\s*(\d+)")
            return BatteryStats(
                design_capacity=design_capacity,
                max_capacity=max_capacity,
                current_capacity=current_capacity,
                cycle_count=cycle_count,
                voltage_mv=voltage_mv,
                temperature_raw=temperature_raw,
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "BatteryDiagnostics._parse_stats", "Failed to parse stats", exc)
            ) from exc


class BatteryTempDiagnostics:
    """
    Summary
    Provide a lightweight battery temperature summary.

    Inputs
    None. Reads ioreg output.

    Outputs
    Dict with temperature data.

    Side effects
    Executes ioreg.

    Error handling
    Returns None temperatures when output is missing; raises `RuntimeError` with module and method context when
    parsing fails unexpectedly.

    Ties to other methods
    Used by the Power section and tests.

    Why this exists
    Provides a focused temperature signal for the UI.
    """

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch battery temperature details.

        Inputs
        None.

        Outputs
        Dict with temp_c, temp_f, and raw.

        Side effects
        Executes ioreg.

        Error handling
        Returns None temperatures when output is missing; raises `RuntimeError` with module and method context when
        parsing fails unexpectedly.

        Ties to other methods
        Used by power-related sections.

        Why this exists
        Keeps temperature logic separate from full battery health.
        """
        try:
            out, err = safe_run(
                ["ioreg", "-r", "-c", "AppleSmartBattery"], context="battery_temp", allow_sudo=False
            )
            if not out:
                return {"temp_c": None, "temp_f": None, "raw": "", "error": err or ""}
            temp_raw = regex_extract_int(out, r"\"Temperature\"\s*=\s*(\d+)")
            temp_c = safe_int(temp_raw)
            temp_c_val = float(temp_c) / 100.0 if temp_c is not None else None
            temp_f_val = (temp_c_val * 9.0 / 5.0 + 32.0) if temp_c_val is not None else None
            return {"temp_c": temp_c_val, "temp_f": temp_f_val, "raw": out}
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "BatteryTempDiagnostics.fetch", "Failed to fetch temp", exc)
            ) from exc
