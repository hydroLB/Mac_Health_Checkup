from __future__ import annotations

import pytest

from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.app.gui.sections import updates as updates_section
from mac_health_checkup.diagnostics.updates import SoftwareUpdateDiagnostics

MODULE_PATH = "tests/test_updates_section.py"


def test_update_section_renders_update_sizes(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure the Updates section renders per-update rows with parsed package sizes.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Monkeypatches `SoftwareUpdateDiagnostics.fetch` for deterministic section behavior.

    Error handling
    Raises `AssertionError` with module and method context on failure.

    Ties to other methods
    Exercises `mac_health_checkup.app.gui.sections.updates.update_section`.

    Why this exists
    Users should be able to see pending update names and sizes without reading raw diagnostics text.
    """
    try:
        monkeypatch.setattr(
            SoftwareUpdateDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "ok": True,
                    "updates_available": True,
                    "update_labels": ["macOS Sequoia 15.3-24D60", "Safari17.3Auto-17.3"],
                    "update_items": [
                        {"label": "macOS Sequoia 15.3-24D60", "size": "3274921KiB"},
                        {"label": "Safari17.3Auto-17.3", "size": "145221KiB"},
                    ],
                }
            ),
        )
        host = ConsoleHost()
        result = updates_section.update_section(host)
        rows = host.metrics.get("updates", [])
        assert result.get("ok") is True
        assert rows[0] == ("Updates", "2 available", "warn")
        assert ("Update 1", "macOS Sequoia 15.3-24D60 (3274921KiB)", "info") in rows
        assert ("Update 2", "Safari17.3Auto-17.3 (145221KiB)", "info") in rows
        assert host.fields.get("updates") == "2 updates available"
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
        raise AssertionError(f"{MODULE_PATH}:test_update_section_renders_update_sizes failed: {exc}") from exc


def test_update_section_falls_back_to_label_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure the Updates section still renders when diagnostics provide only legacy label lists.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Monkeypatches `SoftwareUpdateDiagnostics.fetch` for deterministic section behavior.

    Error handling
    Raises `AssertionError` with module and method context on failure.

    Ties to other methods
    Exercises the legacy-path fallback in `update_section`.

    Why this exists
    Backward compatibility keeps older snapshots and mocks functional while the diagnostics schema evolves.
    """
    try:
        monkeypatch.setattr(
            SoftwareUpdateDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "ok": True,
                    "updates_available": True,
                    "update_labels": ["CommandLineTools-15.3"],
                }
            ),
        )
        host = ConsoleHost()
        _ = updates_section.update_section(host)
        rows = host.metrics.get("updates", [])
        assert rows[0] == ("Updates", "1 available", "warn")
        assert ("Update 1", "CommandLineTools-15.3", "info") in rows
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
        raise AssertionError(f"{MODULE_PATH}:test_update_section_falls_back_to_label_list failed: {exc}") from exc
