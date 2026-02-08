from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/models.py"


@dataclass(frozen=True)
class TemperatureReading:
    """
    Summary
    Represent a temperature sensor reading.

    Inputs
    label: Sensor name.
    celsius: Numeric temperature.
    status: UI status label.

    Outputs
    Immutable temperature reading.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by thermal diagnostics parsing and rendered in the Performance section.

    Why this exists
    Keeps parsed temperature readings strongly typed and easy to validate.
    """

    label: str
    celsius: float
    status: str


@dataclass(frozen=True)
class FanSpeedReading:
    """
    Summary
    Represent a fan speed reading.

    Inputs
    label: Fan name.
    rpm: Current fan RPM.

    Outputs
    Immutable fan reading.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by thermal diagnostics parsing and rendered in the Fans section.

    Why this exists
    Keeps parsed fan readings strongly typed and easy to validate.
    """

    label: str
    rpm: int
