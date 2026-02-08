"""
Summary
Processing helpers for thermals diagnostics that are independent from any specific sensor backend.

Inputs
None.

Outputs
This package exposes small pure helpers for status mapping and sample aggregation.

Side effects
None.

Error handling
Pure helpers generally do not raise; they return safe defaults for malformed inputs.

Ties to other methods
Used by `mac_health_checkup.diagnostics.thermals.hid_event_system` and other thermals collectors.

Why this exists
Separating "business logic" (status thresholds, dedupe rules) from IO boundaries makes collectors easier to test and extend without changing behavior.
"""

from __future__ import annotations

from mac_health_checkup.diagnostics.thermals.processing.dedupe import update_best_by_label
from mac_health_checkup.diagnostics.thermals.processing.status import status_for_temp

__all__ = [
    "status_for_temp",
    "update_best_by_label",
]
