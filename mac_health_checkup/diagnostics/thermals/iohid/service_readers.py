from __future__ import annotations

import ctypes
import math

from mac_health_checkup.diagnostics.thermals.iohid.constants import (
    K_IOHID_EVENT_FIELD_TEMPERATURE,
    K_IOHID_EVENT_TYPE_TEMPERATURE,
    MAX_REASONABLE_C,
    MIN_REASONABLE_C,
)
from mac_health_checkup.diagnostics.thermals.iohid.corefoundation import cfstring_to_str, is_cfstring
from mac_health_checkup.diagnostics.thermals.iohid.types import HidApi, as_void_p

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/iohid/service_readers.py"


def read_service_product_name(api: HidApi, *, service: ctypes.c_void_p, product_key: ctypes.c_void_p) -> str:
    """
    Summary
    Read the "Product" property from an IOHID service as a best-effort sensor name.

    Inputs
    api: Bound CoreFoundation/IOKit symbols.
    service: IOHIDServiceClientRef pointer.
    product_key: CFStringRef for the "Product" property.

    Outputs
    Sensor name string. Returns "Unknown Sensor" on failure.

    Side effects
    Calls IOHIDServiceClientCopyProperty and releases any returned CF object.

    Error handling
    Returns a placeholder name when the property is missing or non-string.

    Ties to other methods
    Used by `collect_temperature_samples_once` when building samples and raw debug lines.

    Why this exists
    Naming varies across macOS versions and hardware; isolating property handling makes it safer to add additional naming fallbacks later.
    """
    name_ref = api.hid_service_copy_property(service, product_key)
    if not name_ref:
        return "Unknown Sensor"
    try:
        if is_cfstring(api, int(name_ref)):
            return cfstring_to_str(api, as_void_p(int(name_ref)))
        return "Unknown Sensor"
    finally:
        api.cf_release(name_ref)


def read_service_temperature_celsius(api: HidApi, *, service: ctypes.c_void_p) -> float | None:
    """
    Summary
    Read a temperature event from a service and return a sane Celsius value.

    Inputs
    api: Bound CoreFoundation/IOKit symbols.
    service: IOHIDServiceClientRef pointer.

    Outputs
    Celsius float when available and within bounds; otherwise None.

    Side effects
    Calls IOHIDServiceClientCopyEvent and releases the returned event.

    Error handling
    Returns None when the event is missing, non-finite, or outside bounds.

    Ties to other methods
    Used by `collect_temperature_samples_once` inside the service enumeration loop.

    Why this exists
    Separates numeric sanity checks and event handling so the main loop stays readable and can be extended for other sensor event types later.
    """
    event = api.hid_service_copy_event(service, int(K_IOHID_EVENT_TYPE_TEMPERATURE), 0, 0)
    if not event:
        return None
    try:
        value = float(api.hid_event_get_float_value(event, int(K_IOHID_EVENT_FIELD_TEMPERATURE)))
    finally:
        api.cf_release(event)
    if not math.isfinite(value):
        return None
    if value < float(MIN_REASONABLE_C) or value > float(MAX_REASONABLE_C):
        return None
    return value
