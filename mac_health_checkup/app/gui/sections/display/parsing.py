from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.regex_utils import hz_from_text

MODULE_PATH = "mac_health_checkup/app/gui/sections/display/parsing.py"


def _parse_raw_display_rows(raw: str) -> list[tuple[str, str, str, str, str]]:
    """
    Summary
    Parse raw display output into normalized row tuples.

    Inputs
    raw: system_profiler SPDisplaysDataType output.

    Outputs
    List of tuples (name, resolution, mirror, connection, refresh).

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by the display section and tests.

    Why this exists
    Normalizes display output for consistent table rendering.
    """
    try:
        rows: list[tuple[str, str, str, str, str]] = []
        current = {"name": "", "resolution": "?", "mirror": "?", "connection": "?", "refresh": "?"}
        in_displays = False
        displays_indent: int | None = None
        name_indent: int | None = None
        skip_noise = {item.lower() for item in get_config().gui.skip_display_noise}
        for line in raw.splitlines():
            if line.strip().lower() in skip_noise:
                continue
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))

            if stripped.lower() == "displays:":
                in_displays = True
                displays_indent = indent
                name_indent = None
                continue

            if in_displays and displays_indent is not None and indent <= displays_indent and stripped:
                in_displays = False
                displays_indent = None
                name_indent = None

            if not in_displays or displays_indent is None:
                continue

            if stripped.endswith(":") and ":" not in stripped[:-1] and indent > displays_indent:
                # A display name line under the Displays: section.
                if current["name"]:
                    rows.append(
                        (
                            current["name"],
                            current["resolution"],
                            current["mirror"],
                            current["connection"],
                            current["refresh"],
                        )
                    )
                current = {
                    "name": stripped[:-1].strip(),
                    "resolution": "?",
                    "mirror": "?",
                    "connection": "?",
                    "refresh": "?",
                }
                name_indent = indent
                continue

            if not current["name"] or name_indent is None or indent <= name_indent:
                continue

            if ":" not in stripped:
                continue
            head, tail = stripped.split(":", 1)
            key = head.strip().lower()
            value = tail.strip()
            if not value:
                continue
            if key == "resolution":
                current["resolution"] = value
            elif key == "mirror":
                current["mirror"] = "Yes" if value.lower().startswith("on") else ""
            elif key == "connection type":
                current["connection"] = value
            elif key == "refresh rate":
                current["refresh"] = hz_from_text(value)

        if current["name"]:
            rows.append(
                (
                    current["name"],
                    current["resolution"],
                    current["mirror"],
                    current["connection"],
                    current["refresh"],
                )
            )
        if rows:
            return rows
        return _parse_raw_display_rows_legacy(raw)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_raw_display_rows", "Failed to parse display rows", exc)
        ) from exc


def _parse_raw_display_rows_legacy(raw: str) -> list[tuple[str, str, str, str, str]]:
    """
    Summary
    Fallback parser for older or simplified system_profiler output that lacks a Displays section.

    Inputs
    raw: Raw system_profiler text.

    Outputs
    Normalized display rows.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by `_parse_raw_display_rows` when the primary parser yields no rows.

    Why this exists
    Some macOS versions emit display blocks directly under Graphics/Displays without an explicit Displays header.
    """
    try:
        rows: list[tuple[str, str, str, str, str]] = []
        current = {"name": "", "resolution": "?", "mirror": "?", "connection": "?", "refresh": "?"}
        name_indent: int | None = None
        saw_resolution = False
        skip_noise = {item.lower() for item in get_config().gui.skip_display_noise}
        for line in raw.splitlines():
            if line.strip().lower() in skip_noise:
                continue
            stripped = line.strip()
            indent = len(line) - len(line.lstrip(" "))

            if stripped.endswith(":") and ":" not in stripped[:-1] and indent >= 4 and indent <= 8:
                if current["name"] and saw_resolution:
                    rows.append(
                        (
                            current["name"],
                            current["resolution"],
                            current["mirror"],
                            current["connection"],
                            current["refresh"],
                        )
                    )
                current = {
                    "name": stripped[:-1].strip(),
                    "resolution": "?",
                    "mirror": "?",
                    "connection": "?",
                    "refresh": "?",
                }
                name_indent = indent
                saw_resolution = False
                continue

            if not current["name"] or name_indent is None or indent <= name_indent:
                continue
            if ":" not in stripped:
                continue
            head, tail = stripped.split(":", 1)
            key = head.strip().lower()
            value = tail.strip()
            if not value:
                continue
            if key == "resolution":
                current["resolution"] = value
                saw_resolution = True
            elif key == "mirror":
                current["mirror"] = "Yes" if value.lower().startswith("on") else ""
            elif key == "connection type":
                current["connection"] = value
            elif key == "refresh rate":
                current["refresh"] = hz_from_text(value)

        if current["name"] and saw_resolution:
            rows.append(
                (
                    current["name"],
                    current["resolution"],
                    current["mirror"],
                    current["connection"],
                    current["refresh"],
                )
            )
        return rows
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_parse_raw_display_rows_legacy",
                "Failed to parse display rows (legacy mode)",
                exc,
            )
        ) from exc


def _parse_ioreg_display_rows(raw: str) -> list[tuple[str, str, str, str, str, str]]:
    """
    Summary
    Parse IORegistry display blocks into normalized row tuples.

    Inputs
    raw: `ioreg -lw0 -r -c IOMobileFramebufferShim` output.

    Outputs
    List of tuples (name, resolution, mirror, connection, refresh, transport).

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by the display section when system_profiler does not expose per-display inventory.

    Why this exists
    Newer macOS builds may omit display details from SPDisplaysDataType; IORegistry remains a reliable source.
    """
    try:
        blocks = _split_ioreg_blocks(raw, marker="IOMobileFramebufferShim")
        rows: list[tuple[str, str, str, str, str, str]] = []
        for block in blocks:
            width = _extract_ioreg_int(block, '"DisplayWidth" =')
            height = _extract_ioreg_int(block, '"DisplayHeight" =')
            if width is None or height is None:
                continue
            external = _extract_ioreg_yes_no(block, '"external" =')
            edid_uuid = _extract_ioreg_str(block, '"EDID UUID" =')
            name = "Built-in Display"
            connection = "Built-In"
            transport = "Internal"
            if external is True:
                connection = "External"
                transport = "External"
                if edid_uuid:
                    prefix = edid_uuid.split("-", 1)[0]
                    name = f"External Display {prefix}"
                else:
                    name = "External Display"
            refresh = _extract_refresh_hz_from_ioreg_block(block)
            resolution = f"{width} x {height}"
            rows.append((name, resolution, "", connection, refresh or "?", transport))
        rows.sort(key=lambda row: (0 if row[3] == "Built-In" else 1, row[0].lower()))
        return rows
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_ioreg_display_rows", "Failed to parse ioreg display rows", exc)
        ) from exc


def _split_ioreg_blocks(raw: str, *, marker: str) -> list[str]:
    """
    Summary
    Split ioreg output into per-object blocks by a marker string.

    Inputs
    raw: ioreg output.
    marker: Service class marker used to split objects.

    Outputs
    List of per-object block strings.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when splitting fails unexpectedly.

    Ties to other methods
    Used by ioreg parsing helpers.

    Why this exists
    ioreg output is a text tree; splitting enables deterministic parsing without external dependencies.
    """
    try:
        blocks: list[list[str]] = []
        current: list[str] = []
        for line in raw.splitlines():
            if marker in line and "+-o" in line:
                if current:
                    blocks.append(current)
                current = [line]
                continue
            if current:
                current.append(line)
        if current:
            blocks.append(current)
        return ["\n".join(lines) for lines in blocks]
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_split_ioreg_blocks", "Failed to split ioreg blocks", exc)
        ) from exc


def _extract_ioreg_int(block: str, needle: str) -> int | None:
    """
    Summary
    Extract an integer property from an ioreg block using a simple substring needle.

    Inputs
    block: Block string.
    needle: Needle prefix such as '"DisplayWidth" ='.

    Outputs
    Integer value or None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when extraction fails unexpectedly.

    Ties to other methods
    Used by `_parse_ioreg_display_rows`.

    Why this exists
    Avoids fragile full-grammar parsing of ioreg while remaining deterministic.
    """
    try:
        for line in block.splitlines():
            if needle in line:
                tail = line.split(needle, 1)[1].strip()
                try:
                    return int(tail)
                except ValueError:
                    return None
        return None
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_extract_ioreg_int", "Failed to parse ioreg int", exc)
        ) from exc


def _extract_ioreg_str(block: str, needle: str) -> str | None:
    """
    Summary
    Extract a quoted string property from an ioreg block.

    Inputs
    block: Block string.
    needle: Needle prefix such as '"EDID UUID" ='.

    Outputs
    String value or None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when extraction fails unexpectedly.

    Ties to other methods
    Used by `_parse_ioreg_display_rows`.

    Why this exists
    Provides a stable fallback identifier for external displays.
    """
    try:
        for line in block.splitlines():
            if needle in line:
                tail = line.split(needle, 1)[1].strip()
                if tail.startswith('"') and tail.endswith('"') and len(tail) >= 2:
                    return tail[1:-1]
                return tail
        return None
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_extract_ioreg_str", "Failed to parse ioreg string", exc)
        ) from exc


def _extract_ioreg_yes_no(block: str, needle: str) -> bool | None:
    """
    Summary
    Extract a Yes/No boolean property from an ioreg block.

    Inputs
    block: Block string.
    needle: Needle prefix such as '"external" ='.

    Outputs
    True, false, or None when missing.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when extraction fails unexpectedly.

    Ties to other methods
    Used by `_parse_ioreg_display_rows`.

    Why this exists
    ioreg represents booleans as Yes/No in text mode; this normalizes for logic.
    """
    try:
        for line in block.splitlines():
            if needle in line:
                tail = line.split(needle, 1)[1].strip().lower()
                if tail.startswith("yes"):
                    return True
                if tail.startswith("no"):
                    return False
                return None
        return None
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_extract_ioreg_yes_no", "Failed to parse ioreg bool", exc)
        ) from exc


def _extract_refresh_hz_from_ioreg_block(block: str) -> str | None:
    """
    Summary
    Extract a refresh rate string from an ioreg display block.

    Inputs
    block: Block string.

    Outputs
    Refresh string like "120 Hz" or None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when extraction fails unexpectedly.

    Ties to other methods
    Used by `_parse_ioreg_display_rows`.

    Why this exists
    ioreg timing elements encode refresh as fixed-point values; extracting it provides a useful UI column.
    """
    try:
        anchor = block.find('"PreferredTimingElements"')
        if anchor < 0:
            anchor = block.find('"TimingElements"')
        if anchor < 0:
            return None
        window = block[anchor : min(len(block), anchor + 6000)]
        idx = window.find('"VerticalAttributes"')
        if idx < 0:
            return None
        tail = window[idx : min(len(window), idx + 1500)]
        match = None
        for pattern in (r'"SyncRate"=(\d+)', r'"PreciseSyncRate"=(\d+)'):
            found = re.search(pattern, tail)
            if found:
                match = found
                break
        if not match:
            return None
        raw_value = int(match.group(1))
        hz = raw_value
        if raw_value > 1000:
            hz = int(round(raw_value / 65536.0))
        if hz <= 0:
            return None
        return f"{hz} Hz"
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH, "_extract_refresh_hz_from_ioreg_block", "Failed to parse refresh rate", exc
            )
        ) from exc
