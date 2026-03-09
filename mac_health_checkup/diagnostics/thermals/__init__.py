from __future__ import annotations

from mac_health_checkup.diagnostics.thermals.collector import ThermalSensorsDiagnostics
from mac_health_checkup.diagnostics.thermals.models import FanSpeedReading, TemperatureReading

__all__ = [
    "FanSpeedReading",
    "TemperatureReading",
    "ThermalSensorsDiagnostics",
]
