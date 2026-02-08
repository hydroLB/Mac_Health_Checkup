from __future__ import annotations

from dataclasses import dataclass

from mac_health_checkup.app.backend.snapshot import Snapshot, SnapshotSection, SnapshotTable
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/reports/snapshot_diff.py"


@dataclass(frozen=True)
class MetricChange:
    """
    Summary
    Represent a change in a single metrics row between two snapshots.

    Inputs
    label: Stable label for the metric.
    before: Previous value string.
    after: Current value string.
    before_status: Previous status string.
    after_status: Current status string.

    Outputs
    Immutable change record.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `diff_snapshots` for report rendering.

    Why this exists
    Metrics changes are the most actionable “diff” signal and should be summarized explicitly.
    """

    label: str
    before: str
    after: str
    before_status: str
    after_status: str


@dataclass(frozen=True)
class SectionDiff:
    """
    Summary
    Represent changes for a single section key.

    Inputs
    key: Section key.
    field_before: Previous section field text (summary).
    field_after: Current section field text (summary).
    metrics_added: Metrics present only in the “after” snapshot.
    metrics_removed: Metrics present only in the “before” snapshot.
    metrics_changed: Metrics with the same label but different value or status.
    table_changed: Whether table headers/rows changed.
    table_before_rows: Row count in the “before” snapshot.
    table_after_rows: Row count in the “after” snapshot.

    Outputs
    Immutable diff record.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `diff_snapshots` and rendered by report formatters.

    Why this exists
    Per-section diffs keep report output readable and localized.
    """

    key: str
    field_before: str | None
    field_after: str | None
    metrics_added: list[tuple[str, str, str]]
    metrics_removed: list[tuple[str, str, str]]
    metrics_changed: list[MetricChange]
    table_changed: bool
    table_before_rows: int
    table_after_rows: int

    @property
    def changed(self) -> bool:
        return bool(
            (self.field_before or "") != (self.field_after or "")
            or self.metrics_added
            or self.metrics_removed
            or self.metrics_changed
            or self.table_changed
        )


@dataclass(frozen=True)
class SnapshotDiff:
    """
    Summary
    Represent a high-level diff between two snapshots.

    Inputs
    before_generated_at_unix_ms: Timestamp from the “before” snapshot.
    after_generated_at_unix_ms: Timestamp from the “after” snapshot.
    before_ok: Whether the “before” snapshot was successful.
    after_ok: Whether the “after” snapshot was successful.
    before_error: Optional error string from the “before” snapshot.
    after_error: Optional error string from the “after” snapshot.
    added_sections: Section keys present only in “after”.
    removed_sections: Section keys present only in “before”.
    section_diffs: Per-section diffs for section keys present in both.

    Outputs
    Immutable diff container.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `diff_snapshots` and consumed by Markdown/HTML renderers.

    Why this exists
    Export and sharing workflows benefit from a deterministic, typed diff shape.
    """

    before_generated_at_unix_ms: int
    after_generated_at_unix_ms: int
    before_ok: bool
    after_ok: bool
    before_error: str | None
    after_error: str | None
    added_sections: list[str]
    removed_sections: list[str]
    section_diffs: list[SectionDiff]

    @property
    def changed_sections(self) -> list[SectionDiff]:
        return [item for item in self.section_diffs if item.changed]


def diff_snapshots(before: Snapshot, after: Snapshot) -> SnapshotDiff:
    """
    Summary
    Compute a UI-facing diff between two snapshots.

    Inputs
    before: Snapshot captured earlier.
    after: Snapshot captured later.

    Outputs
    SnapshotDiff summarizing changes in fields, metrics, and tables.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when diff computation fails unexpectedly.

    Ties to other methods
    Used by the entrypoint export and stdout diff modes.

    Why this exists
    Snapshot diffs enable “before vs after” troubleshooting without re-running collectors or eyeballing logs.
    """
    try:
        before_sections = {section.key: section for section in before.sections}
        after_sections = {section.key: section for section in after.sections}

        added = sorted([key for key in after_sections.keys() if key not in before_sections])
        removed = sorted([key for key in before_sections.keys() if key not in after_sections])
        shared = sorted([key for key in before_sections.keys() if key in after_sections])

        diffs: list[SectionDiff] = []
        for key in shared:
            diffs.append(_diff_section(key, before_sections[key], after_sections[key]))

        return SnapshotDiff(
            before_generated_at_unix_ms=int(before.generated_at_unix_ms),
            after_generated_at_unix_ms=int(after.generated_at_unix_ms),
            before_ok=bool(before.ok),
            after_ok=bool(after.ok),
            before_error=before.error,
            after_error=after.error,
            added_sections=added,
            removed_sections=removed,
            section_diffs=diffs,
        )
    except (AttributeError, TypeError, ValueError, RuntimeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "diff_snapshots", "Failed to diff snapshots", exc)
        ) from exc


def _diff_section(key: str, before: SnapshotSection, after: SnapshotSection) -> SectionDiff:
    field_before = before.field
    field_after = after.field
    metrics_added, metrics_removed, metrics_changed = _diff_metrics(before.metrics, after.metrics)
    table_changed, before_rows, after_rows = _diff_table(before.table, after.table)
    return SectionDiff(
        key=key,
        field_before=field_before,
        field_after=field_after,
        metrics_added=metrics_added,
        metrics_removed=metrics_removed,
        metrics_changed=metrics_changed,
        table_changed=table_changed,
        table_before_rows=before_rows,
        table_after_rows=after_rows,
    )


def _diff_metrics(
    before: list[tuple[str, str, str]] | None,
    after: list[tuple[str, str, str]] | None,
) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]], list[MetricChange]]:
    if not before and not after:
        return [], [], []
    before_rows = before or []
    after_rows = after or []

    before_labels = [label for label, _value, _status in before_rows]
    after_labels = [label for label, _value, _status in after_rows]
    unique_before = len(set(before_labels)) == len(before_labels)
    unique_after = len(set(after_labels)) == len(after_labels)

    added: list[tuple[str, str, str]] = []
    removed: list[tuple[str, str, str]] = []
    changed: list[MetricChange] = []

    if unique_before and unique_after:
        before_map = {label: (label, value, status) for label, value, status in before_rows}
        after_map = {label: (label, value, status) for label, value, status in after_rows}
        for label in sorted(set(after_map) - set(before_map)):
            added.append(after_map[label])
        for label in sorted(set(before_map) - set(after_map)):
            removed.append(before_map[label])
        for label in sorted(set(before_map) & set(after_map)):
            b_label, b_value, b_status = before_map[label]
            a_label, a_value, a_status = after_map[label]
            if b_value != a_value or b_status != a_status:
                changed.append(
                    MetricChange(
                        label=b_label,
                        before=b_value,
                        after=a_value,
                        before_status=b_status,
                        after_status=a_status,
                    )
                )
        return added, removed, changed

    # Fallback: index-based diff when labels are not stable/unique.
    max_len = max(len(before_rows), len(after_rows))
    for idx in range(max_len):
        b = before_rows[idx] if idx < len(before_rows) else None
        a = after_rows[idx] if idx < len(after_rows) else None
        if b is None and a is not None:
            added.append(a)
            continue
        if a is None and b is not None:
            removed.append(b)
            continue
        if b is None or a is None:
            continue
        b_label, b_value, b_status = b
        a_label, a_value, a_status = a
        if b_label != a_label or b_value != a_value or b_status != a_status:
            changed.append(
                MetricChange(
                    label=f"{b_label} (idx={idx})",
                    before=b_value,
                    after=a_value,
                    before_status=b_status,
                    after_status=a_status,
                )
            )
    return added, removed, changed


def _diff_table(before: SnapshotTable | None, after: SnapshotTable | None) -> tuple[bool, int, int]:
    before_rows = len(before.rows) if before is not None else 0
    after_rows = len(after.rows) if after is not None else 0
    if before is None and after is None:
        return False, 0, 0
    if before is None or after is None:
        return True, before_rows, after_rows
    if before.headers != after.headers:
        return True, before_rows, after_rows
    if before.rows != after.rows:
        return True, before_rows, after_rows
    return False, before_rows, after_rows
