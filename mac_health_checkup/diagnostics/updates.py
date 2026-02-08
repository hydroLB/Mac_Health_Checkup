from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.shell import safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/updates.py"

_UPDATE_LINE_RE = re.compile(r"^\s*\*\s+(.+?)\s*$")


class SoftwareUpdateDiagnostics:
    """
    Summary
    Collect macOS software update posture using read-only `softwareupdate`.

    Inputs
    None.

    Outputs
    Dict with whether updates are available and a list of update labels.

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
                "raw": text,
                "error": err or "",
            }
        except Exception as exc:
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
    labels: list[str] = []
    for line in (text or "").splitlines():
        match = _UPDATE_LINE_RE.match(line)
        if not match:
            continue
        label = match.group(1).strip()
        if label:
            labels.append(label)
    # Preserve order but remove duplicates.
    seen: set[str] = set()
    unique: list[str] = []
    for item in labels:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique.append(item)
    return unique
