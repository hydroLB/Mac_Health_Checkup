from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/models.py"


@dataclass(frozen=True)
class TemperatureReading:
    """
    Purpose: Represent a temperature sensor reading.
    Ties: Produced by ThermalSensorsDiagnostics parsing and rendered in the Performance section.
    Inputs: label is the sensor name, celsius is the numeric temperature.
    Outputs: Immutable temperature reading.
    Side effects: None.
    Why: Keeps parsed temperature readings strongly typed and easy to validate.
    """

    label: str
    celsius: float
    status: str


@dataclass(frozen=True)
class FanSpeedReading:
    """
    Purpose: Represent a fan speed reading.
    Ties: Produced by ThermalSensorsDiagnostics parsing and rendered in the Fans section.
    Inputs: label is the fan name, rpm is the current fan RPM.
    Outputs: Immutable fan reading.
    Side effects: None.
    Why: Keeps parsed fan readings strongly typed and easy to validate.
    """

    label: str
    rpm: int
