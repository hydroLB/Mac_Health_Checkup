from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.shell import safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/security.py"

_BOOL_STATUS_RE = re.compile(r"\b(enabled|disabled|on|off)\b", re.IGNORECASE)


class SecurityPostureDiagnostics:
    """
    Summary
    Collect high-signal macOS security posture flags (read-only).

    Inputs
    None.

    Outputs
    Dict containing FileVault, SIP, Gatekeeper, and firewall state.

    Side effects
    Executes system commands (`fdesetup`, `csrutil`, `spctl`, `defaults`).

    Error handling
    Returns `ok=false` with an `error` string when collection fails unexpectedly.

    Ties to other methods
    Used by the Security section (`mac_health_checkup/app/gui/sections/security.py`).

    Why this exists
    Security posture is a common root cause for device management and troubleshooting issues. Surfacing these
    flags in one place makes health checks actionable while remaining read-only.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch security posture flags with caching.

        Inputs
        None.

        Outputs
        Diagnostics dict with per-signal statuses and raw outputs.

        Side effects
        Executes bounded system commands when cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching logic fails unexpectedly.

        Ties to other methods
        Used by the Security section refresh cycle.

        Why this exists
        Avoids repeatedly executing security posture commands on short UI refresh intervals.
        """
        try:
            return cached_fetch(
                SecurityPostureDiagnostics._cache,
                "security_posture",
                SecurityPostureDiagnostics._fetch_uncached,
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "SecurityPostureDiagnostics.fetch", "Failed to fetch security posture", exc
                )
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch security posture flags without caching.

        Inputs
        None.

        Outputs
        Diagnostics dict.

        Side effects
        Executes system commands.

        Error handling
        Never raises for missing tools; returns partial results with `ok=true` when some signals are available.

        Ties to other methods
        Wrapped by `fetch` via `cached_fetch`.

        Why this exists
        Some tools may be missing or restricted; partial visibility is still valuable.
        """
        logger = get_diagnostics_logger()
        context = new_context("SecurityPostureDiagnostics")
        try:
            timeout = int(get_config().timeouts.default_cmd_timeout)

            fv_out, fv_err = safe_run(
                ["fdesetup", "status"], context="filevault", allow_sudo=False, timeout=timeout
            )
            filevault = _parse_filevault_status(fv_out or "")

            sip_out, sip_err = safe_run(
                ["csrutil", "status"], context="sip", allow_sudo=False, timeout=timeout
            )
            sip = _parse_sip_status(sip_out or "")

            gk_out, gk_err = safe_run(
                ["spctl", "--status"], context="gatekeeper", allow_sudo=False, timeout=timeout
            )
            gatekeeper = _parse_gatekeeper_status(gk_out or "")

            fw_out, fw_err = safe_run(
                ["defaults", "read", "/Library/Preferences/com.apple.alf", "globalstate"],
                context="firewall",
                allow_sudo=False,
                timeout=timeout,
            )
            firewall = _parse_firewall_globalstate(fw_out or "")

            ok_any = any(
                item.get("enabled") is not None
                for item in (filevault, sip, gatekeeper, firewall)
                if isinstance(item, dict)
            )
            if not ok_any:
                logger.warning(
                    "security posture unavailable",
                    event="security_unavailable",
                    context=context,
                    payload={
                        "filevault_error": fv_err or "",
                        "sip_error": sip_err or "",
                        "gatekeeper_error": gk_err or "",
                        "firewall_error": fw_err or "",
                    },
                )
            return {
                "ok": ok_any,
                "filevault": {**filevault, "raw": fv_out or "", "error": fv_err or ""},
                "sip": {**sip, "raw": sip_out or "", "error": sip_err or ""},
                "gatekeeper": {**gatekeeper, "raw": gk_out or "", "error": gk_err or ""},
                "firewall": {**firewall, "raw": fw_out or "", "error": fw_err or ""},
            }
        except Exception as exc:
            logger.warning(
                "security posture collection failed",
                event="security_error",
                context=context,
                payload={"error": str(exc), "error_type": type(exc).__name__},
            )
            return {
                "ok": False,
                "error": format_error(
                    MODULE_PATH,
                    "SecurityPostureDiagnostics._fetch_uncached",
                    "Failed to collect security posture",
                    exc,
                ),
            }


def _parse_filevault_status(text: str) -> JsonDict:
    """
    Summary
    Parse `fdesetup status` output into a normalized enabled/disabled flag.

    Inputs
    text: Command output.

    Outputs
    Dict with `enabled` bool or None and `status` string.

    Side effects
    None.

    Error handling
    Never raises; returns unknown values on malformed input.

    Ties to other methods
    Used by `SecurityPostureDiagnostics._fetch_uncached`.

    Why this exists
    Output phrasing varies slightly across macOS versions; parsing should be robust.
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return {"enabled": None, "status": "unknown"}
    if "filevault is on" in lowered:
        return {"enabled": True, "status": "on"}
    if "filevault is off" in lowered:
        return {"enabled": False, "status": "off"}
    match = _BOOL_STATUS_RE.search(lowered)
    if match:
        word = match.group(1).lower()
        if word in {"on", "enabled"}:
            return {"enabled": True, "status": word}
        if word in {"off", "disabled"}:
            return {"enabled": False, "status": word}
    return {"enabled": None, "status": "unknown"}


def _parse_sip_status(text: str) -> JsonDict:
    """
    Summary
    Parse `csrutil status` output into a normalized enabled/disabled flag.

    Inputs
    text: Command output.

    Outputs
    Dict with `enabled` bool or None and `status` string.

    Side effects
    None.

    Error handling
    Never raises; returns unknown values on malformed input.

    Ties to other methods
    Used by `SecurityPostureDiagnostics._fetch_uncached`.

    Why this exists
    SIP impacts many diagnostics tools and is often a key troubleshooting dimension.
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return {"enabled": None, "status": "unknown"}
    if "status: enabled" in lowered:
        return {"enabled": True, "status": "enabled"}
    if "status: disabled" in lowered:
        return {"enabled": False, "status": "disabled"}
    match = _BOOL_STATUS_RE.search(lowered)
    if match:
        word = match.group(1).lower()
        if word in {"on", "enabled"}:
            return {"enabled": True, "status": word}
        if word in {"off", "disabled"}:
            return {"enabled": False, "status": word}
    return {"enabled": None, "status": "unknown"}


def _parse_gatekeeper_status(text: str) -> JsonDict:
    """
    Summary
    Parse `spctl --status` output into a normalized enabled/disabled flag.

    Inputs
    text: Command output.

    Outputs
    Dict with `enabled` bool or None and `status` string.

    Side effects
    None.

    Error handling
    Never raises; returns unknown values on malformed input.

    Ties to other methods
    Used by `SecurityPostureDiagnostics._fetch_uncached`.

    Why this exists
    Gatekeeper provides a baseline protection against unsigned apps; it is a high-signal posture flag.
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return {"enabled": None, "status": "unknown"}
    if "assessments enabled" in lowered:
        return {"enabled": True, "status": "enabled"}
    if "assessments disabled" in lowered:
        return {"enabled": False, "status": "disabled"}
    match = _BOOL_STATUS_RE.search(lowered)
    if match:
        word = match.group(1).lower()
        if word in {"on", "enabled"}:
            return {"enabled": True, "status": word}
        if word in {"off", "disabled"}:
            return {"enabled": False, "status": word}
    return {"enabled": None, "status": "unknown"}


def _parse_firewall_globalstate(text: str) -> JsonDict:
    """
    Summary
    Parse firewall globalstate value from `defaults read` output.

    Inputs
    text: Command output expected to contain an integer state.

    Outputs
    Dict with `enabled` bool or None and `state` int or None.

    Side effects
    None.

    Error handling
    Never raises; returns unknown values on malformed input.

    Ties to other methods
    Used by `SecurityPostureDiagnostics._fetch_uncached`.

    Why this exists
    The firewall globalstate is a stable numeric signal and is easy to read without privileges.
    """
    lowered = (text or "").strip().lower()
    if not lowered:
        return {"enabled": None, "state": None}
    try:
        state = int(lowered.splitlines()[0].strip())
    except ValueError:
        return {"enabled": None, "state": None}
    # Known meanings: 0=off, 1=on for specific services, 2=on for essential services.
    enabled = state != 0
    return {"enabled": enabled, "state": state}
