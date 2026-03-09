from __future__ import annotations

from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/parsing/base.py"


def get_section(raw: JsonDict, key: str) -> JsonDict:
    """
    Summary
    Retrieve a required config section from raw JSON.

    Inputs
    raw: Raw config dict.
    key: Section key.

    Outputs
    Section dict.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context when the section is missing or invalid.

    Ties to other methods
    Used by all section parsing functions.

    Why this exists
    Keeps section boundary checks consistent across the config parser.
    """
    try:
        section = raw.get(key)
        if not isinstance(section, dict):
            raise ValueError(f"section {key} missing or invalid")
        return section
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(format_error(MODULE_PATH, "get_section", "Invalid config section", exc)) from exc
