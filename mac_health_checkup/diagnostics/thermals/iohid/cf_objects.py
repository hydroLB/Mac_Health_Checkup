from __future__ import annotations

import ctypes

from mac_health_checkup.diagnostics.thermals.iohid.constants import (
    K_CF_NUMBER_SINT32,
    K_CF_STRING_ENCODING_UTF8,
)
from mac_health_checkup.diagnostics.thermals.iohid.types import (
    CFDictionaryKeyCallBacks,
    CFDictionaryValueCallBacks,
    HidApi,
)

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/iohid/cf_objects.py"


def release_all(api: HidApi, *values: ctypes.c_void_p) -> None:
    """
    Summary
    Release multiple CoreFoundation objects using CFRelease, ignoring null values.

    Inputs
    api: Bound CoreFoundation symbols.
    values: CFTypeRef pointers to release.

    Outputs
    None.

    Side effects
    Calls CFRelease on each non-null pointer.

    Error handling
    Never raises. Release failures are intentionally ignored to keep collection best-effort.

    Ties to other methods
    Used by `collect_temperature_samples_once` and IOHID matching helpers.

    Why this exists
    IOHID sampling allocates many transient CF objects; a shared helper keeps cleanup consistent and reduces duplicated null checks.
    """
    try:
        for value in values:
            if value:
                api.cf_release(value)
    except Exception:
        return


def create_cfstring(api: HidApi, name: bytes) -> ctypes.c_void_p | None:
    """
    Summary
    Create a UTF-8 CFString from a byte string.

    Inputs
    api: Bound CoreFoundation symbols.
    name: UTF-8 bytes.

    Outputs
    CFStringRef pointer or None on failure.

    Side effects
    Allocates a CFString.

    Error handling
    Returns None when CoreFoundation fails to create the string.

    Ties to other methods
    Used by `collect_temperature_samples_once` to build matching dictionaries and query properties.

    Why this exists
    Centralizes CFString creation so encoding and null-handling stay consistent across all IOHID helpers.
    """
    try:
        created = api.cf_string_create(ctypes.c_void_p(0), name, K_CF_STRING_ENCODING_UTF8)
        return created if created else None
    except Exception:
        return None


def create_cfnumbers(
    api: HidApi, *, page: int, usage: int
) -> tuple[ctypes.c_void_p | None, ctypes.c_void_p | None]:
    """
    Summary
    Create CFNumber values for PrimaryUsagePage and PrimaryUsage.

    Inputs
    api: Bound CoreFoundation symbols.
    page: HID PrimaryUsagePage numeric value.
    usage: HID PrimaryUsage numeric value.

    Outputs
    Tuple `(num_page, num_usage)` where each element may be None on failure.

    Side effects
    Allocates CFNumbers.

    Error handling
    Returns `(None, None)` on failure.

    Ties to other methods
    Used by IOHID matching dictionary creation.

    Why this exists
    Keeps CFNumber creation in one place so type selection remains consistent and easy to audit.
    """
    try:
        null = ctypes.c_void_p(0)
        num_page = api.cf_number_create(null, K_CF_NUMBER_SINT32, ctypes.byref(ctypes.c_int32(int(page))))
        num_usage = api.cf_number_create(null, K_CF_NUMBER_SINT32, ctypes.byref(ctypes.c_int32(int(usage))))
        return (num_page if num_page else None, num_usage if num_usage else None)
    except Exception:
        return (None, None)


def create_matching_dict(
    api: HidApi,
    *,
    key_usage_page: ctypes.c_void_p,
    key_usage: ctypes.c_void_p,
    num_page: ctypes.c_void_p,
    num_usage: ctypes.c_void_p,
) -> ctypes.c_void_p | None:
    """
    Summary
    Create a CFDictionary matching filter for IOHID services based on page and usage.

    Inputs
    api: Bound CoreFoundation symbols.
    key_usage_page: CFStringRef for "PrimaryUsagePage".
    key_usage: CFStringRef for "PrimaryUsage".
    num_page: CFNumberRef containing the page.
    num_usage: CFNumberRef containing the usage.

    Outputs
    CFDictionaryRef pointer or None on failure.

    Side effects
    Allocates a CFDictionary and uses kCFType callbacks.

    Error handling
    Returns None when dictionary creation fails.

    Ties to other methods
    Used by `collect_temperature_samples_once` to configure IOHIDEventSystemClient matching.

    Why this exists
    The matching dictionary is a common CF allocation path; keeping it isolated makes cleanup and future extensions safer.
    """
    try:
        null = ctypes.c_void_p(0)
        keys = (ctypes.c_void_p * 2)(key_usage_page, key_usage)
        values = (ctypes.c_void_p * 2)(num_page, num_usage)
        key_callbacks = CFDictionaryKeyCallBacks.in_dll(api.cf, "kCFTypeDictionaryKeyCallBacks")
        value_callbacks = CFDictionaryValueCallBacks.in_dll(api.cf, "kCFTypeDictionaryValueCallBacks")
        matching = api.cf_dictionary_create(
            null,
            keys,
            values,
            2,
            ctypes.byref(key_callbacks),
            ctypes.byref(value_callbacks),
        )
        return matching if matching else None
    except Exception:
        return None
