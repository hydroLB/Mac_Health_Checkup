from __future__ import annotations

from dataclasses import dataclass

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.thermals.iohid import collect_temperature_samples_once, load_hid_api
from mac_health_checkup.diagnostics.thermals.iohid.constants import TEMPERATURE_USAGE_CANDIDATES
from mac_health_checkup.diagnostics.thermals.iohid.types import HidApi
from mac_health_checkup.diagnostics.thermals.models import TemperatureReading
from mac_health_checkup.diagnostics.thermals.processing import status_for_temp, update_best_by_label

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/hid_event_system.py"


@dataclass(frozen=True)
class HidTemperatureResult:
    """
    Summary
    Represent a best-effort IOHIDEventSystem temperature collection result.

    Inputs
    readings: Parsed temperature readings in Celsius.
    raw_lines: Debug lines with sensor names and numeric values.
    error: Optional error string when collection fails.

    Outputs
    Value object for `collect_temperature_readings`.

    Side effects
    None.

    Error handling
    None. Errors are represented as strings.

    Ties to other methods
    Used by `ThermalSensorsDiagnostics` to populate the Performance section.

    Why this exists
    Keeps IOHID implementation details isolated while returning a stable typed payload to diagnostics callers.
    """

    readings: list[TemperatureReading]
    raw_lines: list[str]
    error: str | None = None


def collect_temperature_readings() -> HidTemperatureResult:
    """
    Summary
    Collect temperature readings via IOHIDEventSystemClient without sudo.

    Inputs
    None.

    Outputs
    `HidTemperatureResult` containing zero or more temperature readings.

    Side effects
    Calls into CoreFoundation + IOKit to enumerate HID temperature sensor services and query events.

    Error handling
    Returns an `error` string when the API cannot be loaded or a CoreFoundation call fails.

    Ties to other methods
    Called by `mac_health_checkup.diagnostics.thermals.collector.ThermalSensorsDiagnostics`.

    Why this exists
    Newer macOS builds increasingly restrict `powermetrics` without privileged helpers. IOHID temperature sensors can often be read without sudo and match the approach used by other low-level tooling.
    """
    try:
        api = load_hid_api()
        if api is None:
            return HidTemperatureResult(readings=[], raw_lines=[], error="IOKit/CoreFoundation unavailable")

        return _collect_with_api(api)
    except Exception as exc:
        return HidTemperatureResult(
            readings=[],
            raw_lines=[],
            error=format_error(
                MODULE_PATH, "collect_temperature_readings", "Failed collecting temperatures", exc
            ),
        )


def _collect_with_api(api: HidApi) -> HidTemperatureResult:
    """
    Summary
    Collect temperature readings using a pre-loaded IOHID API binding.

    Inputs
    api: Bound CoreFoundation/IOKit symbols.

    Outputs
    `HidTemperatureResult` containing zero or more readings plus raw debug lines.

    Side effects
    Queries IOHID services for temperature sensor events.

    Error handling
    Returns a populated `error` string when no readings can be collected.

    Ties to other methods
    Used by `collect_temperature_readings` after `load_hid_api` succeeds.

    Why this exists
    Keeps the library binding boundary (`load_hid_api`) separate from the multi-candidate sampling logic so the caller stays small and testable.
    """
    thresholds = get_config().thresholds
    raw_lines: list[str] = []
    errors: list[str] = []
    successful_queries = 0
    best_by_label: dict[str, float] = {}

    # Apple HID usage tables are not consistently documented across macOS releases.
    # The code path intentionally tries multiple (page, usage) combinations and returns the union.
    for page, usage in TEMPERATURE_USAGE_CANDIDATES:
        collected, collected_raw, err = collect_temperature_samples_once(api, page=page, usage=usage)
        raw_lines.extend(collected_raw)
        if err is not None:
            errors.append(f"{page:#06x}/{usage:#06x}:{err}")
            continue
        successful_queries += 1
        update_best_by_label(best_by_label, collected)

    readings: list[TemperatureReading] = []
    for name, celsius in best_by_label.items():
        status = status_for_temp(celsius, warn=thresholds.temp_warn_c, bad=thresholds.temp_bad_c)
        readings.append(TemperatureReading(label=name, celsius=celsius, status=status))
    readings.sort(key=lambda item: item.celsius, reverse=True)

    error: str | None = None
    if not readings:
        if errors:
            error = "; ".join(dict.fromkeys(errors))
        elif successful_queries > 0:
            error = "no_sensor_events"
        else:
            error = "no_sensors"
    return HidTemperatureResult(readings=readings, raw_lines=raw_lines, error=error)
