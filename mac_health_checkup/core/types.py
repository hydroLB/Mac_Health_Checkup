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
    Summary
    Bundle headers and rows for table rendering.

    Inputs
    headers: Column labels.
    rows: Row tuples.

    Outputs
    Immutable container with headers and rows.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by GUI sections and tests to pass table data around.

    Why this exists
    Keeps table output strongly typed and explicit.
    """

    headers: tuple[str, ...]
    rows: list[tuple[str, ...]]


@dataclass(frozen=True)
class MetricsTable:
    """
    Summary
    Bundle metric table rows and column count.

    Inputs
    rows: (label, value, status) tuples.
    columns: Column count used by renderers.

    Outputs
    Immutable container for metrics data.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by metrics rendering in GUI sections.

    Why this exists
    Keeps metric output strongly typed and consistent.
    """

    rows: list[tuple[str, str, str]]
    columns: int


@dataclass(frozen=True)
class RedactionConfig:
    """
    Summary
    Carry redaction settings for structured logging.

    Inputs
    keys: Case-insensitive redaction keys.
    replacement: Replacement value string.

    Outputs
    Immutable config for redaction logic.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by loggers to protect secrets.

    Why this exists
    Prevents secrets from leaking into logs.
    """

    keys: tuple[str, ...]
    replacement: str


def normalize_redaction_keys(keys: Iterable[str]) -> tuple[str, ...]:
    """
    Summary
    Normalize redaction keys to lowercase for matching.

    Inputs
    keys: Iterable of raw redaction key strings.

    Outputs
    Tuple of lowercase keys with duplicates removed.

    Side effects
    None.

    Error handling
    Raises `ValueError` when input elements are malformed.

    Ties to other methods
    Used by logging config parsing.

    Why this exists
    Ensures consistent key matching across log payloads.
    """
    try:
        normalized = {key.strip().lower() for key in keys if key.strip()}
        return tuple(sorted(normalized))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{MODULE_PATH}:normalize_redaction_keys invalid keys: {exc}") from exc


def merge_json_dicts(left: Mapping[str, JsonValue], right: Mapping[str, JsonValue]) -> JsonDict:
    """
    Summary
    Merge two JSON compatible dicts with right-side precedence.

    Inputs
    left: Base mapping.
    right: Mapping whose keys override values from left.

    Outputs
    New merged dict with combined keys.

    Side effects
    None.

    Error handling
    Raises `ValueError` when inputs are malformed.

    Ties to other methods
    Used by config parsing when overlays are applied.

    Why this exists
    Provides deterministic override behavior for config merges.
    """
    try:
        merged: JsonDict = dict(left)
        for key, value in right.items():
            merged[key] = value
        return merged
    except (AttributeError, TypeError) as exc:
        raise ValueError(f"{MODULE_PATH}:merge_json_dicts failed: {exc}") from exc
