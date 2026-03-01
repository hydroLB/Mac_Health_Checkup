from __future__ import annotations

from types import SimpleNamespace
from typing import Sequence

import pytest

from mac_health_checkup.app.gui.sections import ssd as ssd_section
from mac_health_checkup.app.gui.sections.types import SectionHost, Widget
from mac_health_checkup.core.utils.health import health_from_percent

MODULE_PATH = "tests/test_health_thresholds.py"


class _Host(SectionHost):
    """
    Summary
    Lightweight section host used for deterministic unit tests.

    Inputs
    None.

    Outputs
    Captures section field and metrics updates.

    Side effects
    Stores render calls in memory.

    Error handling
    None.

    Ties to other methods
    Used by SSD section threshold tests.

    Why this exists
    Section tests should validate behavior without Tk dependencies.
    """

    def __init__(self) -> None:
        """
        Summary
        Initialize in-memory capture storage.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Initializes dictionaries for captured UI output.

        Error handling
        None.

        Ties to other methods
        Used by test helpers in this module.

        Why this exists
        Keeps section behavior tests deterministic and side-effect free.
        """
        self.fields: dict[str, str] = {}
        self.metrics: dict[str, list[tuple[str, str, str]]] = {}

    def get_widget(self, key: str) -> Widget | None:
        """
        Summary
        Return no concrete widget in test mode.

        Inputs
        key: Section key.

        Outputs
        Always returns `None`.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Satisfies the `SectionHost` protocol.

        Why this exists
        These tests exercise section logic only.
        """
        _ = key
        return None

    def set_field(self, key: str, text: str, fg: str | None = None, tooltip: str | None = None) -> None:
        """
        Summary
        Capture field text updates.

        Inputs
        key: Section key.
        text: Field text.
        fg: Optional text color.
        tooltip: Optional tooltip text.

        Outputs
        None.

        Side effects
        Updates in-memory `fields`.

        Error handling
        None.

        Ties to other methods
        Called by section update functions.

        Why this exists
        Assertions can verify what sections publish without rendering a GUI.
        """
        _ = fg
        _ = tooltip
        self.fields[key] = text

    def render_metrics_table(
        self,
        key: str,
        rows: Sequence[tuple[str, str, str]],
        *,
        columns: int = 2,
    ) -> None:
        """
        Summary
        Capture metric row updates.

        Inputs
        key: Section key.
        rows: Metrics rows.
        columns: Render hint.

        Outputs
        None.

        Side effects
        Updates in-memory `metrics`.

        Error handling
        None.

        Ties to other methods
        Called by section update functions.

        Why this exists
        Metrics assertions should not depend on Tk widgets.
        """
        _ = columns
        self.metrics[key] = list(rows)

    def render_table(
        self,
        key: str,
        headers: tuple[str, ...],
        rows: Sequence[tuple[str, ...]],
        max_col_chars: tuple[int | None, ...] | None = None,
    ) -> None:
        """
        Summary
        No-op table renderer for protocol completeness.

        Inputs
        key: Section key.
        headers: Table headers.
        rows: Table rows.
        max_col_chars: Optional width hints.

        Outputs
        None.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Satisfies `SectionHost`.

        Why this exists
        These tests only need metric behavior.
        """
        _ = key
        _ = headers
        _ = rows
        _ = max_col_chars

    def section_container(self, key: str) -> Widget | None:
        """
        Summary
        Return no section container in test mode.

        Inputs
        key: Section key.

        Outputs
        Always returns `None`.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Satisfies `SectionHost`.

        Why this exists
        UI containers are not needed for these logic tests.
        """
        _ = key
        return None

    def run_on_ui(self, fn: object) -> None:
        """
        Summary
        Execute callbacks immediately in tests.

        Inputs
        fn: Callable object.

        Outputs
        None.

        Side effects
        Executes callback synchronously.

        Error handling
        Raises `TypeError` when `fn` is not callable.

        Ties to other methods
        Satisfies `SectionHost`.

        Why this exists
        Test hosts should keep behavior deterministic and synchronous.
        """
        if not callable(fn):
            raise TypeError(f"{MODULE_PATH}:_Host.run_on_ui expected callable")
        fn()

    def set_machine_hint(self, descriptor: str) -> None:
        """
        Summary
        No-op machine hint setter for protocol completeness.

        Inputs
        descriptor: Machine descriptor.

        Outputs
        None.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Satisfies `SectionHost`.

        Why this exists
        Machine-hint behavior is outside this test scope.
        """
        _ = descriptor

    def machine_hint(self) -> str:
        """
        Summary
        Return a stable machine hint for protocol completeness.

        Inputs
        None.

        Outputs
        Constant hint string.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Satisfies `SectionHost`.

        Why this exists
        Section logic may request a hint even in tests.
        """
        return "mac"


def test_health_from_percent_uses_configured_cutoffs() -> None:
    """
    Summary
    Verify health label mapping follows supplied policy cutoffs instead of fixed constants.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Exercises `health_from_percent`.

    Why this exists
    Battery and SSD health labels must remain tunable from config.
    """
    assert health_from_percent(95.0, excellent_min=95.0, good_min=85.0, fair_min=70.0) == "excellent"
    assert health_from_percent(89.9, excellent_min=95.0, good_min=85.0, fair_min=70.0) == "good"
    assert health_from_percent(70.0, excellent_min=95.0, good_min=85.0, fair_min=70.0) == "fair"
    assert health_from_percent(69.9, excellent_min=95.0, good_min=85.0, fair_min=70.0) == "degraded"


def test_ssd_section_explicitly_exports_ssd_diagnostics() -> None:
    """
    Summary
    Verify SSD diagnostics symbol is part of the section module public API.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Guards monkeypatch paths used by SSD section tests.

    Why this exists
    Mypy strict re-export rules require explicit module exports for imported symbols.
    """
    exported = getattr(ssd_section, "__all__", ())
    assert "SSDDiagnostics" in exported


def test_ssd_section_uses_configured_warn_and_bad_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Verify SSD status rows use configured warning and bad counters.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches config and diagnostics fetch behavior.

    Error handling
    None.

    Ties to other methods
    Exercises `mac_health_checkup.app.gui.sections.ssd.update_section`.

    Why this exists
    SSD error severity policy must be tunable without code edits.
    """
    monkeypatch.setattr(
        ssd_section,
        "get_config",
        lambda: SimpleNamespace(
            thresholds=SimpleNamespace(
                health_excellent_min_percent=95.0,
                health_good_min_percent=90.0,
                health_fair_min_percent=85.0,
                ssd_unsafe_shutdowns_warn_count=2,
                ssd_media_errors_bad_count=3,
            )
        ),
    )
    monkeypatch.setattr(
        ssd_section.SSDDiagnostics,
        "fetch",
        staticmethod(
            lambda: {
                "health_text": "sample",
                "percent_left": 86.0,
                "unsafe_shutdowns": 1,
                "media_errors": 2,
                "data_written": None,
                "data_read": None,
            }
        ),
    )
    host = _Host()
    _ = ssd_section.update_section(host)
    rows = host.metrics["ssd"]
    status_by_label = {label: status for label, _value, status in rows}
    assert status_by_label["Life remaining"] == "warn"
    assert status_by_label["Unsafe shutdowns"] == "ok"
    assert status_by_label["Media errors"] == "ok"
