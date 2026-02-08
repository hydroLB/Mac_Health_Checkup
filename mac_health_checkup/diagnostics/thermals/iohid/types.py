"""
Summary
Typed ctypes structures and API surface for CoreFoundation and IOHID bindings.

Inputs
None.

Outputs
Dataclasses and structs used by the IOHID collector.

Side effects
None.

Error handling
None.

Ties to other methods
Used by `mac_health_checkup.diagnostics.thermals.iohid.bindings` and `mac_health_checkup.diagnostics.thermals.iohid.temperature`.

Why this exists
Separating types from logic keeps the collector code smaller and makes mypy constraints easier to satisfy.
"""

from __future__ import annotations

import ctypes
from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class HidApi:
    """
    Summary
    Bound CoreFoundation and IOKit symbols required for IOHID temperature sampling.

    Inputs
    cf: Loaded CoreFoundation dynamic library handle.
    iokit: Loaded IOKit dynamic library handle.
    ...: Bound function pointers used by the collector.

    Outputs
    An immutable container of function pointers.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `load_hid_api` and consumed by `collect_temperature_samples_once`.

    Why this exists
    Grouping bindings into one value object reduces argument churn and centralizes symbol loading.
    """

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


def as_void_p(value: int | None) -> ctypes.c_void_p:
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
    Used by `collect_temperature_samples_once` and `cfstring_to_str`.

    Why this exists
    ctypes returns many CFTypeRef values as raw integers; wrapping them explicitly keeps mypy happy and makes call sites consistent.
    """
    return ctypes.c_void_p(0 if value is None else int(value))


class CFDictionaryKeyCallBacks(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_long),
        ("retain", ctypes.c_void_p),
        ("release", ctypes.c_void_p),
        ("copy_description", ctypes.c_void_p),
        ("equal", ctypes.c_void_p),
        ("hash", ctypes.c_void_p),
    ]


class CFDictionaryValueCallBacks(ctypes.Structure):
    _fields_ = [
        ("version", ctypes.c_long),
        ("retain", ctypes.c_void_p),
        ("release", ctypes.c_void_p),
        ("copy_description", ctypes.c_void_p),
        ("equal", ctypes.c_void_p),
    ]
