from __future__ import annotations

import pytest

from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.app.gui.sections import fan as fan_section
from mac_health_checkup.app.gui.sections import performance as performance_section
from mac_health_checkup.diagnostics.fan import FanDiagnostics
from mac_health_checkup.diagnostics.power import PowerResidencyDiagnostics
from mac_health_checkup.diagnostics.thermals import ThermalSensorsDiagnostics

MODULE_PATH = "tests/test_fan_performance_sections.py"


def test_fan_section_ignores_temperature_guidance_when_no_fans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Summary
    Ensure fan rendering does not expose thermal-guidance warnings when no fan readings exist.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Monkeypatches fan and thermal diagnostics to deterministic empty payloads.

    Error handling
    Raises `AssertionError` with module and method context on failures.

    Ties to other methods
    Exercises `mac_health_checkup.app.gui.sections.fan.update_section`.

    Why this exists
    The fan section should stay focused on fan availability and not show temperature collection warnings.
    """
    try:
        warning_text = (
            "No temperature sensors returned data. On some macOS builds, Apple restricts low-level sensors."
        )
        monkeypatch.setattr(
            ThermalSensorsDiagnostics,
            "fetch",
            staticmethod(lambda: {"ok": False, "fans": [], "guidance": warning_text, "source": "iohid"}),
        )
        monkeypatch.setattr(
            FanDiagnostics,
            "fetch",
            staticmethod(lambda: {"status": "No fan data", "fans": [], "raw": ""}),
        )

        host = ConsoleHost()
        payload = fan_section.update_section(host)

        assert payload.get("ok") is False
        assert host.fields.get("fan") == "Fan speeds unavailable"
        assert warning_text not in host.fields.get("fan", "")
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
            f"{MODULE_PATH}:test_fan_section_ignores_temperature_guidance_when_no_fans failed: {exc}"
        ) from exc


def test_performance_section_hides_temperature_when_sensors_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Summary
    Ensure performance rendering omits temperature warnings when thermal sensors are unavailable.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Monkeypatches thermal and power diagnostics to deterministic payloads.

    Error handling
    Raises `AssertionError` with module and method context on failures.

    Ties to other methods
    Exercises `mac_health_checkup.app.gui.sections.performance.update_section`.

    Why this exists
    Temperature should be hidden when unavailable while still showing available power metrics.
    """
    try:
        monkeypatch.setattr(
            ThermalSensorsDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "ok": False,
                    "sensors": [],
                    "guidance": "No temperature sensors returned data.",
                    "source": "iohid_event_system",
                }
            ),
        )
        monkeypatch.setattr(
            PowerResidencyDiagnostics,
            "fetch",
            staticmethod(lambda: {"cpu_w": 9.4, "gpu_w": 1.7, "ane_w": None, "ok": True}),
        )

        host = ConsoleHost()
        payload = performance_section.update_section(host)
        summary = host.fields.get("performance", "")
        rows = host.metrics.get("performance", [])

        assert isinstance(payload, dict)
        assert summary == "Power: CPU 9.4 W | GPU 1.7 W"
        assert "temperature" not in summary.lower()
        assert all("C" not in value for _label, value, _status in rows)
        assert ("CPU Power", "9.4 W", "info") in rows
        assert ("GPU Power", "1.7 W", "info") in rows
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
            f"{MODULE_PATH}:test_performance_section_hides_temperature_when_sensors_unavailable failed: {exc}"
        ) from exc
