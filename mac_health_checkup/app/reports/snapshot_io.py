from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, cast

from mac_health_checkup.app.backend import (
    Snapshot,
    SnapshotSection,
    SnapshotSectionDescriptor,
    SnapshotTable,
    SnapshotTheme,
)
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict, JsonValue
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/reports/snapshot_io.py"


def load_snapshot_from_path(path: Path) -> Snapshot:
    """
    Summary
    Load a snapshot JSON file from disk into the typed `Snapshot` shape.

    Inputs
    path: Filesystem path to a snapshot JSON file produced by `--snapshot-json`.

    Outputs
    Parsed `Snapshot` instance.

    Side effects
    Reads from disk.

    Error handling
    Raises `RuntimeError` with module and method context when the file cannot be read or decoded.

    Ties to other methods
    Used by report export and diff workflows in the entrypoint.

    Why this exists
    Snapshot export and diff should not require re-running collectors; loading saved snapshots enables sharing and
    historical comparisons.
    """
    try:
        snapshot_path = path.expanduser()
        max_bytes = int(get_config().io.file_read_max_bytes)
        raw = _read_text_bounded(snapshot_path, max_bytes=max_bytes)
        payload_obj: object = json.loads(raw)
        if not isinstance(payload_obj, dict):
            raise ValueError("snapshot root must be object")
        payload = cast(Mapping[str, object], payload_obj)
        return _snapshot_from_mapping(payload)
    except (OSError, ValueError, TypeError, json.JSONDecodeError, RuntimeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "load_snapshot_from_path", f"Failed to load snapshot: {path}", exc)
        ) from exc


def _read_text_bounded(path: Path, *, max_bytes: int) -> str:
    """
    Summary
    Read a UTF-8 text file with a strict size limit.

    Inputs
    path: Path to read.
    max_bytes: Maximum allowed bytes.

    Outputs
    Decoded text content.

    Side effects
    Reads from disk.

    Error handling
    Raises `ValueError` when the file exceeds the limit. Raises `OSError` for IO failures.

    Ties to other methods
    Used by `load_snapshot_from_path` to prevent huge snapshot files from exhausting memory.

    Why this exists
    Snapshot files can contain raw diagnostic output; reads must be bounded.
    """
    if max_bytes < 1:
        raise ValueError("max_bytes must be >= 1")
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"file too large: bytes={size} max_bytes={max_bytes}")
    data = path.read_bytes()
    return data.decode("utf-8")


def _snapshot_from_mapping(raw: Mapping[str, object]) -> Snapshot:
    """
    Summary
    Convert a decoded snapshot mapping into a `Snapshot` instance with strict normalization.

    Inputs
    raw: Mapping decoded from JSON.

    Outputs
    Snapshot instance.

    Side effects
    None.

    Error handling
    Raises `ValueError` when required fields are missing or malformed.

    Ties to other methods
    Used by `load_snapshot_from_path`.

    Why this exists
    Reports should not trust arbitrary JSON; strict normalization prevents confusing partial failures.
    """
    schema_version = _require_int(raw.get("schema_version"), "schema_version")
    generated_at = _require_int(raw.get("generated_at_unix_ms"), "generated_at_unix_ms")
    ok = _require_bool(raw.get("ok"), "ok")
    error = _optional_str(raw.get("error"))

    theme_raw = raw.get("theme")
    theme = _theme_from_value(theme_raw)

    catalog_raw = raw.get("section_catalog")
    section_catalog = _catalog_from_value(catalog_raw)

    sections_raw = raw.get("sections")
    sections = _sections_from_value(sections_raw)

    return Snapshot(
        schema_version=schema_version,
        generated_at_unix_ms=generated_at,
        theme=theme,
        section_catalog=section_catalog,
        sections=sections,
        ok=ok,
        error=error,
    )


def _theme_from_value(value: object) -> SnapshotTheme:
    """
    Summary
    Parse the theme object from snapshot JSON.

    Inputs
    value: Raw JSON value.

    Outputs
    SnapshotTheme instance.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the theme is malformed.

    Ties to other methods
    Used by `_snapshot_from_mapping`.

    Why this exists
    Theme values influence HTML export styling and must be decoded deterministically.
    """
    if value is None:
        return SnapshotTheme(ui={}, colors={}, fonts={}, gui={})
    if not isinstance(value, dict):
        raise ValueError("theme must be object")
    ui = _require_json_dict(value.get("ui"), "theme.ui", allow_empty=True)
    colors = _require_json_dict(value.get("colors"), "theme.colors", allow_empty=True)
    fonts = _require_json_dict(value.get("fonts"), "theme.fonts", allow_empty=True)
    gui = _require_json_dict(value.get("gui"), "theme.gui", allow_empty=True)
    return SnapshotTheme(ui=ui, colors=colors, fonts=fonts, gui=gui)


def _catalog_from_value(value: object) -> list[SnapshotSectionDescriptor]:
    """
    Summary
    Parse the section catalog list from snapshot JSON.

    Inputs
    value: Raw JSON value.

    Outputs
    List of `SnapshotSectionDescriptor` entries.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the catalog is malformed.

    Ties to other methods
    Used by `_snapshot_from_mapping`.

    Why this exists
    Exporters use the catalog to display user-facing titles consistently across snapshots.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("section_catalog must be list")
    out: list[SnapshotSectionDescriptor] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("section_catalog items must be objects")
        title = _require_str(item.get("title"), "section_catalog.title")
        subtitle = _require_str(item.get("subtitle"), "section_catalog.subtitle")
        key = _require_str(item.get("key"), "section_catalog.key")
        out.append(SnapshotSectionDescriptor(title=title, subtitle=subtitle, key=key))
    return out


def _sections_from_value(value: object) -> list[SnapshotSection]:
    """
    Summary
    Parse the sections list from snapshot JSON.

    Inputs
    value: Raw JSON value.

    Outputs
    List of `SnapshotSection` entries.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the sections are malformed.

    Ties to other methods
    Used by `_snapshot_from_mapping`.

    Why this exists
    Sections are the primary content for report export and diffing.
    """
    if not isinstance(value, list):
        raise ValueError("sections must be list")
    out: list[SnapshotSection] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("sections items must be objects")
        key = _require_str(item.get("key"), "sections.key")
        field = _optional_str(item.get("field"))
        metrics = _optional_metrics(item.get("metrics"))
        table = _optional_table(item.get("table"))
        diagnostics = _optional_json_dict(item.get("diagnostics"))
        out.append(
            SnapshotSection(
                key=key,
                field=field,
                metrics=metrics,
                table=table,
                diagnostics=diagnostics,
            )
        )
    return out


def _optional_metrics(value: object) -> list[tuple[str, str, str]] | None:
    """
    Summary
    Parse optional metrics rows.

    Inputs
    value: Raw JSON value.

    Outputs
    List of (label, value, status) tuples or None.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the metrics are present but malformed.

    Ties to other methods
    Used by `_sections_from_value`.

    Why this exists
    Metrics are frequently shown in exports and diffs, and their shape must be normalized.
    """
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("metrics must be list")
    rows: list[tuple[str, str, str]] = []
    for item in value:
        if not isinstance(item, list) or len(item) != 3:
            raise ValueError("metrics rows must be 3-item lists")
        a, b, c = item
        if not isinstance(a, str) or not isinstance(b, str) or not isinstance(c, str):
            raise ValueError("metrics row items must be strings")
        rows.append((a, b, c))
    return rows


def _optional_table(value: object) -> SnapshotTable | None:
    """
    Summary
    Parse an optional table payload.

    Inputs
    value: Raw JSON value.

    Outputs
    SnapshotTable instance or None.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the table is present but malformed.

    Ties to other methods
    Used by `_sections_from_value`.

    Why this exists
    Exporters render tables and need stable headers/rows types.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("table must be object")
    headers_raw = value.get("headers")
    rows_raw = value.get("rows")
    if not isinstance(headers_raw, list) or not all(isinstance(h, str) for h in headers_raw):
        raise ValueError("table.headers must be list[str]")
    headers = tuple(str(h) for h in headers_raw)
    if not isinstance(rows_raw, list):
        raise ValueError("table.rows must be list")
    rows: list[tuple[str, ...]] = []
    for row in rows_raw:
        if not isinstance(row, list) or not all(isinstance(cell, str) for cell in row):
            raise ValueError("table row must be list[str]")
        rows.append(tuple(row))
    return SnapshotTable(headers=headers, rows=rows)


def _optional_json_dict(value: object) -> JsonDict | None:
    """
    Summary
    Parse an optional JSON dict value.

    Inputs
    value: Raw JSON value.

    Outputs
    Dict or None.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the value is present but not a dict.

    Ties to other methods
    Used by `_sections_from_value`.

    Why this exists
    Diagnostics content is optional and should remain JSON-safe when included.
    """
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("diagnostics must be object")
    return _coerce_json_dict(value)


def _require_json_dict(value: object, name: str, *, allow_empty: bool) -> JsonDict:
    """
    Summary
    Require a JSON dict value for theme sections.

    Inputs
    value: Raw JSON value.
    name: Field name for error messages.
    allow_empty: Whether empty dict is allowed.

    Outputs
    JSON dict.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the value is invalid.

    Ties to other methods
    Used by `_theme_from_value`.

    Why this exists
    Keeps theme parsing strict while allowing minimal snapshots without styling details.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be object")
    out = _coerce_json_dict(value)
    if not allow_empty and not out:
        raise ValueError(f"{name} must be non-empty")
    return out


def _require_int(value: object, name: str) -> int:
    """
    Summary
    Execute `_require_int` for its module-level responsibility.

    Inputs
    value: `object` parameter from the function signature.
    name: `str` parameter from the function signature.

    Outputs
    Returns `int`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/reports/snapshot_io.py:_require_int` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/reports/snapshot_io.py`.

    Why this exists
    Keeps `_require_int` explicit, testable, and maintainable.
    """
    if not isinstance(value, int):
        raise ValueError(f"{name} must be int")
    return int(value)


def _require_bool(value: object, name: str) -> bool:
    """
    Summary
    Execute `_require_bool` for its module-level responsibility.

    Inputs
    value: `object` parameter from the function signature.
    name: `str` parameter from the function signature.

    Outputs
    Returns `bool`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/reports/snapshot_io.py:_require_bool` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/reports/snapshot_io.py`.

    Why this exists
    Keeps `_require_bool` explicit, testable, and maintainable.
    """
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be bool")
    return bool(value)


def _require_str(value: object, name: str) -> str:
    """
    Summary
    Execute `_require_str` for its module-level responsibility.

    Inputs
    value: `object` parameter from the function signature.
    name: `str` parameter from the function signature.

    Outputs
    Returns `str`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/reports/snapshot_io.py:_require_str` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/reports/snapshot_io.py`.

    Why this exists
    Keeps `_require_str` explicit, testable, and maintainable.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty string")
    return value


def _optional_str(value: object) -> str | None:
    """
    Summary
    Execute `_optional_str` for its module-level responsibility.

    Inputs
    value: `object` parameter from the function signature.

    Outputs
    Returns `str | None`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/reports/snapshot_io.py:_optional_str` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/reports/snapshot_io.py`.

    Why this exists
    Keeps `_optional_str` explicit, testable, and maintainable.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    return value


def _coerce_json_dict(value: Mapping[object, object]) -> JsonDict:
    """
    Summary
    Coerce an arbitrary mapping into a `JsonDict` by validating JSON-compatible nested values.

    Inputs
    value: Mapping with string keys and JSON-compatible values.

    Outputs
    `JsonDict` containing validated `JsonValue` entries.

    Side effects
    None.

    Error handling
    Raises `ValueError` when keys or values are not JSON compatible.

    Ties to other methods
    Used by snapshot loading to decode theme and diagnostics dicts safely.

    Why this exists
    Report export should never accept arbitrary Python objects from untrusted JSON.
    """
    out: JsonDict = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("json dict keys must be strings")
        out[key] = _coerce_json_value(item)
    return out


def _coerce_json_value(value: object) -> JsonValue:
    """
    Summary
    Execute `_coerce_json_value` for its module-level responsibility.

    Inputs
    value: `object` parameter from the function signature.

    Outputs
    Returns `JsonValue`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/reports/snapshot_io.py:_coerce_json_value` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/reports/snapshot_io.py`.

    Why this exists
    Keeps `_coerce_json_value` explicit, testable, and maintainable.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return _coerce_json_dict(value)
    if isinstance(value, list):
        return [_coerce_json_value(item) for item in value]
    raise ValueError(f"invalid json value type: {type(value).__name__}")
