from __future__ import annotations

from mac_health_checkup.app.reports.snapshot_diff import SnapshotDiff, diff_snapshots
from mac_health_checkup.app.reports.snapshot_io import load_snapshot_from_path
from mac_health_checkup.app.reports.snapshot_redaction import redact_snapshot_sensitive
from mac_health_checkup.app.reports.snapshot_render import (
    render_diff_html,
    render_diff_markdown,
    render_snapshot_html,
    render_snapshot_markdown,
)

__all__ = [
    "SnapshotDiff",
    "diff_snapshots",
    "load_snapshot_from_path",
    "redact_snapshot_sensitive",
    "render_diff_html",
    "render_diff_markdown",
    "render_snapshot_html",
    "render_snapshot_markdown",
]
