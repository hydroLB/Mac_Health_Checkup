from __future__ import annotations

import ctypes
import ctypes.util
import math
from collections.abc import Callable
from dataclasses import dataclass

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.thermals.models import TemperatureReading

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
        api = _load_hid_api()
        if api is None:
            return HidTemperatureResult(readings=[], raw_lines=[], error="IOKit/CoreFoundation unavailable")

        thresholds = get_config().thresholds
        raw_lines: list[str] = []
        errors: list[str] = []
        successful_queries = 0
        best_by_label: dict[str, float] = {}

        # Apple HID usage tables are not consistently documented across macOS releases.
        # The code path intentionally tries multiple (page, usage) combinations and returns the union.
        candidates: list[tuple[int, int]] = [
            (
                0xFF05,
                0x0005,
            ),  # kHIDPage_AppleVendorTemperatureSensor / kHIDUsage_AppleVendor_TemperatureSensor
            (0xFF00, 0x0005),  # Fallback: AppleVendor page with temperature usage
        ]

        for page, usage in candidates:
            collected, collected_raw, err = _collect_once(api, page=page, usage=usage)
            raw_lines.extend(collected_raw)
            if err is not None:
                errors.append(f"{page:#06x}/{usage:#06x}:{err}")
                continue
            successful_queries += 1
            for name, celsius in collected:
                existing = best_by_label.get(name)
                if existing is None or celsius > existing:
                    best_by_label[name] = celsius

        readings: list[TemperatureReading] = []
        for name, celsius in best_by_label.items():
            status = _status_for_temp(celsius, warn=thresholds.temp_warn_c, bad=thresholds.temp_bad_c)
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
    except Exception as exc:
        return HidTemperatureResult(
            readings=[],
            raw_lines=[],
            error=format_error(
                MODULE_PATH, "collect_temperature_readings", "Failed collecting temperatures", exc
            ),
        )


def _status_for_temp(value_c: float, *, warn: float, bad: float) -> str:
    """
    Summary
    Map a numeric temperature into an ok/warn/bad status based on config thresholds.

    Inputs
    value_c: Temperature in Celsius.
    warn: Warning threshold in Celsius.
    bad: Bad threshold in Celsius.

    Outputs
    Status string: "ok", "warn", or "bad".

    Side effects
    None.

    Error handling
    Returns "ok" when the input is non-finite.

    Ties to other methods
    Used by `collect_temperature_readings`.

    Why this exists
    Keeps the UI consistent by applying the same thresholding behavior across different temperature sources.
    """
    try:
        if not math.isfinite(float(value_c)):
            return "ok"
        value = float(value_c)
        if value >= float(bad):
            return "bad"
        if value >= float(warn):
            return "warn"
        return "ok"
    except Exception:
        return "ok"


@dataclass(frozen=True)
class _HidApi:
    cf: ctypes.CDLL
    iokit: ctypes.CDLL

    # CoreFoundation symbols and callback structs.
    cf_release: Callable[[ctypes.c_void_p], None]
    cf_get_type_id: Callable[[ctypes.c_void_p], int]
    cf_string_get_type_id: Callable[[], int]
    cf_string_create: Callable[[ctypes.c_void_p, bytes, int], ctypes.c_void_p]
    cf_string_get_cstring: Callable[[ctypes.c_void_p, object, int, int], bool]
    cf_number_create: Callable[[ctypes.c_void_p, int, object], ctypes.c_void_p]
    cf_dictionary_create: Callable[
        [ctypes.c_void_p, object, object, int, object, object],
        ctypes.c_void_p,
    ]
    cf_array_get_count: Callable[[ctypes.c_void_p], int]
    cf_array_get_value_at_index: Callable[[ctypes.c_void_p, int], ctypes.c_void_p]

    # IOHID / IOHIDEventSystemClient symbols.
    hid_system_client_create: Callable[[ctypes.c_void_p], ctypes.c_void_p]
    hid_system_client_set_matching: Callable[[ctypes.c_void_p, ctypes.c_void_p], int]
    hid_system_client_copy_services: Callable[[ctypes.c_void_p], ctypes.c_void_p]
    hid_service_copy_event: Callable[[ctypes.c_void_p, int, int, int], ctypes.c_void_p]
    hid_service_copy_property: Callable[[ctypes.c_void_p, ctypes.c_void_p], ctypes.c_void_p]
    hid_event_get_float_value: Callable[[ctypes.c_void_p, int], float]


def _as_void_p(value: int | None) -> ctypes.c_void_p:
    """
    Summary
    Convert a pointer-sized integer into a `ctypes.c_void_p` for CoreFoundation/IOKit calls.

    Inputs
    value: Pointer value as int (or None).

    Outputs
    `ctypes.c_void_p` instance with the provided pointer value.

    Side effects
    None.

    Error handling
    Returns a null pointer for None.

    Ties to other methods
    Used by `_collect_once` and `_cfstring_to_str`.

    Why this exists
    ctypes returns many CFTypeRef values as raw integers; wrapping them explicitly keeps mypy happy and makes call sites consistent.
    """
    return ctypes.c_void_p(0 if value is None else int(value))


class _CFDictionaryKeyCallBacks(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_long),
        ("retain", ctypes.c_void_p),
        ("release", ctypes.c_void_p),
        ("copy_description", ctypes.c_void_p),
        ("equal", ctypes.c_void_p),
        ("hash", ctypes.c_void_p),
    ]


class _CFDictionaryValueCallBacks(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_long),
        ("retain", ctypes.c_void_p),
        ("release", ctypes.c_void_p),
        ("copy_description", ctypes.c_void_p),
        ("equal", ctypes.c_void_p),
    ]


def _load_hid_api() -> _HidApi | None:
    """
    Summary
    Load CoreFoundation and IOKit libraries and bind required symbols.

    Inputs
    None.

    Outputs
    `_HidApi` on success, otherwise None.

    Side effects
    Loads dynamic libraries into the process.

    Error handling
    Returns None when any required symbol cannot be loaded.

    Ties to other methods
    Used by `collect_temperature_readings`.

    Why this exists
    The IOHID symbols used here are not part of the stable public SDK surface for Python. Binding via ctypes keeps dependencies minimal while allowing best-effort access.
    """
    try:
        cf_path = ctypes.util.find_library("CoreFoundation")
        iokit_path = ctypes.util.find_library("IOKit")
        if not cf_path or not iokit_path:
            return None
        cf = ctypes.CDLL(cf_path)
        iokit = ctypes.CDLL(iokit_path)

        # CoreFoundation
        cf_release = cf.CFRelease
        cf_release.restype = None
        cf_release.argtypes = [ctypes.c_void_p]

        cf_get_type_id = cf.CFGetTypeID
        cf_get_type_id.restype = ctypes.c_ulong
        cf_get_type_id.argtypes = [ctypes.c_void_p]

        cf_string_get_type_id = cf.CFStringGetTypeID
        cf_string_get_type_id.restype = ctypes.c_ulong
        cf_string_get_type_id.argtypes = []

        cf_string_create = cf.CFStringCreateWithCString
        cf_string_create.restype = ctypes.c_void_p
        cf_string_create.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]

        cf_string_get_cstring = cf.CFStringGetCString
        cf_string_get_cstring.restype = ctypes.c_bool
        cf_string_get_cstring.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]

        cf_number_create = cf.CFNumberCreate
        cf_number_create.restype = ctypes.c_void_p
        cf_number_create.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]

        cf_dictionary_create = cf.CFDictionaryCreate
        cf_dictionary_create.restype = ctypes.c_void_p
        cf_dictionary_create.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_long,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]

        cf_array_get_count = cf.CFArrayGetCount
        cf_array_get_count.restype = ctypes.c_long
        cf_array_get_count.argtypes = [ctypes.c_void_p]

        cf_array_get_value_at_index = cf.CFArrayGetValueAtIndex
        cf_array_get_value_at_index.restype = ctypes.c_void_p
        cf_array_get_value_at_index.argtypes = [ctypes.c_void_p, ctypes.c_long]

        # IOHID / IOHIDEventSystemClient
        hid_system_client_create = iokit.IOHIDEventSystemClientCreate
        hid_system_client_create.restype = ctypes.c_void_p
        hid_system_client_create.argtypes = [ctypes.c_void_p]

        hid_system_client_set_matching = iokit.IOHIDEventSystemClientSetMatching
        hid_system_client_set_matching.restype = ctypes.c_int
        hid_system_client_set_matching.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        hid_system_client_copy_services = iokit.IOHIDEventSystemClientCopyServices
        hid_system_client_copy_services.restype = ctypes.c_void_p
        hid_system_client_copy_services.argtypes = [ctypes.c_void_p]

        hid_service_copy_event = iokit.IOHIDServiceClientCopyEvent
        hid_service_copy_event.restype = ctypes.c_void_p
        hid_service_copy_event.argtypes = [
            ctypes.c_void_p,
            ctypes.c_longlong,
            ctypes.c_int,
            ctypes.c_longlong,
        ]

        hid_service_copy_property = iokit.IOHIDServiceClientCopyProperty
        hid_service_copy_property.restype = ctypes.c_void_p
        hid_service_copy_property.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

        hid_event_get_float_value = iokit.IOHIDEventGetFloatValue
        hid_event_get_float_value.restype = ctypes.c_double
        hid_event_get_float_value.argtypes = [ctypes.c_void_p, ctypes.c_int]

        return _HidApi(
            cf=cf,
            iokit=iokit,
            cf_release=cf_release,
            cf_get_type_id=cf_get_type_id,
            cf_string_get_type_id=cf_string_get_type_id,
            cf_string_create=cf_string_create,
            cf_string_get_cstring=cf_string_get_cstring,
            cf_number_create=cf_number_create,
            cf_dictionary_create=cf_dictionary_create,
            cf_array_get_count=cf_array_get_count,
            cf_array_get_value_at_index=cf_array_get_value_at_index,
            hid_system_client_create=hid_system_client_create,
            hid_system_client_set_matching=hid_system_client_set_matching,
            hid_system_client_copy_services=hid_system_client_copy_services,
            hid_service_copy_event=hid_service_copy_event,
            hid_service_copy_property=hid_service_copy_property,
            hid_event_get_float_value=hid_event_get_float_value,
        )
    except Exception:
        return None


def _collect_once(
    api: _HidApi, *, page: int, usage: int
) -> tuple[list[tuple[str, float]], list[str], str | None]:
    """
    Summary
    Collect one pass of (name, celsius) readings for a given (page, usage) match.

    Inputs
    api: Bound CoreFoundation/IOKit symbols.
    page: PrimaryUsagePage value.
    usage: PrimaryUsage value.

    Outputs
    Tuple `(samples, raw_lines, error)`.

    Side effects
    Allocates and releases CoreFoundation objects and queries IOHID services.

    Error handling
    Returns `error` on failure instead of raising.

    Ties to other methods
    Used by `collect_temperature_readings` to try multiple usage definitions.

    Why this exists
    Some macOS versions report temperature sensors under different pages; isolating one pass keeps retries clean.
    """
    # CoreFoundation constants.
    k_cf_string_encoding_utf8 = 0x0800_0100
    k_cf_number_sint32 = 3

    k_iohid_event_type_temperature = 15
    event_field = int(k_iohid_event_type_temperature) << 16

    null = ctypes.c_void_p(0)

    # Create CFStrings for matching keys and product property.
    key_usage_page = api.cf_string_create(null, b"PrimaryUsagePage", k_cf_string_encoding_utf8)
    key_usage = api.cf_string_create(null, b"PrimaryUsage", k_cf_string_encoding_utf8)
    prop_product = api.cf_string_create(null, b"Product", k_cf_string_encoding_utf8)
    if not key_usage_page or not key_usage or not prop_product:
        for item in (key_usage_page, key_usage, prop_product):
            if item:
                api.cf_release(item)
        return ([], [], "failed_to_create_cfstrings")

    num_page = api.cf_number_create(null, k_cf_number_sint32, ctypes.byref(ctypes.c_int32(int(page))))
    num_usage = api.cf_number_create(null, k_cf_number_sint32, ctypes.byref(ctypes.c_int32(int(usage))))
    if not num_page or not num_usage:
        for item in (key_usage_page, key_usage, prop_product, num_page, num_usage):
            if item:
                api.cf_release(item)
        return ([], [], "failed_to_create_cfnumbers")

    # Build matching dict using CF type callbacks.
    keys = (ctypes.c_void_p * 2)(key_usage_page, key_usage)
    values = (ctypes.c_void_p * 2)(num_page, num_usage)
    key_callbacks = _CFDictionaryKeyCallBacks.in_dll(api.cf, "kCFTypeDictionaryKeyCallBacks")
    value_callbacks = _CFDictionaryValueCallBacks.in_dll(api.cf, "kCFTypeDictionaryValueCallBacks")
    matching = api.cf_dictionary_create(
        null,
        keys,
        values,
        2,
        ctypes.byref(key_callbacks),
        ctypes.byref(value_callbacks),
    )

    # Safe to release key/value objects after dictionary creation because the dictionary retains them.
    for item in (key_usage_page, key_usage, num_page, num_usage):
        api.cf_release(item)

    if not matching:
        api.cf_release(prop_product)
        return ([], [], "failed_to_create_matching_dict")

    system = api.hid_system_client_create(null)
    if not system:
        api.cf_release(prop_product)
        api.cf_release(matching)
        return ([], [], "failed_to_create_hid_system_client")

    services = None
    try:
        rc = int(api.hid_system_client_set_matching(system, matching))
        if rc != 0:
            return ([], [], f"set_matching_failed rc={rc}")
        services = api.hid_system_client_copy_services(system)
        if not services:
            return ([], [], "no_services")

        out: list[tuple[str, float]] = []
        raw_lines: list[str] = []
        count = int(api.cf_array_get_count(services))
        for idx in range(count):
            svc = api.cf_array_get_value_at_index(services, idx)
            if not svc:
                continue
            name_ref = api.hid_service_copy_property(svc, prop_product)
            name = "Unknown Sensor"
            if name_ref:
                try:
                    if int(api.cf_get_type_id(_as_void_p(int(name_ref)))) == int(api.cf_string_get_type_id()):
                        name = _cfstring_to_str(api, _as_void_p(int(name_ref)))
                finally:
                    api.cf_release(name_ref)

            event = api.hid_service_copy_event(svc, int(k_iohid_event_type_temperature), 0, 0)
            if not event:
                continue
            try:
                value = float(api.hid_event_get_float_value(event, int(event_field)))
            finally:
                api.cf_release(event)
            if not math.isfinite(value):
                continue
            # Basic sanity bounds to avoid reporting garbage values.
            if value < -50.0 or value > 250.0:
                continue
            out.append((name, value))
            raw_lines.append(f"{name}: {value:.3f} C")
        return (out, raw_lines, None)
    except Exception as exc:
        return (
            [],
            [],
            format_error(MODULE_PATH, "_collect_once", "IOHID collection failed", exc),
        )
    finally:
        if services:
            api.cf_release(services)
        if prop_product:
            api.cf_release(prop_product)
        if matching:
            api.cf_release(matching)
        if system:
            api.cf_release(system)


def _cfstring_to_str(api: _HidApi, value: ctypes.c_void_p) -> str:
    """
    Summary
    Convert a CFStringRef to a Python str.

    Inputs
    api: Bound CoreFoundation symbols.
    value: CFStringRef.

    Outputs
    UTF-8 decoded string.

    Side effects
    Allocates a temporary buffer.

    Error handling
    Returns a placeholder string on conversion failure.

    Ties to other methods
    Used by `_collect_once` for sensor product names.

    Why this exists
    CFStringGetCStringPtr is not reliable across encodings; CFStringGetCString is the safe conversion primitive.
    """
    try:
        if not value:
            return "Unknown Sensor"
        buf_len = 512
        buf = ctypes.create_string_buffer(buf_len)
        k_cf_string_encoding_utf8 = 0x0800_0100
        ok = bool(api.cf_string_get_cstring(value, buf, buf_len, k_cf_string_encoding_utf8))
        if not ok:
            return "Unknown Sensor"
        decoded = buf.value.decode("utf-8", errors="replace").strip()
        return decoded or "Unknown Sensor"
    except Exception:
        return "Unknown Sensor"
