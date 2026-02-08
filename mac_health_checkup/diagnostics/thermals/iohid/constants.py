"""
Summary
Constants for IOHIDEventSystemClient temperature sampling.

Inputs
None.

Outputs
Module-level constants used by the IOHID collector.

Side effects
None.

Error handling
None.

Ties to other methods
Used by `mac_health_checkup.diagnostics.thermals.iohid.temperature`.

Why this exists
Centralizes magic numbers and HID table candidates so changes are constrained to one location and safer to review.
"""

from __future__ import annotations

# CoreFoundation constants.
K_CF_STRING_ENCODING_UTF8 = 0x0800_0100
K_CF_NUMBER_SINT32 = 3

# IOHIDEventTypes constants.
K_IOHID_EVENT_TYPE_TEMPERATURE = 15
K_IOHID_EVENT_FIELD_TEMPERATURE = K_IOHID_EVENT_TYPE_TEMPERATURE << 16

# Apple HID usage table candidates for temperature sensors.
# Values vary across macOS versions; callers should try candidates in order and merge results.
TEMPERATURE_USAGE_CANDIDATES: list[tuple[int, int]] = [
    (0xFF05, 0x0005),  # kHIDPage_AppleVendorTemperatureSensor / kHIDUsage_AppleVendor_TemperatureSensor
    (0xFF00, 0x0005),  # Fallback: AppleVendor page with temperature usage
]

# Sanity bounds to avoid reporting garbage values.
MIN_REASONABLE_C = -50.0
MAX_REASONABLE_C = 250.0

# Matching dictionary keys and property names.
KEY_PRIMARY_USAGE_PAGE = b"PrimaryUsagePage"
KEY_PRIMARY_USAGE = b"PrimaryUsage"
PROP_PRODUCT = b"Product"
