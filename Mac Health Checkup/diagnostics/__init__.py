# diagnostics/__init__.py
"""
Mac Health Diagnostics Subsystem

Last updated: 2025-07
[…the whole ‘Overview / Design Conventions / Sections’ block…]
"""
# re-export the public classes so callers can continue to do
#   from diagnostics import BatteryDiagnostics
from .battery import BatteryDiagnostics
from .ssd import SSDDiagnostics
from .fan import FanDiagnostics
from .display import DisplayDiagnostics
from .devices import DeviceScanner, PortsDiagnostics, InputDiagnostics
from .model import GeneralDiagnostics

__all__ = [
    "BatteryDiagnostics", "SSDDiagnostics", "FanDiagnostics",
    "DisplayDiagnostics", "DeviceScanner", "PortsDiagnostics",
    "InputDiagnostics", "GeneralDiagnostics",
]
