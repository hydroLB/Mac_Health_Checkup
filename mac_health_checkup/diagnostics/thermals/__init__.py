from __future__ import annotations

from mac_health_checkup.diagnostics.thermals.authorization import authorize_temperature_sensors
from mac_health_checkup.diagnostics.thermals.collector import ThermalSensorsDiagnostics
from mac_health_checkup.diagnostics.thermals.models import FanSpeedReading, TemperatureReading
from mac_health_checkup.diagnostics.thermals.parsing import (
    _parse_istats_scan_text,
    _parse_powermetrics_smc,
    _parse_temperature_lines,
)

__all__ = [
    "FanSpeedReading",
    "TemperatureReading",
    "ThermalSensorsDiagnostics",
    "_parse_istats_scan_text",
    "_parse_powermetrics_smc",
    "_parse_temperature_lines",
    "authorize_temperature_sensors",
]
