from __future__ import annotations

import pytest

from mac_health_checkup.diagnostics.thermals.collector import ThermalSensorsDiagnostics
from mac_health_checkup.diagnostics.thermals.hid_event_system import HidTemperatureResult
from mac_health_checkup.diagnostics.thermals.models import TemperatureReading

MODULE_PATH = "tests/test_thermals_hid_collector.py"


def test_thermals_fetch_returns_hid_readings(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure the thermals collector returns IOHID readings in the expected JSON shape.

    Inputs
    None.

    Outputs
    None.

    Side effects
    Monkeypatches the IOHID collection function.

    Error handling
    Relies on pytest assertions.

    Ties to other methods
    Exercises `ThermalSensorsDiagnostics._fetch_uncached`.

    Why this exists
    Prevents regressions where the collector silently switches sources or changes payload shape.
    """

    from mac_health_checkup.diagnostics.thermals import collector as thermals_collector

    def _fake_collect_temperature_readings() -> HidTemperatureResult:
        """
        Summary
        Execute `_fake_collect_temperature_readings` for its module-level responsibility.

        Inputs
        None.

        Outputs
        Returns `HidTemperatureResult`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_thermals_hid_collector.py:_fake_collect_temperature_readings` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_thermals_hid_collector.py`.

        Why this exists
        Keeps `_fake_collect_temperature_readings` explicit, testable, and maintainable.
        """
        return HidTemperatureResult(
            readings=[TemperatureReading(label="CPU Core", celsius=42.0, status="ok")],
            raw_lines=["CPU Core: 42.000 C"],
            error=None,
        )

    monkeypatch.setattr(
        thermals_collector, "collect_temperature_readings", _fake_collect_temperature_readings
    )

    payload = ThermalSensorsDiagnostics._fetch_uncached()
    assert payload["ok"] is True
    assert payload["source"] == "iohid_event_system"
    sensors = payload.get("sensors")
    assert isinstance(sensors, list)
    assert sensors and isinstance(sensors[0], dict)
    assert sensors[0].get("label") == "CPU Core"
    assert sensors[0].get("celsius") == 42.0


def test_thermals_fetch_returns_guidance_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure the thermals collector returns actionable guidance when no sensors are available.

    Inputs
    None.

    Outputs
    None.

    Side effects
    Monkeypatches the IOHID collection function.

    Error handling
    Relies on pytest assertions.

    Ties to other methods
    Exercises `ThermalSensorsDiagnostics._fetch_uncached`.

    Why this exists
    Temperature sensors are optional on some macOS builds; the UI should still show a clear explanation.
    """

    from mac_health_checkup.diagnostics.thermals import collector as thermals_collector

    def _fake_collect_temperature_readings() -> HidTemperatureResult:
        """
        Summary
        Execute `_fake_collect_temperature_readings` for its module-level responsibility.

        Inputs
        None.

        Outputs
        Returns `HidTemperatureResult`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_thermals_hid_collector.py:_fake_collect_temperature_readings` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_thermals_hid_collector.py`.

        Why this exists
        Keeps `_fake_collect_temperature_readings` explicit, testable, and maintainable.
        """
        return HidTemperatureResult(readings=[], raw_lines=[], error="no_services")

    monkeypatch.setattr(
        thermals_collector, "collect_temperature_readings", _fake_collect_temperature_readings
    )

    payload = ThermalSensorsDiagnostics._fetch_uncached()
    assert payload["ok"] is False
    assert payload["source"] == "iohid_event_system"
    assert isinstance(payload.get("error"), str)
    assert isinstance(payload.get("guidance"), str)
