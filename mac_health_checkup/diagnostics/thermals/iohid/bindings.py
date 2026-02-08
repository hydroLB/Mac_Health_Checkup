from __future__ import annotations

import ctypes
import ctypes.util

from mac_health_checkup.diagnostics.thermals.iohid.types import HidApi


def load_hid_api() -> HidApi | None:
    """
    Summary
    Load CoreFoundation and IOKit libraries and bind required symbols.

    Inputs
    None.

    Outputs
    `HidApi` on success, otherwise None.

    Side effects
    Loads dynamic libraries into the process.

    Error handling
    Returns None when any required symbol cannot be loaded.

    Ties to other methods
    Used by `mac_health_checkup.diagnostics.thermals.hid_event_system.collect_temperature_readings`.

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

        return HidApi(
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
