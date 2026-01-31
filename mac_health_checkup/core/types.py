from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

MODULE_PATH = "mac_health_checkup/core/types.py"


JsonPrimitive = str | int | float | bool | None
JsonValue = JsonPrimitive | Sequence["JsonValue"] | Mapping[str, "JsonValue"]
JsonDict = dict[str, JsonValue]


@dataclass(frozen=True)
class TableData:
    """
    Purpose: Bundle headers and rows for table rendering.
    Ties: Used by GUI sections and tests to pass table data around.
    Inputs: headers are column labels, rows are row tuples.
    Outputs: Immutable container with headers and rows.
    Side effects: None.
    Why: Keeps table output strongly typed and explicit.
    """

    headers: tuple[str, ...]
    rows: list[tuple[str, ...]]


@dataclass(frozen=True)
class MetricsTable:
    """
    Purpose: Bundle metric table rows and column count.
    Ties: Used by metrics rendering in GUI sections.
    Inputs: rows are (label, value, status) tuples, columns sets layout.
    Outputs: Immutable container for metrics data.
    Side effects: None.
    Why: Keeps metric output strongly typed and consistent.
    """

    rows: list[tuple[str, str, str]]
    columns: int


@dataclass(frozen=True)
class RedactionConfig:
    """
    Purpose: Carry redaction settings for structured logging.
    Ties: Used by loggers to protect secrets.
    Inputs: keys are case insensitive redaction keys, replacement is value string.
    Outputs: Immutable config for redaction logic.
    Side effects: None.
    Why: Prevents secrets from leaking into logs.
    """

    keys: tuple[str, ...]
    replacement: str


def normalize_redaction_keys(keys: Iterable[str]) -> tuple[str, ...]:
    """
    Purpose: Normalize redaction keys to lowercase for matching.
    Ties: Used by logging config parsing.
    Inputs: keys is an iterable of raw redaction key strings.
    Outputs: Tuple of lowercase keys with duplicates removed.
    Side effects: None.
    Why: Ensures consistent key matching across log payloads.
    """
    try:
        normalized = {key.strip().lower() for key in keys if key.strip()}
        return tuple(sorted(normalized))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{MODULE_PATH}:normalize_redaction_keys invalid keys: {exc}") from exc


def merge_json_dicts(left: Mapping[str, JsonValue], right: Mapping[str, JsonValue]) -> JsonDict:
    """
    Purpose: Merge two JSON compatible dicts with right side precedence.
    Ties: Used by config parsing when overlays are applied.
    Inputs: left is the base mapping, right overrides keys from left.
    Outputs: New merged dict with combined keys.
    Side effects: None.
    Why: Provides deterministic override behavior for config merges.
    """
    try:
        merged: JsonDict = dict(left)
        for key, value in right.items():
            merged[key] = value
        return merged
    except (AttributeError, TypeError) as exc:
        raise ValueError(f"{MODULE_PATH}:merge_json_dicts failed: {exc}") from exc
