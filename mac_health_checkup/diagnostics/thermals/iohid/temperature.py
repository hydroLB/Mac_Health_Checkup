from __future__ import annotations

import ctypes

from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.thermals.iohid.cf_objects import (
    create_cfnumbers,
    create_cfstring,
    create_matching_dict,
    release_all,
)
from mac_health_checkup.diagnostics.thermals.iohid.constants import (
    KEY_PRIMARY_USAGE,
    KEY_PRIMARY_USAGE_PAGE,
    PROP_PRODUCT,
)
from mac_health_checkup.diagnostics.thermals.iohid.service_readers import (
    read_service_product_name,
    read_service_temperature_celsius,
)
from mac_health_checkup.diagnostics.thermals.iohid.types import HidApi

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/iohid/temperature.py"


def collect_temperature_samples_once(
    api: HidApi, *, page: int, usage: int
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
    Used by `mac_health_checkup.diagnostics.thermals.hid_event_system.collect_temperature_readings`.

    Why this exists
    Some macOS versions report temperature sensors under different pages; isolating one pass keeps retries clean.
    """
    key_usage_page = create_cfstring(api, KEY_PRIMARY_USAGE_PAGE)
    key_usage = create_cfstring(api, KEY_PRIMARY_USAGE)
    prop_product = create_cfstring(api, PROP_PRODUCT)
    if not key_usage_page or not key_usage or not prop_product:
        release_all(api, *(ptr for ptr in (key_usage_page, key_usage, prop_product) if ptr))
        return ([], [], "failed_to_create_cfstrings")

    num_page, num_usage = create_cfnumbers(api, page=page, usage=usage)
    if not num_page or not num_usage:
        release_all(
            api,
            *(ptr for ptr in (key_usage_page, key_usage, prop_product, num_page, num_usage) if ptr),
        )
        return ([], [], "failed_to_create_cfnumbers")

    matching = create_matching_dict(
        api,
        key_usage_page=key_usage_page,
        key_usage=key_usage,
        num_page=num_page,
        num_usage=num_usage,
    )
    release_all(api, key_usage_page, key_usage, num_page, num_usage)

    if not matching:
        release_all(api, prop_product)
        return ([], [], "failed_to_create_matching_dict")

    system = api.hid_system_client_create(ctypes.c_void_p(0))
    if not system:
        release_all(api, prop_product, matching)
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
            name = read_service_product_name(api, service=svc, product_key=prop_product)
            value = read_service_temperature_celsius(api, service=svc)
            if value is None:
                continue
            out.append((name, value))
            raw_lines.append(f"{name}: {value:.3f} C")
        return (out, raw_lines, None)
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError) as exc:
        return (
            [],
            [],
            format_error(MODULE_PATH, "collect_temperature_samples_once", "IOHID collection failed", exc),
        )
    finally:
        if services:
            api.cf_release(services)
        release_all(api, prop_product, matching, system)
