from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from mac_health_checkup.app.cli import ConsoleHost


@dataclass(frozen=True)
class AdviceInput:
    """
    Summary
    Hold the minimal data required to evaluate one section advice record.

    Inputs
    key: Section key.
    field: Section summary field value.
    metrics: Section metrics rows.
    diagnostics: Section diagnostics payload.

    Outputs
    Immutable advice input record.

    Side effects
    None.

    Error handling
    Validation is performed by the caller-specific collection helpers.

    Ties to other methods
    Used by `should_fail_on_host`, `should_fail_on_snapshot`, and `_should_fail_on_inputs`.

    Why this exists
    A shared record keeps fail-policy evaluation identical across CLI and snapshot sources.
    """

    key: str
    field: str | None
    metrics: Sequence[tuple[str, str, str]] | None
    diagnostics: Mapping[str, object] | None


class _SnapshotSectionProtocol(Protocol):
    """
    Summary
    Describe the snapshot section attributes needed for fail-on evaluation.

    Inputs
    None.

    Outputs
    Structural protocol used only for type checking.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `_SnapshotProtocol` and `_iter_snapshot_inputs`.

    Why this exists
    Snapshot fail evaluation needs only a narrow, stable subset of the full section model.
    """

    key: str
    field: str | None
    metrics: Sequence[tuple[str, str, str]] | None
    diagnostics: Mapping[str, object] | None


class _SnapshotProtocol(Protocol):
    """
    Summary
    Describe the snapshot attributes needed for fail-on evaluation.

    Inputs
    None.

    Outputs
    Structural protocol used only for type checking.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `should_fail_on_snapshot` and `_iter_snapshot_inputs`.

    Why this exists
    The fail policy should depend on the smallest possible snapshot surface.
    """

    sections: Sequence[_SnapshotSectionProtocol]


def should_fail_on_host(host: ConsoleHost, *, fail_on: str, section_keys: Iterable[str]) -> bool:
    """
    Summary
    Decide whether CLI-rendered section output should trigger `--fail-on` automation behavior.

    Inputs
    host: ConsoleHost containing rendered fields, metrics, and captured diagnostics.
    fail_on: "warn" or "bad".
    section_keys: Ordered section keys to evaluate.

    Outputs
    True when any section meets or exceeds the requested severity threshold.

    Side effects
    None.

    Error handling
    Never raises; returns false when evaluation fails.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._should_fail_on_host`.

    Why this exists
    Automation should not depend on parsing human formatted CLI output.
    """
    try:
        return _should_fail_on_inputs(_iter_host_inputs(host, section_keys), fail_on=fail_on)
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError):
        return False


def should_fail_on_snapshot(snapshot: object, *, fail_on: str, snapshot_type: type[object]) -> bool:
    """
    Summary
    Decide whether a snapshot should trigger `--fail-on` automation behavior.

    Inputs
    snapshot: Snapshot instance treated as an opaque object.
    fail_on: "warn" or "bad".
    snapshot_type: Runtime `Snapshot` type used for validation.

    Outputs
    True when any section meets or exceeds the requested severity threshold.

    Side effects
    None.

    Error handling
    Never raises; returns false on evaluation errors.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._should_fail_on_snapshot`.

    Why this exists
    Snapshot JSON is machine readable, but the process exit code is still the cleanest automation signal.
    """
    try:
        if not isinstance(snapshot, snapshot_type):
            return False
        return _should_fail_on_inputs(
            _iter_snapshot_inputs(cast(_SnapshotProtocol, snapshot)), fail_on=fail_on
        )
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError):
        return False


def _iter_host_inputs(host: ConsoleHost, section_keys: Iterable[str]) -> list[AdviceInput]:
    """
    Summary
    Collect advice evaluation inputs from a console host.

    Inputs
    host: ConsoleHost holding rendered section content.
    section_keys: Ordered section keys to evaluate.

    Outputs
    List of `AdviceInput` records.

    Side effects
    None.

    Error handling
    Propagates unexpected container access failures to the caller.

    Ties to other methods
    Used by `should_fail_on_host`.

    Why this exists
    Host-backed fail evaluation should share the same normalized input shape as snapshot-backed evaluation.
    """
    return [
        AdviceInput(
            key=key,
            field=host.fields.get(key),
            metrics=host.metrics.get(key),
            diagnostics=host.diagnostics.get(key),
        )
        for key in section_keys
    ]


def _iter_snapshot_inputs(snapshot: _SnapshotProtocol) -> list[AdviceInput]:
    """
    Summary
    Collect advice evaluation inputs from a snapshot payload.

    Inputs
    snapshot: Snapshot object with a `sections` attribute.

    Outputs
    List of `AdviceInput` records.

    Side effects
    None.

    Error handling
    Propagates unexpected snapshot shape failures to the caller.

    Ties to other methods
    Used by `should_fail_on_snapshot`.

    Why this exists
    Snapshot-backed fail evaluation should use the same advice pipeline as CLI-backed evaluation.
    """
    return [
        AdviceInput(
            key=section.key,
            field=section.field,
            metrics=section.metrics,
            diagnostics=section.diagnostics,
        )
        for section in snapshot.sections
    ]


def _should_fail_on_inputs(inputs: Iterable[AdviceInput], *, fail_on: str) -> bool:
    """
    Summary
    Evaluate a collection of normalized advice inputs against a fail threshold.

    Inputs
    inputs: Advice inputs to evaluate.
    fail_on: "warn" or "bad".

    Outputs
    True when any advice severity meets or exceeds the threshold.

    Side effects
    None.

    Error handling
    Propagates actionability import or advice construction failures to the caller.

    Ties to other methods
    Used by `should_fail_on_host` and `should_fail_on_snapshot`.

    Why this exists
    A single fail evaluator keeps automation semantics identical for CLI and snapshot modes.
    """
    from mac_health_checkup.app.actionability import AdviceSeverity, build_section_advice, should_fail_on

    for item in inputs:
        advice = build_section_advice(
            item.key,
            field=item.field,
            metrics=item.metrics,
            diagnostics=item.diagnostics,
        )
        severity = advice.get("severity")
        if severity in {"ok", "warn", "bad"} and should_fail_on(cast(AdviceSeverity, severity), fail_on):
            return True
    return False
