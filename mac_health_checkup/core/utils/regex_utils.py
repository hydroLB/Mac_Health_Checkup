from __future__ import annotations

import re
from typing import Optional

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/regex_utils.py"


def regex_extract_int(text: str, pattern: str) -> Optional[int]:
    """
    Purpose: Extract the first integer matching a regex pattern.
    Ties: Used by diagnostics parsing helpers.
    Inputs: text is input string, pattern is regex with a capture group.
    Outputs: Parsed int or None if not found or invalid.
    Side effects: None.
    Why: Centralizes safe integer extraction for diagnostics output.
    """
    try:
        match = re.search(pattern, text)
        if not match:
            return None
        raw = match.group(1)
        return int(raw.replace(",", ""))
    except (AttributeError, ValueError, re.error) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "regex_extract_int", "Failed to extract int", exc)
        ) from exc


def regex_extract_float(text: str, pattern: str) -> Optional[float]:
    """
    Purpose: Extract the first float matching a regex pattern.
    Ties: Used by diagnostics parsing helpers.
    Inputs: text is input string, pattern is regex with a capture group.
    Outputs: Parsed float or None if not found or invalid.
    Side effects: None.
    Why: Centralizes safe float extraction for diagnostics output.
    """
    try:
        match = re.search(pattern, text)
        if not match:
            return None
        raw = match.group(1)
        return float(raw.replace(",", ""))
    except (AttributeError, ValueError, re.error) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "regex_extract_float", "Failed to extract float", exc)
        ) from exc


def regex_extract_str(text: str, pattern: str) -> Optional[str]:
    """
    Purpose: Extract the first string matching a regex pattern.
    Ties: Used by diagnostics parsing helpers.
    Inputs: text is input string, pattern is regex with a capture group.
    Outputs: Extracted string or None if not found.
    Side effects: None.
    Why: Centralizes safe string extraction for diagnostics output.
    """
    try:
        match = re.search(pattern, text)
        if not match:
            return None
        return match.group(1).strip()
    except (AttributeError, re.error) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "regex_extract_str", "Failed to extract string", exc)
        ) from exc


def hz_from_text(text: str) -> str:
    """
    Purpose: Normalize refresh rate strings into a compact Hz label.
    Ties: Used by display parsing and benchmarks.
    Inputs: text contains a refresh rate substring.
    Outputs: Normalized string like "60Hz" or "?" if not found.
    Side effects: None.
    Why: Keeps refresh rate formatting consistent across the UI.
    """
    try:
        match = re.search(r"(\d+(?:\.\d+)?)\s*Hz", text, re.IGNORECASE)
        if not match:
            return "?"
        hz_value = float(match.group(1))
        return f"{int(round(hz_value))}Hz"
    except (AttributeError, ValueError, re.error) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "hz_from_text", "Failed to parse Hz", exc)) from exc
