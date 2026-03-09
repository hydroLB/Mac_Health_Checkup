from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from mac_health_checkup.app.backend import (
    Snapshot,
    SnapshotSection,
    SnapshotSectionDescriptor,
    SnapshotTable,
    SnapshotTheme,
)
from mac_health_checkup.app.reports import (
    diff_snapshots,
    load_snapshot_from_path,
    render_diff_markdown,
    render_snapshot_markdown,
)
from mac_health_checkup.core.config import reset_config_cache
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.qr import maybe_render_qr_ansiutf8

MODULE_PATH = "tests/test_reports_export.py"


def _snapshot(*, metric_value: str, include_diagnostics: bool) -> Snapshot:
    """
    Summary
    Build a minimal in-memory `Snapshot` for export and diff tests.

    Inputs
    `metric_value` sets the metric value; `include_diagnostics` toggles diagnostic blobs.

    Outputs
    A `Snapshot` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module context if snapshot construction fails.

    Ties to other methods
    Used by report rendering tests in this module.

    Why this exists
    Keeps tests deterministic without invoking collectors or macOS commands.
    """
    try:
        diagnostics = {"raw": "secret"} if include_diagnostics else None
        diagnostics_json = cast(JsonDict, diagnostics) if diagnostics is not None else None
        return Snapshot(
            schema_version=2,
            generated_at_unix_ms=0,
            theme=SnapshotTheme(ui={}, colors={}, fonts={}, gui={}),
            section_catalog=[SnapshotSectionDescriptor(title="General", subtitle="Model", key="general")],
            sections=[
                SnapshotSection(
                    key="general",
                    field="Hello",
                    metrics=[("Battery", metric_value, "info")],
                    table=SnapshotTable(headers=("A", "B"), rows=[("1", "2")]),
                    diagnostics=diagnostics_json,
                )
            ],
            ok=True,
            error=None,
        )
    except (
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_snapshot failed: {exc}") from exc


def test_render_snapshot_markdown_omits_diagnostics_by_default() -> None:
    """
    Summary
    Ensure Markdown exports omit raw diagnostics unless explicitly enabled.

    Inputs
    A `Snapshot` containing a diagnostics blob.

    Outputs
    Assertions on the rendered Markdown content.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `render_snapshot_markdown` `include_diagnostics` behavior.

    Why this exists
    Diagnostics may include sensitive system data and should be opt-in for sharing.
    """
    try:
        snap = _snapshot(metric_value="1", include_diagnostics=True)
        md = render_snapshot_markdown(snap, include_diagnostics=False)
        assert "Mac Health Checkup Report" in md
        assert "**Summary:** Hello" in md
        assert "Battery" in md
        assert "secret" not in md
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_render_snapshot_markdown_omits_diagnostics_by_default failed: {exc}"
        ) from exc


def test_diff_snapshots_changes_metric_value() -> None:
    """
    Summary
    Verify snapshot diffs detect metric value changes and render them.

    Inputs
    Two snapshots with different metric values.

    Outputs
    Assertions on the diff Markdown output.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `diff_snapshots` and `render_diff_markdown`.

    Why this exists
    Diff output must be actionable and surface changes clearly.
    """
    try:
        before = _snapshot(metric_value="1", include_diagnostics=False)
        after = _snapshot(metric_value="2", include_diagnostics=False)
        diff = diff_snapshots(before, after)
        md = render_diff_markdown(diff)
        assert "Snapshot Diff" in md
        assert "Changed" in md
        assert "`Battery`" in md
        assert "`1`" in md and "`2`" in md
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_diff_snapshots_changes_metric_value failed: {exc}") from exc


def test_load_snapshot_from_path_round_trips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure snapshot IO can load a valid snapshot JSON file into a typed `Snapshot`.

    Inputs
    Temporary snapshot JSON file written to disk.

    Outputs
    Assertions on decoded fields.

    Side effects
    Writes a temp file and sets config env var.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `load_snapshot_from_path`.

    Why this exists
    Saved snapshots are the core primitive for export and diff workflows.
    """
    try:
        monkeypatch.delenv("MAC_HEALTH_CHECKUP_CONFIG", raising=False)
        reset_config_cache()
        snap = _snapshot(metric_value="1", include_diagnostics=False)
        payload = json.loads(snap.to_json(pretty=False))
        path = tmp_path / "snapshot.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        loaded = load_snapshot_from_path(path)
        assert loaded.schema_version == 2
        assert loaded.ok is True
        assert loaded.sections[0].key == "general"
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_load_snapshot_from_path_round_trips failed: {exc}") from exc


def test_maybe_render_qr_ansiutf8_best_effort(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify QR rendering returns output when `qrencode` is available and succeeds.

    Inputs
    Monkeypatched `qrencode_available` and `subprocess.run` behavior.

    Outputs
    Assertions on returned QR text.

    Side effects
    Monkeypatches module functions.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `maybe_render_qr_ansiutf8`.

    Why this exists
    Pairing QR is an optional, best-effort ergonomics feature.
    """
    try:
        import mac_health_checkup.core.utils.qr as qr_mod

        monkeypatch.setattr(qr_mod, "qrencode_available", lambda: True)
        monkeypatch.setattr(
            "mac_health_checkup.core.utils.qr.shutil.which",
            lambda _name: "/usr/local/bin/qrencode",
        )

        def _fake_run(*_args: object, **_kwargs: object) -> object:
            """
            Summary
            Execute `_fake_run` for its module-level responsibility.

            Inputs
            *_args: variadic `object` parameters.
            **_kwargs: variadic keyword `object` parameters.

            Outputs
            Returns `object`.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `tests/test_reports_export.py:_fake_run` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_reports_export.py`.

            Why this exists
            Keeps `_fake_run` explicit, testable, and maintainable.
            """
            return SimpleNamespace(returncode=0, stdout="QR", stderr="")

        monkeypatch.setattr("mac_health_checkup.core.utils.qr.subprocess.run", _fake_run)
        assert maybe_render_qr_ansiutf8("data", timeout_sec=1) == "QR"
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_maybe_render_qr_ansiutf8_best_effort failed: {exc}"
        ) from exc
