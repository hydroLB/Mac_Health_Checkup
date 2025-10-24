from utils import update_result_with_defaults, safe_run, regex_extract_int
from typing import Dict, Any
from diagnostics.base import debug_msg, log_exc
from utils import Health
from dataclasses import dataclass
from typing import Optional, Tuple


# ----------------------------------------------------------------------
# Internal model for parsed battery stats
# ----------------------------------------------------------------------
@dataclass
class _BatteryStats:
    design_capacity: int
    max_capacity: int
    current_capacity: Optional[int]
    cycle_count: Optional[int]
    voltage_mv: Optional[int]
    temperature_raw: Optional[int]  # raw value from ioreg (0.01 °C)

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------
    @property
    def percent_health(self) -> float:
        return self.max_capacity / self.design_capacity * 100

    @property
    def temperature_c(self) -> Optional[float]:
        """Convert raw temperature (0.01 °C) to normal Celsius."""
        return None if self.temperature_raw is None else self.temperature_raw / 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "present"        : True,
            "percent_health" : self.percent_health,
            "design_capacity": self.design_capacity,
            "max_capacity"   : self.max_capacity,
            "current_capacity": self.current_capacity,
            "cycle_count"    : self.cycle_count,
            "voltage_mv"     : self.voltage_mv,
            "temperature_c"  : self.temperature_c,
        }


class BatteryDiagnostics:
    """
    Battery health and cycle diagnostics section builder.
    Produces a row/section summarizing battery health, cycle count, and state.
    """

    # ------------------------------------------------------------------
    # Class‑level defaults & helpers
    # ------------------------------------------------------------------
    _DEFAULTS = {
        "present"       : False,
        "percent_health": None,
        "cycle_count"   : None,
        "health_text"   : "Battery Not Found",
        "raw"           : "",
        "design_capacity": None,
        "max_capacity"   : None,
        "current_capacity": None,
        "voltage_mv"     : None,
        "temperature_c"  : None,
    }

    @staticmethod
    def _read_ioreg() -> Tuple[str, str]:
        """Run ioreg command and return (stdout, stderr)."""
        return safe_run(["ioreg", "-r", "-c", "AppleSmartBattery"], "Battery")

    @staticmethod
    def _parse_stats(raw: str) -> Optional[_BatteryStats]:
        """Extract capacity and cycle stats from raw ioreg output."""
        dc  = regex_extract_int(raw, r'"DesignCapacity"\s*=\s*(\d+)')
        mc  = regex_extract_int(raw, r'"AppleRawMaxCapacity"\s*=\s*(\d+)') \
              or regex_extract_int(raw, r'"MaxCapacity"\s*=\s*(\d+)')
        if not (dc and mc):
            return None

        cc  = regex_extract_int(raw, r'"CycleCount"\s*=\s*(\d+)')
        cur = regex_extract_int(raw, r'"AppleRawCurrentCapacity"\s*=\s*(\d+)') \
              or regex_extract_int(raw, r'"CurrentCapacity"\s*=\s*(\d+)')
        volt = regex_extract_int(raw, r'"Voltage"\s*=\s*(\d+)')
        temp = regex_extract_int(raw, r'"Temperature"\s*=\s*(\d+)')
        return _BatteryStats(dc, mc, cur, cc, volt, temp)

    # ------------------------------------------------------------------
    # Presentation helper
    # ------------------------------------------------------------------
    @staticmethod
    def _format_health_text(stats: "_BatteryStats") -> str:
        """
        Build a concise string, e.g.
            "91.4 % | 8280 / 9087 mAh | Cycles: 177 | 30.5 °C | good"
        """
        state = Health.from_percent(stats.percent_health)
        pct   = f"{stats.percent_health:.1f}%"
        caps  = f"{stats.max_capacity:,}/{stats.design_capacity:,} mAh"
        cycles= stats.cycle_count if stats.cycle_count is not None else "?"
        temp  = f"{stats.temperature_c:.1f}°C" if stats.temperature_c is not None else "?"
        return f"{pct} | {caps} | Cycles: {cycles} | {temp} | {state}"

    @staticmethod
    def fetch() -> Dict[str, Any]:
        """
        Fetch battery health info and return a normalized section dict.

        Returns:
            Dict[str, Any] with keys:
                - "present": bool
                - "percent_health": float or None
                - "cycle_count": int or None
                - "health_text": str (row summary)
                - "raw": str (source)
        """
        result: Dict[str, Any] = {}

        try:
            out, err = BatteryDiagnostics._read_ioreg()
            if not out:
                debug_msg("BatteryDiagnostics", f"No battery info found; err={err}")
                result["health_text"] = f"Not accessible ({err})"
                update_result_with_defaults(result, BatteryDiagnostics._DEFAULTS)
                return result

            stats = BatteryDiagnostics._parse_stats(out)
            if not stats:
                debug_msg("BatteryDiagnostics", "Battery info incomplete (missing dc or mc)")
                result["health_text"] = "Battery info incomplete"
                update_result_with_defaults(result, BatteryDiagnostics._DEFAULTS)
                return result

            # Build final dict
            result.update(stats.to_dict())
            result["raw"] = out
            result["health_text"] = BatteryDiagnostics._format_health_text(stats)
            update_result_with_defaults(result, BatteryDiagnostics._DEFAULTS)
            return result
        except Exception as exc:
            log_exc("BatteryDiagnostics", exc)
            result["health_text"] = "Battery diagnostics failed"
            update_result_with_defaults(result, BatteryDiagnostics._DEFAULTS)
            return result
