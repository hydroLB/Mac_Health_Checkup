from __future__ import annotations

import ctypes

from mac_health_checkup.diagnostics.thermals.iohid.constants import K_CF_STRING_ENCODING_UTF8
from mac_health_checkup.diagnostics.thermals.iohid.types import HidApi, as_void_p


def cfstring_to_str(api: HidApi, value: ctypes.c_void_p) -> str:
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
    Used by `collect_temperature_samples_once` for sensor product names.

    Why this exists
    CFStringGetCStringPtr is not reliable across encodings; CFStringGetCString is the safe conversion primitive.
    """
    try:
        if not value:
            return "Unknown Sensor"
        buf_len = 512
        buf = ctypes.create_string_buffer(buf_len)
        ok = bool(api.cf_string_get_cstring(value, buf, buf_len, K_CF_STRING_ENCODING_UTF8))
        if not ok:
            return "Unknown Sensor"
        decoded = buf.value.decode("utf-8", errors="replace").strip()
        return decoded or "Unknown Sensor"
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError):
        return "Unknown Sensor"


def is_cfstring(api: HidApi, value_ref: int) -> bool:
    """
    Summary
    Check whether a CFTypeRef pointer refers to a CFString instance.

    Inputs
    api: Bound CoreFoundation symbols.
    value_ref: Raw CFTypeRef pointer value as int.

    Outputs
    True when the value is a CFStringRef, otherwise false.

    Side effects
    None.

    Error handling
    Returns false on conversion failures.

    Ties to other methods
    Used by `collect_temperature_samples_once` before attempting CFString conversion.

    Why this exists
    Some IOKit properties can return non-string values; type checking prevents calling string APIs on the wrong type.
    """
    try:
        if value_ref <= 0:
            return False
        return int(api.cf_get_type_id(as_void_p(int(value_ref)))) == int(api.cf_string_get_type_id())
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError):
        return False


def release_if_present(api: HidApi, value: int | None) -> None:
    """
    Summary
    Release a CoreFoundation pointer if it is non-null.

    Inputs
    api: Bound CoreFoundation symbols.
    value: Raw pointer value as int or None.

    Outputs
    None.

    Side effects
    Calls CFRelease when the pointer is non-null.

    Error handling
    None. CFRelease failures are not surfaced.

    Ties to other methods
    Used across the IOHID collector to avoid leaking CF objects.

    Why this exists
    Keeps release logic uniform at call sites and reduces duplicated null checks.
    """
    if value:
        api.cf_release(as_void_p(int(value)))
