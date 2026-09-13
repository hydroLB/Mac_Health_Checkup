from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error, safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/updates.py"

_UPDATE_LINE_RE = re.compile(r"^\s*\*\s+(.+?)\s*$")
_LABEL_PREFIX_RE = re.compile(r"^label:\s*(.+)$", re.IGNORECASE)
_SIZE_FIELD_RE = re.compile(
    r"\bsize:\s*([0-9][0-9,]*(?:\.[0-9]+)?\s*(?:[kmgtp]?i?b|[kmgtp]?b|k))\b",
    re.IGNORECASE,
)
_LEGACY_SIZE_RE = re.compile(
    r"(?:^|,\s*)([0-9][0-9,]*(?:\.[0-9]+)?\s*(?:[kmgtp]?i?b|[kmgtp]?b|k))(?:\s|$|\[)",
    re.IGNORECASE,
)


class SoftwareUpdateDiagnostics:
    """
    Summary
    Collect macOS software update posture using read-only `softwareupdate`.

    Inputs
    None.

    Outputs
    Dict with whether updates are available, update labels, and parsed update entries with optional sizes.

    Side effects
    Executes `softwareupdate --list`.

    Error handling
    Returns `ok=false` when the tool is unavailable or the output cannot be parsed.

    Ties to other methods
    Used by the Updates section (`mac_health_checkup/app/gui/sections/updates.py`).

    Why this exists
    Update posture is a key security and stability signal, but update checks can be slow. This collector is cached
    with a long TTL to keep the UI responsive.
    """

    _cache = Cache(get_config().timeouts.softwareupdate_cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch software update posture with caching.

        Inputs
        None.

        Outputs
        Diagnostics dict.

        Side effects
        Executes `softwareupdate` when cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by the Updates section refresh loop.

        Why this exists
        Update checks can take seconds to minutes; caching prevents slow UI refresh loops.
        """
        try:
            return cached_fetch(
                SoftwareUpdateDiagnostics._cache, "softwareupdate", SoftwareUpdateDiagnostics._fetch_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SoftwareUpdateDiagnostics.fetch", "Failed to fetch updates", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch software update posture without caching.

        Inputs
        None.

        Outputs
        Diagnostics dict.

        Side effects
        Executes `softwareupdate --list`.

        Error handling
        Never raises for command failures; returns `ok=false` with error details.

        Ties to other methods
        Wrapped by `fetch` via `cached_fetch`.

        Why this exists
        `softwareupdate` output varies by macOS version; failures should be captured as guidance.
        """
        logger = get_diagnostics_logger()
        context = new_context("SoftwareUpdateDiagnostics")
        try:
            timeout = int(get_config().timeouts.softwareupdate_timeout)
            out, err = safe_run(
                ["softwareupdate", "--list"],
                context="softwareupdate_list",
                allow_sudo=False,
                timeout=timeout,
            )
            text = out or ""
            update_items = _parse_update_items(text)
            labels = _parse_update_labels(text)
            no_updates = "no new software available" in text.lower()
            available = bool(labels) or (not no_updates and bool(text.strip()))
            ok = bool(text.strip()) or bool(err)
            if not ok:
                logger.info(
                    "softwareupdate returned no output",
                    event="updates_empty",
                    context=context,
                    payload={"error": err or ""},
                )
            return {
                "ok": ok,
                "updates_available": available if ok else None,
                "update_labels": labels,
                "update_items": update_items,
                "raw": text,
                "error": err or "",
            }
        except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError) as exc:
            logger.warning(
                "softwareupdate failed",
                event="updates_error",
                context=context,
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            return {
                "ok": False,
                "error": format_error(
                    MODULE_PATH,
                    "SoftwareUpdateDiagnostics._fetch_uncached",
                    "Failed to collect software update posture",
                    exc,
                ),
            }


def _parse_update_labels(text: str) -> list[str]:
    """
    Summary
    Parse update labels from `softwareupdate --list` output.

    Inputs
    text: Raw command output.

    Outputs
    List of update label strings (may be empty).

    Side effects
    None.

    Error handling
    Never raises; returns an empty list on malformed input.

    Ties to other methods
    Used by `SoftwareUpdateDiagnostics._fetch_uncached`.

    Why this exists
    Update output is unstructured and contains extra guidance lines; labels are the most useful shareable summary.
    """
    return [
        str(item.get("label", "")).strip()
        for item in _parse_update_items(text)
        if str(item.get("label", "")).strip()
    ]


def _parse_update_items(text: str) -> list[JsonDict]:
    """
    Summary
    Parse update labels and optional package sizes from `softwareupdate --list` output.

    Inputs
    text: Raw command output.

    Outputs
    List of update entries with `label` and optional `size`.

    Side effects
    None.

    Error handling
    Never raises; returns an empty list on malformed input.

    Ties to other methods
    Used by `_parse_update_labels` and `SoftwareUpdateDiagnostics._fetch_uncached`.

    Why this exists
    Users need concrete package-level update information, including size when available.
    """
    parsed_items: list[tuple[str, str]] = []
    current_label = ""
    current_size = ""

    for raw_line in (text or "").splitlines():
        match = _UPDATE_LINE_RE.match(raw_line)
        if match:
            if current_label:
                parsed_items.append((current_label, current_size))
            current_label = _normalize_update_label(match.group(1))
            current_size = _extract_size_value(match.group(1)) or ""
            continue

        if not current_label:
            continue

        discovered_size = _extract_size_value(raw_line)
        if discovered_size:
            current_size = discovered_size

    if current_label:
        parsed_items.append((current_label, current_size))

    deduped: list[JsonDict] = []
    seen: dict[str, int] = {}
    for label, size in parsed_items:
        normalized_label = label.strip()
        if not normalized_label:
            continue
        key = normalized_label.lower()
        if key in seen:
            existing_index = seen[key]
            existing_size = str(deduped[existing_index].get("size", "")).strip()
            if (not existing_size) and size.strip():
                deduped[existing_index]["size"] = size.strip()
            continue
        seen[key] = len(deduped)
        entry: JsonDict = {"label": normalized_label}
        if size.strip():
            entry["size"] = size.strip()
        deduped.append(entry)
    return deduped


def _normalize_update_label(value: str) -> str:
    """
    Summary
    Normalize a raw update label by removing common output prefixes.

    Inputs
    value: Raw label text from a bullet line.

    Outputs
    Normalized label string.

    Side effects
    None.

    Error handling
    Never raises; returns an empty string for malformed input.

    Ties to other methods
    Used by `_parse_update_items`.

    Why this exists
    Modern `softwareupdate` output prefixes labels with `Label:`, while older output does not.
    """
    raw = (value or "").strip()
    if not raw:
        return ""
    match = _LABEL_PREFIX_RE.match(raw)
    if match:
        return match.group(1).strip()
    return raw


def _extract_size_value(value: str) -> str | None:
    """
    Summary
    Extract a package size token from a raw output line.

    Inputs
    value: Raw line text from `softwareupdate --list`.

    Outputs
    Size token string when found, otherwise `None`.

    Side effects
    None.

    Error handling
    Never raises; returns `None` when no size token is present.

    Ties to other methods
    Used by `_parse_update_items`.

    Why this exists
    `softwareupdate` has at least two common formats for size output and both should parse.
    """
    text = (value or "").strip()
    if not text:
        return None

    modern_match = _SIZE_FIELD_RE.search(text)
    if modern_match:
        return re.sub(r"\s+", "", modern_match.group(1))

    legacy_match = _LEGACY_SIZE_RE.search(text)
    if legacy_match:
        return re.sub(r"\s+", "", legacy_match.group(1))

    return None
