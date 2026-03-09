"""
Summary
Provide the supported backend public API surface.

Inputs
None.

Outputs
Exports stable backend interfaces consumed by entrypoints, reports, and external clients.

Side effects
None at import time beyond loading exported modules.

Error handling
None.

Ties to other methods
Used by top-level runners and app orchestration code to avoid importing backend implementation modules directly.

Why this exists
Reduces accidental coupling to backend internals and makes boundary ownership explicit.
"""

from __future__ import annotations

from mac_health_checkup.app.backend.one_click import run_one_click_agent
from mac_health_checkup.app.backend.server import SnapshotApiServer, pick_free_port, wait_until_ready
from mac_health_checkup.app.backend.snapshot import (
    Snapshot,
    SnapshotBuilder,
    SnapshotSection,
    SnapshotSectionDescriptor,
    SnapshotTable,
    SnapshotTheme,
    emit_section_json,
    emit_snapshot_json,
)

__all__ = [
    "Snapshot",
    "SnapshotApiServer",
    "SnapshotBuilder",
    "SnapshotSection",
    "SnapshotSectionDescriptor",
    "SnapshotTable",
    "SnapshotTheme",
    "emit_section_json",
    "emit_snapshot_json",
    "pick_free_port",
    "run_one_click_agent",
    "wait_until_ready",
]
