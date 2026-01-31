from __future__ import annotations

import time

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.shell import run_with_admin_prompt
from mac_health_checkup.diagnostics.thermals.executables import resolve_executable
from mac_health_checkup.diagnostics.thermals.parsing import (
    _istats_output_indicates_permission_error,
    _parse_istats_scan_text,
    _parse_temperature_lines,
)

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/authorization.py"

_ADMIN_PROMPT_MIN_INTERVAL_SEC = 90.0
_ADMIN_PROMPT_SESSION_TTL_SEC = 600.0

_next_admin_prompt_allowed_at = 0.0
_admin_prompt_enabled_until = 0.0


def admin_prompt_gate(*, force: bool, now: float | None = None) -> tuple[bool, int]:
    """
    Summary
    Determine whether it is permissible to show an admin prompt now.

    Inputs
    force: When true, ignore backoff and allow.
    now: Optional monotonic timestamp used for determinism in tests.

    Outputs
    Tuple `(allowed, retry_after_seconds)`.

    Side effects
    None.

    Error handling
    Never raises; returns a conservative deny on any failure.

    Ties to other methods
    Used by `authorize_temperature_sensors` and background thermals collection to avoid repeated prompts.

    Why this exists
    Prevents rapid prompt spam and makes prompt behavior deterministic for UI refresh loops.
    """
    try:
        current = time.monotonic() if now is None else float(now)
        if force:
            return True, 0
        if current < _next_admin_prompt_allowed_at:
            retry_after = int(max(1.0, _next_admin_prompt_allowed_at - current))
            return False, retry_after
        return True, 0
    except Exception:
        return False, 1


def record_admin_prompt_failure(*, now: float | None = None) -> None:
    """
    Summary
    Apply a short backoff after an admin prompt attempt fails.

    Inputs
    now: Optional monotonic timestamp.

    Outputs
    None.

    Side effects
    Updates in-memory backoff state.

    Error handling
    Never raises; failures are absorbed by design.

    Ties to other methods
    Called by `authorize_temperature_sensors` and `ThermalSensorsDiagnostics` when osascript-based prompting fails.

    Why this exists
    Avoids repeated prompt attempts producing a poor UX and excessive logs.
    """
    try:
        global _next_admin_prompt_allowed_at
        current = time.monotonic() if now is None else float(now)
        _next_admin_prompt_allowed_at = current + _ADMIN_PROMPT_MIN_INTERVAL_SEC
    except Exception:
        return


def enable_admin_prompt_session(*, now: float | None = None) -> None:
    """
    Summary
    Enable a short-lived session during which background refresh may retry privileged sensor commands.

    Inputs
    now: Optional monotonic timestamp.

    Outputs
    None.

    Side effects
    Updates in-memory session state.

    Error handling
    Never raises; failures are absorbed by design.

    Ties to other methods
    Called by `authorize_temperature_sensors` on success and consulted by `ThermalSensorsDiagnostics`.

    Why this exists
    Prevents surprise prompts on startup while still allowing refresh to reuse cached authorization after a user-driven grant.
    """
    try:
        global _admin_prompt_enabled_until
        current = time.monotonic() if now is None else float(now)
        _admin_prompt_enabled_until = current + _ADMIN_PROMPT_SESSION_TTL_SEC
    except Exception:
        return


def admin_prompt_session_active(*, now: float | None = None) -> bool:
    """
    Summary
    Determine whether privileged prompting is currently allowed for background refresh.

    Inputs
    now: Optional monotonic timestamp.

    Outputs
    True when the prompt session is active.

    Side effects
    None.

    Error handling
    Never raises; returns false on any failure.

    Ties to other methods
    Used by `ThermalSensorsDiagnostics` to decide whether to attempt privileged probes without direct user interaction.

    Why this exists
    Keeps privileged prompting opt-in and bounded in time.
    """
    try:
        current = time.monotonic() if now is None else float(now)
        return current < _admin_prompt_enabled_until
    except Exception:
        return False


def authorize_temperature_sensors(*, force: bool) -> JsonDict:
    """
    Summary
    Attempt to authorize temperature sensor access via the macOS admin prompt.

    Inputs
    force: When true, ignore backoff and always attempt the prompt.

    Outputs
    JSON dict with ok, sensors_found, and error details.

    Side effects
    May display a macOS admin password prompt and updates in-memory prompt session state.

    Error handling
    Returns `ok=false` with an actionable error string when authorization fails or is cancelled.

    Ties to other methods
    Called by the agent API endpoint `/v1/authorize/thermals` and influences `ThermalSensorsDiagnostics` prompt behavior.

    Why this exists
    Provides an explicit user-driven way to request privileged access without relying on background refresh timing.
    """
    try:
        allowed, retry_after = admin_prompt_gate(force=force)
        if not allowed:
            return {
                "ok": False,
                "sensors_found": 0,
                "error": "rate_limited",
                "retry_after_sec": retry_after,
                "guidance": "Please wait a moment before requesting access again.",
            }

        powermetrics_path = resolve_executable("powermetrics") or "/usr/bin/powermetrics"
        out, err = run_with_admin_prompt(
            [powermetrics_path, "-n", "1", "--show-all"],
            context="authorize_powermetrics",
            timeout=max(8, get_config().timeouts.powermetrics_timeout),
        )
        combined = "\n\n".join([part for part in [out or "", err or ""] if part.strip()]).strip()
        if err and not err.startswith("command_failed"):
            record_admin_prompt_failure()
            lowered = err.lower()
            if "user canceled" in lowered or "user cancelled" in lowered or "-128" in lowered:
                return {
                    "ok": False,
                    "sensors_found": 0,
                    "error": "cancelled",
                    "guidance": "Authorization was cancelled. Click Request Access Now again when ready.",
                    "raw": combined,
                }
            if (
                "not correct" in lowered
                or "incorrect" in lowered
                or ("password" in lowered and "incorrect" in lowered)
                or ("passphrase" in lowered and "not correct" in lowered)
                or "-60007" in lowered
            ):
                return {
                    "ok": False,
                    "sensors_found": 0,
                    "error": "incorrect_password",
                    "guidance": "The macOS password was not accepted. Enter your Mac login password (not Apple ID) and try again.",
                    "raw": combined,
                }
            if "-1743" in lowered or "not authorised" in lowered or "not authorized" in lowered:
                return {
                    "ok": False,
                    "sensors_found": 0,
                    "error": "automation_denied",
                    "guidance": (
                        "macOS blocked the authorization request. "
                        "Go to System Settings → Privacy & Security and allow Automation/Permissions for this app, then try again."
                    ),
                    "raw": combined,
                }
            return {
                "ok": False,
                "sensors_found": 0,
                "error": "admin_prompt_failed",
                "guidance": (
                    "Authorization failed. If the prompt flashes and closes, try again and enter your Mac login password. "
                    "If you keep seeing failures, open Error Details to see the exact osascript message."
                ),
                "raw": combined,
            }

        if not out:
            istats_path = resolve_executable("istats")
            if istats_path is None:
                return {
                    "ok": False,
                    "sensors_found": 0,
                    "error": "no_output",
                    "guidance": (
                        "Authorization ran, but no output was returned from the sensor probe. "
                        "Install iStats for additional sensors and try again."
                    ),
                    "raw": combined,
                }
        sensors = _parse_temperature_lines(out or "")
        if not sensors:
            istats_path = resolve_executable("istats")
            if istats_path is None:
                return {
                    "ok": False,
                    "sensors_found": 0,
                    "error": "no_sensors",
                    "guidance": (
                        "Authorization completed, but no temperature sensors were detected from powermetrics. "
                        "Install iStats for additional sensors and try again."
                    ),
                    "raw": combined,
                }
            istats_out, istats_err = run_with_admin_prompt(
                [istats_path, "scan", "--no-graphs", "--no-scale"],
                context="authorize_istats_scan",
                timeout=max(8, get_config().timeouts.istats_timeout),
            )
            istats_combined = "\n\n".join(
                [part for part in [istats_out or "", istats_err or ""] if part.strip()]
            ).strip()
            if istats_err:
                record_admin_prompt_failure()
                return {
                    "ok": False,
                    "sensors_found": 0,
                    "error": "istats_failed",
                    "guidance": (
                        "Authorization succeeded, but iStats did not return sensors. "
                        "Open Error Details to see the raw output."
                    ),
                    "raw": istats_combined,
                }
            if istats_out and not _istats_output_indicates_permission_error(istats_out):
                sensors = _parse_istats_scan_text(istats_out)
            combined = "\n\n".join([chunk for chunk in [combined, istats_combined] if chunk.strip()])

        if not sensors:
            return {
                "ok": False,
                "sensors_found": 0,
                "error": "no_sensors",
                "guidance": (
                    "Authorization completed, but temperature sensors are still not available. "
                    "On some macOS builds this requires a signed privileged helper like Mac Fan Control uses. "
                    "Open Error Details to see exactly which tool failed."
                ),
                "raw": combined,
            }

        enable_admin_prompt_session()
        return {
            "ok": True,
            "sensors_found": len(sensors),
            "guidance": "Authorization successful. Temperature sensors should now populate in the dashboard.",
        }
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        return {
            "ok": False,
            "sensors_found": 0,
            "error": format_error(MODULE_PATH, "authorize_temperature_sensors", "Authorization failed", exc),
        }
