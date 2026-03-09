from __future__ import annotations

from mac_health_checkup.app.gui.sections import (
    battery,
    devices,
    fan,
    general,
    input,
    network,
    performance,
    ports,
    power,
    ssd,
)
from mac_health_checkup.app.gui.sections.display import update_section as display_section

__all__ = [
    "battery",
    "devices",
    "fan",
    "general",
    "input",
    "network",
    "performance",
    "ports",
    "power",
    "ssd",
    "display_section",
]
