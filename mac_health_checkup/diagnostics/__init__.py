from __future__ import annotations

from mac_health_checkup.diagnostics.battery import BatteryDiagnostics, BatteryTempDiagnostics
from mac_health_checkup.diagnostics.devices import DeviceScanner, InputDiagnostics, PortsDiagnostics
from mac_health_checkup.diagnostics.display import DisplayDiagnostics
from mac_health_checkup.diagnostics.display_transport import DisplayTransportDiagnostics
from mac_health_checkup.diagnostics.fan import FanDiagnostics
from mac_health_checkup.diagnostics.general import GeneralDiagnostics
from mac_health_checkup.diagnostics.network import NetworkQualityDiagnostics
from mac_health_checkup.diagnostics.power import (
    PowerAdapterDiagnostics,
    PowerResidencyDiagnostics,
    ThermalDiagnostics,
    USBPowerDiagnostics,
)
from mac_health_checkup.diagnostics.ssd import SSDDiagnostics

__all__ = [
    "BatteryDiagnostics",
    "BatteryTempDiagnostics",
    "DeviceScanner",
    "DisplayDiagnostics",
    "DisplayTransportDiagnostics",
    "FanDiagnostics",
    "GeneralDiagnostics",
    "InputDiagnostics",
    "NetworkQualityDiagnostics",
    "PortsDiagnostics",
    "PowerAdapterDiagnostics",
    "PowerResidencyDiagnostics",
    "SSDDiagnostics",
    "ThermalDiagnostics",
    "USBPowerDiagnostics",
]
