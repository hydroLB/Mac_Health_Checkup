"""
Summary
Internal IOHIDEventSystemClient bindings used for temperature sensor collection.

Inputs
None.

Outputs
This package exposes helpers for loading IOHID symbols and performing best-effort queries.

Side effects
None at import time.

Error handling
Best-effort modules return explicit error strings rather than raising, except for unexpected programmer errors.

Ties to other methods
Used by `mac_health_checkup.diagnostics.thermals.hid_event_system`.

Why this exists
Keeping ctypes bindings in a dedicated package prevents the main diagnostics logic from becoming a single large file
and makes it easier to extend (more sensors, better naming) without destabilizing callers.
"""

from __future__ import annotations

from mac_health_checkup.diagnostics.thermals.iohid.bindings import load_hid_api
from mac_health_checkup.diagnostics.thermals.iohid.temperature import collect_temperature_samples_once

__all__ = [
    "collect_temperature_samples_once",
    "load_hid_api",
]
