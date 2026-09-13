from __future__ import annotations

import copy
import ipaddress
import re
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath

from mac_health_checkup.app.backend import (
    Snapshot,
    SnapshotSection,
    SnapshotSectionDescriptor,
    SnapshotTable,
    SnapshotTheme,
)
from mac_health_checkup.core.types import JsonDict, JsonValue
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/reports/snapshot_redaction.py"

REDACTED_SERIAL = "[REDACTED: serial]"
REDACTED_SSID = "[REDACTED: SSID]"
REDACTED_IP = "[REDACTED: IP address]"
REDACTED_PID = "[REDACTED: PID]"
REDACTED_RAW_DIAGNOSTICS = "[REDACTED: raw diagnostics]"
REDACTED_PROCESS_PATH_PREFIX = "[REDACTED: process path]"

_IPV4_CANDIDATE_RE = re.compile(r"(?<![0-9A-Za-z_.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9A-Za-z_.])")
_IPV6_CANDIDATE_RE = re.compile(r"(?<![0-9A-Fa-f:])[0-9A-Fa-f:]*:[0-9A-Fa-f:]+(?![0-9A-Fa-f:])")
_NETWORK_FIELD_SEPARATOR = "  •  "


def redact_snapshot_sensitive(snapshot: Snapshot) -> Snapshot:
    """
    Summary
    Return a safe-share copy of a snapshot with known sensitive values redacted.

    Inputs
    snapshot: Source snapshot to copy and redact.

    Outputs
    A new `Snapshot` with serial numbers, SSIDs, IP addresses, process IDs, process command paths, and opaque raw
    diagnostics redacted.

    Side effects
    None. The source snapshot and all of its nested mutable collections remain unchanged.

    Error handling
    Raises `RuntimeError` with module and method context when a malformed snapshot cannot be copied or redacted.

    Ties to other methods
    Used by report export, diff export, and opt-in JSON snapshot output paths.

    Why this exists
    Snapshot payloads contain useful troubleshooting context but can also expose machine- and network-specific data
    that should not be copied into tickets or shared reports by default.
    """
    try:
        sections = [_redact_section(section) for section in snapshot.sections]
        return Snapshot(
            schema_version=snapshot.schema_version,
            generated_at_unix_ms=snapshot.generated_at_unix_ms,
            theme=_copy_theme(snapshot.theme),
            section_catalog=[
                SnapshotSectionDescriptor(title=item.title, subtitle=item.subtitle, key=item.key)
                for item in snapshot.section_catalog
            ],
            sections=sections,
            ok=snapshot.ok,
            error=_redact_ip_addresses(snapshot.error) if snapshot.error is not None else None,
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "redact_snapshot_sensitive",
                "Failed to redact sensitive snapshot values",
                exc,
            )
        ) from exc


def _copy_theme(theme: SnapshotTheme) -> SnapshotTheme:
    """
    Summary
    Deep-copy snapshot theme dictionaries.

    Inputs
    theme: Source snapshot theme.

    Outputs
    Independent `SnapshotTheme` copy.

    Side effects
    None.

    Error handling
    Propagates copy errors to `redact_snapshot_sensitive`.

    Ties to other methods
    Used by `redact_snapshot_sensitive` while constructing an independent snapshot object.

    Why this exists
    Although theme values are not redacted, copying them guarantees callers cannot mutate the source through the
    returned safe-share snapshot.
    """
    return SnapshotTheme(
        ui=copy.deepcopy(theme.ui),
        colors=copy.deepcopy(theme.colors),
        fonts=copy.deepcopy(theme.fonts),
        gui=copy.deepcopy(theme.gui),
    )


def _redact_section(section: SnapshotSection) -> SnapshotSection:
    """
    Summary
    Redact one snapshot section while preserving its render shape.

    Inputs
    section: Source section.

    Outputs
    New redacted `SnapshotSection`.

    Side effects
    None.

    Error handling
    Propagates normalization errors to `redact_snapshot_sensitive`.

    Ties to other methods
    Used for every section copied by `redact_snapshot_sensitive`.

    Why this exists
    Section fields, metrics, tables, and diagnostics need coordinated redaction because the same sensitive value may
    appear in several render surfaces.
    """
    diagnostics = _redact_diagnostics(section.diagnostics)
    return SnapshotSection(
        key=section.key,
        field=_redact_section_field(section),
        metrics=_redact_metrics(section.metrics),
        table=_redact_table(section.table),
        diagnostics=diagnostics,
    )


def _redact_section_field(section: SnapshotSection) -> str | None:
    """
    Summary
    Redact sensitive values embedded in a section summary field.

    Inputs
    section: Source snapshot section.

    Outputs
    Redacted field text or `None`.

    Side effects
    None.

    Error handling
    Propagates string normalization errors to `redact_snapshot_sensitive`.

    Ties to other methods
    Used by `_redact_section` for Markdown, HTML, diff, and JSON-safe output.

    Why this exists
    General and network summary fields flatten multiple values into prose, so key-based diagnostics redaction alone
    cannot protect them.
    """
    if section.field is None:
        return None

    field = _redact_ip_addresses(section.field)
    candidates = _sensitive_candidates(section)
    for kind, value in candidates:
        replacement = _replacement_for_kind(kind)
        if value:
            field = field.replace(value, replacement)

    if section.key == "general" and "|" in field:
        prefix, _separator, _serial = field.rpartition("|")
        field = f"{prefix.rstrip()} | {REDACTED_SERIAL}"

    if section.key == "network":
        parts = field.split(_NETWORK_FIELD_SEPARATOR)
        if len(parts) > 1 and parts[0].strip() in {"Wi-Fi", "Wi‑Fi"}:
            parts[1] = REDACTED_SSID
            field = _NETWORK_FIELD_SEPARATOR.join(parts)

    return field


def _sensitive_candidates(section: SnapshotSection) -> list[tuple[str, str]]:
    """
    Summary
    Collect known sensitive string values that may also be embedded in a summary field.

    Inputs
    section: Source snapshot section.

    Outputs
    Ordered `(kind, value)` pairs used for exact replacement.

    Side effects
    None.

    Error handling
    Ignores non-string and empty values rather than failing redaction.

    Ties to other methods
    Used by `_redact_section_field` before section-specific fallback parsing.

    Why this exists
    Reusing diagnostics and metric values avoids guessing which free-form text fragments represent SSIDs, serials,
    or addresses.
    """
    candidates: list[tuple[str, str]] = []
    if section.metrics:
        for label, value, _status in section.metrics:
            kind = _sensitive_kind(label)
            if kind is not None and value:
                candidates.append((kind, value))
    if section.diagnostics:
        for key, diagnostic_value in section.diagnostics.items():
            kind = _sensitive_kind(key)
            if kind is not None and isinstance(diagnostic_value, str) and diagnostic_value:
                candidates.append((kind, diagnostic_value))
    return candidates


def _redact_metrics(
    metrics: list[tuple[str, str, str]] | None,
) -> list[tuple[str, str, str]] | None:
    """
    Summary
    Redact sensitive metric values while retaining labels, statuses, and row order.

    Inputs
    metrics: Optional snapshot metrics rows.

    Outputs
    New metrics rows or `None`.

    Side effects
    None.

    Error handling
    Propagates malformed row errors to `redact_snapshot_sensitive`.

    Ties to other methods
    Used by `_redact_section`.

    Why this exists
    Network identifiers may be rendered as metrics even when diagnostics are omitted from reports.
    """
    if metrics is None:
        return None
    rows: list[tuple[str, str, str]] = []
    for label, value, status in metrics:
        kind = _sensitive_kind(label)
        redacted_value = _redact_typed_string(value, kind=kind)
        rows.append((label, redacted_value, status))
    return rows


def _redact_table(table: SnapshotTable | None) -> SnapshotTable | None:
    """
    Summary
    Redact sensitive table columns without changing table dimensions.

    Inputs
    table: Optional snapshot table.

    Outputs
    New `SnapshotTable` or `None`.

    Side effects
    None.

    Error handling
    Propagates malformed table errors to `redact_snapshot_sensitive`.

    Ties to other methods
    Used by `_redact_section` for process and future identifier-bearing tables.

    Why this exists
    Process IDs and command paths are exposed in table cells and need column-aware handling that keeps CPU and memory
    values useful.
    """
    if table is None:
        return None
    kinds = tuple(_sensitive_kind(header) for header in table.headers)
    rows: list[tuple[str, ...]] = []
    for row in table.rows:
        redacted_row = tuple(
            _redact_typed_string(value, kind=kinds[index] if index < len(kinds) else None)
            for index, value in enumerate(row)
        )
        rows.append(redacted_row)
    return SnapshotTable(headers=tuple(table.headers), rows=rows)


def _redact_diagnostics(diagnostics: JsonDict | None) -> JsonDict | None:
    """
    Summary
    Recursively redact sensitive diagnostics keys and opaque raw blobs.

    Inputs
    diagnostics: Optional section diagnostics mapping.

    Outputs
    Independent redacted diagnostics mapping or `None`.

    Side effects
    None.

    Error handling
    Propagates malformed JSON-compatible values to `redact_snapshot_sensitive`.

    Ties to other methods
    Used by `_redact_section` so opt-in diagnostics and JSON snapshots are safe to share.

    Why this exists
    Diagnostics contain nested collector payloads and raw command output that can repeat identifiers not visible in
    the report's normal fields and tables.
    """
    if diagnostics is None:
        return None
    return _redact_mapping(diagnostics)


def _redact_mapping(values: Mapping[str, JsonValue]) -> JsonDict:
    """
    Summary
    Redact a JSON-compatible mapping recursively.

    Inputs
    values: Diagnostics mapping.

    Outputs
    New redacted dictionary.

    Side effects
    None.

    Error handling
    Propagates unsupported value errors to `redact_snapshot_sensitive`.

    Ties to other methods
    Used by `_redact_diagnostics` and `_redact_json_value`.

    Why this exists
    Key-aware traversal protects structured diagnostics while preserving their shape for troubleshooting.
    """
    output: JsonDict = {}
    for key, value in values.items():
        normalized = _normalize_label(key)
        if "raw" in normalized.split():
            output[key] = _redact_nonempty(value, replacement=REDACTED_RAW_DIAGNOSTICS)
            continue
        kind = _sensitive_kind(key)
        if kind is not None:
            output[key] = _redact_typed_value(value, kind=kind)
            continue
        output[key] = _redact_json_value(value)
    return output


def _redact_json_value(value: JsonValue) -> JsonValue:
    """
    Summary
    Copy a JSON-compatible value while redacting embedded IP addresses.

    Inputs
    value: Arbitrary JSON-compatible diagnostics value.

    Outputs
    Independent JSON-compatible value.

    Side effects
    None.

    Error handling
    Raises `TypeError` when a value falls outside the declared JSON contract.

    Ties to other methods
    Used by `_redact_mapping` and recursively for nested lists.

    Why this exists
    Some collectors store addresses under generic keys such as `gateway`, so string-level address validation provides
    a safe fallback without redacting unrelated text.
    """
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_redact_json_value(item) for item in value]
    if isinstance(value, str):
        return _redact_ip_addresses(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise TypeError(f"unsupported diagnostics value: {type(value).__name__}")


def _redact_typed_value(value: JsonValue, *, kind: str) -> JsonValue:
    """
    Summary
    Redact a diagnostics value according to its sensitive key kind.

    Inputs
    value: JSON-compatible diagnostics value.
    kind: Normalized sensitive kind.

    Outputs
    Redacted JSON-compatible value.

    Side effects
    None.

    Error handling
    Propagates unsupported nested value errors to `redact_snapshot_sensitive`.

    Ties to other methods
    Used by `_redact_mapping` for serial, SSID, IP, PID, and command keys.

    Why this exists
    Structured diagnostics may encode PIDs as numbers and command paths as strings, so redaction must support more
    than a single string replacement rule.
    """
    if value is None or value == "":
        return value
    if kind == "command" and isinstance(value, str):
        return _redact_command_path(value)
    if isinstance(value, Sequence) and not isinstance(value, str):
        return [_redact_typed_value(item, kind=kind) for item in value]
    if isinstance(value, Mapping):
        return _redact_mapping(value)
    return _replacement_for_kind(kind)


def _redact_nonempty(value: JsonValue, *, replacement: str) -> JsonValue:
    """
    Summary
    Replace a non-empty diagnostics value with a fixed placeholder.

    Inputs
    value: JSON-compatible value.
    replacement: Deterministic replacement string.

    Outputs
    Original empty value or the replacement string.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `_redact_mapping` for opaque raw command output.

    Why this exists
    Empty raw output carries no sensitive data and can remain semantically empty, while populated blobs must never be
    copied into a safe-share artifact.
    """
    if value is None or value == "" or value == [] or value == {}:
        return value
    return replacement


def _redact_typed_string(value: str, *, kind: str | None) -> str:
    """
    Summary
    Redact a rendered string using an optional column or metric kind.

    Inputs
    value: Rendered snapshot string.
    kind: Optional normalized sensitive kind.

    Outputs
    Redacted string.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by metric and table redaction.

    Why this exists
    Render rows require exact placeholders for known sensitive columns plus validated IP detection in otherwise
    unclassified text.
    """
    if not value:
        return value
    if kind == "command":
        return _redact_command_path(value)
    if kind is not None:
        return _replacement_for_kind(kind)
    return _redact_ip_addresses(value)


def _redact_command_path(value: str) -> str:
    """
    Summary
    Remove directory components from a process command while retaining its executable name.

    Inputs
    value: Process command value.

    Outputs
    Original command name when no path is present, otherwise a redacted path prefix and executable basename.

    Side effects
    None.

    Error handling
    Falls back to a path-only placeholder when no basename can be resolved.

    Ties to other methods
    Used for process table command columns and nested diagnostics command keys.

    Why this exists
    Executable names remain useful for identifying resource-heavy processes, while directories can expose usernames,
    installed applications, and private workspace layouts.
    """
    stripped = value.strip()
    if "/" not in stripped and not stripped.startswith("~"):
        return _redact_ip_addresses(value)
    basename = PurePosixPath(stripped).name.strip()
    if not basename:
        return REDACTED_PROCESS_PATH_PREFIX
    return f"{REDACTED_PROCESS_PATH_PREFIX}/{_redact_ip_addresses(basename)}"


def _sensitive_kind(label: str) -> str | None:
    """
    Summary
    Classify a diagnostics key, metric label, or table header by sensitive value kind.

    Inputs
    label: Raw key or label.

    Outputs
    One of `serial`, `ssid`, `ip`, `pid`, `command`, or `None`.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used across field, metrics, table, and diagnostics redaction.

    Why this exists
    One normalized classifier keeps redaction consistent across snapshot surfaces with different naming conventions.
    """
    normalized = _normalize_label(label)
    tokens = set(normalized.split())
    if "serial" in tokens:
        return "serial"
    if "ssid" in tokens:
        return "ssid"
    if "ipv4" in tokens or "ipv6" in tokens or normalized in {"ip", "ip address", "internet address"}:
        return "ip"
    if "pid" in tokens or normalized == "process id":
        return "pid"
    if "command" in tokens or "executable" in tokens or normalized in {"process path", "command path"}:
        return "command"
    return None


def _normalize_label(label: str) -> str:
    """
    Summary
    Normalize a key or label for deterministic classifier matching.

    Inputs
    label: Raw key, metric label, or table header.

    Outputs
    Lowercase space-separated alphanumeric tokens.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `_sensitive_kind` and raw diagnostics detection.

    Why this exists
    Snapshot producers use spaces, underscores, and mixed case interchangeably for equivalent concepts.
    """
    return " ".join(re.findall(r"[a-z0-9]+", label.lower()))


def _replacement_for_kind(kind: str) -> str:
    """
    Summary
    Resolve the deterministic replacement string for a sensitive kind.

    Inputs
    kind: Sensitive classifier value.

    Outputs
    Replacement placeholder.

    Side effects
    None.

    Error handling
    Raises `ValueError` for unsupported kinds.

    Ties to other methods
    Used by field, metrics, table, and diagnostics redaction.

    Why this exists
    Centralizing placeholders keeps safe-share output predictable and easy to audit.
    """
    replacements = {
        "serial": REDACTED_SERIAL,
        "ssid": REDACTED_SSID,
        "ip": REDACTED_IP,
        "pid": REDACTED_PID,
        "command": REDACTED_PROCESS_PATH_PREFIX,
    }
    try:
        return replacements[kind]
    except KeyError as exc:
        raise ValueError(f"unsupported sensitive kind: {kind}") from exc


def _redact_ip_addresses(value: str) -> str:
    """
    Summary
    Replace validated IPv4 and IPv6 address substrings with a deterministic placeholder.

    Inputs
    value: Source text.

    Outputs
    Text with validated address candidates redacted.

    Side effects
    None.

    Error handling
    Invalid address-like substrings remain unchanged.

    Ties to other methods
    Used as a fallback across fields, metrics, tables, diagnostics, and top-level errors.

    Why this exists
    Addresses sometimes appear under generic keys or inside summary prose, and validation avoids confusing ordinary
    version numbers or timestamps with network identifiers.
    """

    def replace_candidate(match: re.Match[str]) -> str:
        """
        Summary
        Validate and redact one regex-selected address candidate.

        Inputs
        match: Candidate regex match.

        Outputs
        IP placeholder for a valid address or the original text.

        Side effects
        None.

        Error handling
        Treats `ValueError` from `ipaddress` as a non-address candidate.

        Ties to other methods
        Used as the replacement callback for IPv4 and IPv6 regex passes.

        Why this exists
        Regex locates candidates efficiently while the standard library provides authoritative address validation.
        """
        candidate = match.group(0)
        try:
            ipaddress.ip_address(candidate)
        except ValueError:
            return candidate
        return REDACTED_IP

    without_ipv4 = _IPV4_CANDIDATE_RE.sub(replace_candidate, value)
    return _IPV6_CANDIDATE_RE.sub(replace_candidate, without_ipv4)


__all__ = [
    "REDACTED_IP",
    "REDACTED_PID",
    "REDACTED_PROCESS_PATH_PREFIX",
    "REDACTED_RAW_DIAGNOSTICS",
    "REDACTED_SERIAL",
    "REDACTED_SSID",
    "redact_snapshot_sensitive",
]
