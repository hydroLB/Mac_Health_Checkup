from __future__ import annotations

from collections import OrderedDict
from typing import Callable

from mac_health_checkup.app.gui.dashboard.queueing import RefreshLimiter
from mac_health_checkup.app.gui.sections import (
    battery,
    devices,
    fan,
    general,
    network,
    performance,
    power,
    ssd,
)
from mac_health_checkup.app.gui.sections.display.section import update_section as display_section
from mac_health_checkup.app.gui.sections.input import update_section as input_section
from mac_health_checkup.app.gui.sections.ports import update_section as ports_section
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/sections.py"

SectionHandler = Callable[[SectionHost], JsonDict]

SECTION_RENDERERS: dict[str, SectionHandler] = {
    "performance": performance.update_section,
    "general": general.update_section,
    "power": power.update_section,
    "fan": fan.update_section,
    "battery": battery.update_section,
    "ssd": ssd.update_section,
    "display": display_section,
    "network": network.update_section,
    "devices": devices.update_section,
    "ports": ports_section,
    "input": input_section,
}


def _build_section_handlers() -> dict[str, SectionHandler]:
    """
    Purpose: Build ordered section handlers from config-defined rows.
    Ties: Used by SECTION_HANDLERS at import time.
    Inputs: None.
    Outputs: Ordered dict of section handlers.
    Side effects: Reads config values.
    Why: Keeps section order and membership configurable.
    """
    try:
        ordered: OrderedDict[str, SectionHandler] = OrderedDict()
        for _title, _subtitle, key in get_config().gui.section_rows:
            if key not in SECTION_RENDERERS:
                raise KeyError(f"Unknown section key: {key}")
            ordered[key] = SECTION_RENDERERS[key]
        return ordered
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_build_section_handlers", "Failed to build sections", exc)
        ) from exc


SECTION_HANDLERS: dict[str, SectionHandler] = _build_section_handlers()
_RATE_LIMITER = RefreshLimiter()


def run_section(host: SectionHost, key: str) -> JsonDict:
    """
    Purpose: Run a section handler by key.
    Ties: Used by refresh loops and tests.
    Inputs: host implements SectionHost, key is section key.
    Outputs: Diagnostics dict for the section.
    Side effects: Updates host via handler.
    Why: Provides a consistent entrypoint for section execution.
    """
    try:
        handler = SECTION_HANDLERS[key]
        if not _RATE_LIMITER.allow(key):
            return {"skipped": True, "reason": "refresh_min_interval"}
        result = handler(host)
        _RATE_LIMITER.mark(key)
        return result
    except KeyError as exc:
        raise RuntimeError(format_error(MODULE_PATH, "run_section", f"Unknown section {key}", exc)) from exc
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "run_section", "Failed to run section", exc)) from exc
