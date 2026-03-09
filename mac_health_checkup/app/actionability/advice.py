from __future__ import annotations

from typing import Literal, Mapping, Sequence, cast

from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/actionability/advice.py"

AdviceSeverity = Literal["ok", "warn", "bad"]


def build_section_advice(
    key: str,
    *,
    field: str | None,
    metrics: Sequence[tuple[str, str, str]] | None,
    diagnostics: Mapping[str, object] | None,
) -> JsonDict:
    """
    Summary
    Build a UI and automation friendly advice block for a section.

    Inputs
    key: Section key (stable identifier).
    field: Rendered summary field text from the host (may be None).
    metrics: Rendered metrics rows as (label, value, status) tuples.
    diagnostics: Optional diagnostics mapping returned by the section handler.

    Outputs
    JSON dict containing `severity`, `diagnosis`, and `next_steps`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when advice construction fails unexpectedly.

    Ties to other methods
    Used by snapshot builder and CLI mode to provide an actionability layer on top of raw metrics.

    Why this exists
    Most users want recommended next steps, not just raw numbers. This provides consistent guidance and supports
    automation (for example, failing CI jobs when a snapshot shows warn or bad signals).
    """
    try:
        normalized_key = str(key or "").strip()
        metric_rows = list(metrics) if metrics is not None else []
        metric_map = _metric_map(metric_rows)

        severity = _severity_for_section(metric_rows, diagnostics)
        diagnosis = _diagnosis_for_section(
            normalized_key, field=field, metric_map=metric_map, severity=severity
        )
        next_steps = _next_steps_for_section(normalized_key, metric_map=metric_map, severity=severity)
        return {
            "severity": severity,
            "diagnosis": diagnosis,
            "next_steps": next_steps,
        }
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "build_section_advice", f"Failed to build advice for {key}", exc)
        ) from exc


def worst_severity_from_metrics(metrics: Sequence[tuple[str, str, str]] | None) -> AdviceSeverity:
    """
    Summary
    Determine the worst severity implied by rendered metric statuses.

    Inputs
    metrics: Metrics rows as (label, value, status) tuples.

    Outputs
    Severity string: "ok", "warn", or "bad".

    Side effects
    None.

    Error handling
    Never raises; returns "ok" on malformed input.

    Ties to other methods
    Used by `build_section_advice` and `should_fail_on` logic.

    Why this exists
    Sections already attach ok/warn/bad statuses to key metrics; this function turns those into a single decision.
    """
    try:
        if not metrics:
            return "ok"
        worst: AdviceSeverity = "ok"
        for _label, _value, status in metrics:
            normalized = _normalize_status(status)
            if normalized == "bad":
                return "bad"
            if normalized == "warn":
                worst = "warn"
        return worst
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError):
        return "ok"


def should_fail_on(severity: AdviceSeverity, fail_on: str | None) -> bool:
    """
    Summary
    Decide whether a given severity should trigger a non-zero exit code for automation.

    Inputs
    severity: Computed advice severity.
    fail_on: CLI flag value: "warn", "bad", or None.

    Outputs
    True when the severity meets or exceeds the threshold, else false.

    Side effects
    None.

    Error handling
    Never raises; returns false when fail_on is missing or invalid.

    Ties to other methods
    Used by CLI and snapshot modes to implement `--fail-on warn|bad`.

    Why this exists
    Automation workflows need a deterministic exit code when health signals cross a threshold.
    """
    try:
        mode = (fail_on or "").strip().lower()
        if not mode:
            return False
        if mode == "bad":
            return severity == "bad"
        if mode == "warn":
            return severity in {"warn", "bad"}
        return False
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError, IndexError, OSError):
        return False


def _severity_for_section(
    metrics: Sequence[tuple[str, str, str]], diagnostics: Mapping[str, object] | None
) -> AdviceSeverity:
    """
    Summary
    Execute `_severity_for_section` for its module-level responsibility.

    Inputs
    metrics: `Sequence[tuple[str, str, str]]` parameter from the function signature.
    diagnostics: `Mapping[str, object] | None` parameter from the function signature.

    Outputs
    Returns `AdviceSeverity`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/actionability/advice.py:_severity_for_section` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/actionability/advice.py`.

    Why this exists
    Keeps `_severity_for_section` explicit, testable, and maintainable.
    """
    worst = worst_severity_from_metrics(metrics)
    if worst != "ok":
        return worst
    if diagnostics is None:
        return "ok"
    ok_value = diagnostics.get("ok")
    if ok_value is False:
        return "warn"
    return "ok"


def _normalize_status(value: object) -> AdviceSeverity | None:
    """
    Summary
    Execute `_normalize_status` for its module-level responsibility.

    Inputs
    value: `object` parameter from the function signature.

    Outputs
    Returns `AdviceSeverity | None`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/actionability/advice.py:_normalize_status` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/actionability/advice.py`.

    Why this exists
    Keeps `_normalize_status` explicit, testable, and maintainable.
    """
    if not isinstance(value, str):
        return None
    lowered = value.strip().lower()
    if lowered in {"ok", "warn", "bad"}:
        return cast(AdviceSeverity, lowered)
    return None


def _metric_map(
    rows: Sequence[tuple[str, str, str]],
) -> dict[str, tuple[str, str]]:
    """
    Summary
    Execute `_metric_map` for its module-level responsibility.

    Inputs
    rows: `Sequence[tuple[str, str, str]]` parameter from the function signature.

    Outputs
    Returns `dict[str, tuple[str, str]]`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/actionability/advice.py:_metric_map` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/actionability/advice.py`.

    Why this exists
    Keeps `_metric_map` explicit, testable, and maintainable.
    """
    out: dict[str, tuple[str, str]] = {}
    for label, value, status in rows:
        if not label.strip():
            continue
        out[label.strip()] = (value, status.strip())
    return out


def _diagnosis_for_section(
    key: str,
    *,
    field: str | None,
    metric_map: Mapping[str, tuple[str, str]],
    severity: AdviceSeverity,
) -> str:
    """
    Summary
    Execute `_diagnosis_for_section` for its module-level responsibility.

    Inputs
    key: `str` parameter from the function signature.
    field: keyword-only `str | None` parameter.
    metric_map: keyword-only `Mapping[str, tuple[str, str]]` parameter.
    severity: keyword-only `AdviceSeverity` parameter.

    Outputs
    Returns `str`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/actionability/advice.py:_diagnosis_for_section` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/actionability/advice.py`.

    Why this exists
    Keeps `_diagnosis_for_section` explicit, testable, and maintainable.
    """
    if key == "battery":
        health = metric_map.get("Health")
        cycles = metric_map.get("Cycle count")
        if health:
            base = f"Battery health {health[0]}."
            if cycles:
                base = f"{base} Cycle count {cycles[0]}."
            return base
        return (field or "Battery data unavailable").strip() or "Battery data unavailable."
    if key == "ssd":
        life = metric_map.get("Life remaining")
        media = metric_map.get("Media errors")
        unsafe = metric_map.get("Unsafe shutdowns")
        parts: list[str] = []
        if life:
            parts.append(f"SSD life {life[0]}.")
        if media:
            parts.append(f"Media errors {media[0]}.")
        if unsafe:
            parts.append(f"Unsafe shutdowns {unsafe[0]}.")
        if parts:
            return " ".join(parts)
        return (field or "SSD data unavailable").strip() or "SSD data unavailable."
    if key == "network":
        rssi = metric_map.get("RSSI")
        iface = metric_map.get("Interface")
        ssid = metric_map.get("SSID")
        parts = []
        if iface:
            parts.append(f"Interface {iface[0]}.")
        if ssid:
            parts.append(f"SSID {ssid[0]}.")
        if rssi:
            parts.append(f"Signal {rssi[0]} ({_normalize_status(rssi[1]) or 'info'}).")
        if parts:
            return " ".join(parts)
        return (field or "Network data unavailable").strip() or "Network data unavailable."
    if key == "performance":
        hottest = metric_map.get("Hottest")
        if hottest:
            return f"Thermals: {hottest[0]}."
        sensors = [label for label in metric_map.keys() if "cpu" in label.lower() or "gpu" in label.lower()]
        if sensors and severity != "ok":
            return "High temperature readings detected."
        return (field or "Performance signals collected.").strip() or "Performance signals collected."
    if key == "fan":
        if severity != "ok":
            return (field or "Fan speed readings unavailable.").strip() or "Fan speed readings unavailable."
        return (field or "Fan speeds collected.").strip() or "Fan speeds collected."
    if key == "security":
        if severity == "ok":
            return "Security posture signals look healthy."
        return "One or more security posture flags are not enabled."
    if key == "system":
        if severity == "ok":
            return "Storage and memory pressure look healthy."
        return "Storage or memory pressure is elevated."
    if key == "backups":
        if severity == "ok":
            return "Time Machine backups look recent."
        return "Time Machine backups are missing or stale."
    if key == "updates":
        if severity == "ok":
            return "No pending software updates detected."
        return "Software updates appear to be available."
    if key == "startup":
        return "Startup items listed. Review unknown or unnecessary launch agents and daemons."
    if key == "processes":
        return "Top CPU and memory offenders listed."
    if field and field.strip():
        return field.strip()
    if severity == "bad":
        return "Bad signals detected."
    if severity == "warn":
        return "Warning signals detected."
    return "No warning signals detected."


def _next_steps_for_section(
    key: str, *, metric_map: Mapping[str, tuple[str, str]], severity: AdviceSeverity
) -> list[str]:
    """
    Summary
    Execute `_next_steps_for_section` for its module-level responsibility.

    Inputs
    key: `str` parameter from the function signature.
    metric_map: keyword-only `Mapping[str, tuple[str, str]]` parameter.
    severity: keyword-only `AdviceSeverity` parameter.

    Outputs
    Returns `list[str]`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `mac_health_checkup/app/actionability/advice.py:_next_steps_for_section` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `mac_health_checkup/app/actionability/advice.py`.

    Why this exists
    Keeps `_next_steps_for_section` explicit, testable, and maintainable.
    """
    steps: list[str] = []
    if key == "battery":
        if severity == "bad":
            steps.extend(
                [
                    "Back up data and plan for battery service or replacement.",
                    "If the system throttles on battery, test with the charger connected and compare.",
                ]
            )
        elif severity == "warn":
            steps.extend(
                [
                    "Monitor health and runtime over the next few charge cycles.",
                    "If battery life is noticeably reduced, plan a replacement before it becomes urgent.",
                ]
            )
        else:
            steps.append("No action needed. Recheck occasionally and keep macOS up to date.")
        steps.append("If cycle count is high, reduced runtime is expected as the pack ages.")
        return steps[:4]

    if key == "ssd":
        media = metric_map.get("Media errors")
        unsafe = metric_map.get("Unsafe shutdowns")
        if media and _normalize_status(media[1]) == "bad":
            steps.extend(
                [
                    "Back up immediately. Media errors can indicate impending SSD failure.",
                    "Run Disk Utility First Aid and review Console logs for repeated I/O errors.",
                ]
            )
        if unsafe and _normalize_status(unsafe[1]) in {"warn", "bad"}:
            steps.append("Investigate unexpected power loss or forced shutdowns that can corrupt data.")
        if severity in {"warn", "bad"}:
            steps.append("Confirm you have a current backup and enough free disk space for updates.")
        if not steps:
            steps.append("No immediate action. Keep reliable backups and recheck periodically.")
        return steps[:4]

    if key == "network":
        rssi = metric_map.get("RSSI")
        rssi_status = _normalize_status(rssi[1]) if rssi else None
        if rssi_status in {"warn", "bad"}:
            steps.extend(
                [
                    "Move closer to the access point or reduce obstacles and sources of interference.",
                    "Prefer 5 GHz or 6 GHz when available, and consider changing Wi‑Fi channels.",
                    "If RSSI stays poor, test with Ethernet to separate Wi‑Fi issues from ISP issues.",
                ]
            )
            return steps[:4]
        steps.extend(
            [
                "If connectivity is intermittent, re-run the check and compare RSSI and tx/rx rates.",
                "Restart the router if packet loss or capacity metrics are consistently degraded.",
            ]
        )
        return steps[:4]

    if key == "performance":
        if severity == "bad":
            steps.extend(
                [
                    "Check Activity Monitor for runaway processes and close or restart heavy apps.",
                    "Verify the Mac has adequate airflow and that vents are not blocked.",
                    "If temperatures remain high at idle, reboot and recheck.",
                ]
            )
            return steps[:4]
        if severity == "warn":
            steps.extend(
                [
                    "Monitor thermals during your normal workload and avoid sustained load on soft surfaces.",
                    "If fans are unavailable, compare against a trusted sensor tool (example: Mac Fan Control).",
                ]
            )
            return steps[:4]
        steps.append("No action needed. Use the snapshot diff feature to compare under load vs idle.")
        return steps[:4]

    if key == "fan":
        if severity != "ok":
            steps.extend(
                [
                    "Re-run after a reboot to confirm fan readings are consistently unavailable.",
                    "If you need fan speeds, install a user-space tool that exposes them (example: istats).",
                ]
            )
            return steps[:4]
        steps.append("No action needed. Fan speeds are informational unless paired with thermal warnings.")
        return steps[:4]

    if key == "ports":
        steps.append(
            "If a device behaves incorrectly, unplug peripherals one at a time and re-run the Ports tree."
        )
        steps.append(
            "If a USB-C port shows Display Alt Mode, confirm the cable and adapter support your display."
        )
        return steps[:4]

    if key == "devices":
        steps.append("If an unknown device appears, unplug it and re-run to confirm what changed.")
        return steps[:4]

    if key == "display":
        steps.append("If an external display is missing, verify the cable/adapter and re-run the snapshot.")
        return steps[:4]

    if key == "input":
        steps.append("If input devices are duplicated or missing, reconnect them and re-run the snapshot.")
        return steps[:4]

    if key == "power":
        steps.append("If charging behavior is unexpected, verify the adapter wattage and cable and re-run.")
        return steps[:4]

    if key == "security":
        steps.extend(
            [
                "If FileVault is off and this Mac is portable, consider enabling it to protect data at rest.",
                "If SIP is disabled, re-enable it unless you intentionally changed it for development or tooling.",
                "If Gatekeeper is disabled, consider enabling it to reduce the risk of running untrusted software.",
                "If the firewall is off, consider enabling it on untrusted networks.",
            ]
        )
        return steps[:4]

    if key == "system":
        steps.extend(
            [
                "If disk free is low, delete large unused files, empty Trash, and review Storage Management recommendations.",
                "If memory free is low, close heavy applications and check Activity Monitor for memory pressure.",
                "If the issue persists, reboot and compare a snapshot before vs after to identify changes.",
            ]
        )
        return steps[:4]

    if key == "backups":
        steps.extend(
            [
                "If you rely on backups, enable Time Machine and ensure a destination disk is connected.",
                "If backups are stale, keep the destination connected long enough to complete a full backup.",
                "Verify you can restore files by checking recent backup snapshots in Time Machine.",
            ]
        )
        return steps[:4]

    if key == "updates":
        steps.extend(
            [
                "Open System Settings > General > Software Update and apply pending updates.",
                "If updates are blocked by MDM or policy, confirm device management settings.",
            ]
        )
        return steps[:4]

    if key == "startup":
        steps.extend(
            [
                "Review launch items you do not recognize and identify the owning application.",
                "Disable unnecessary background helpers and reboot to confirm behavior changes.",
            ]
        )
        return steps[:4]

    if key == "processes":
        steps.extend(
            [
                "If CPU is high, inspect the listed processes in Activity Monitor and quit or restart the offender.",
                "If memory usage is high, close memory-heavy apps and watch Memory Pressure.",
                "If an unknown process is consuming resources, identify its path and signing status before taking action.",
            ]
        )
        return steps[:4]

    return ["No recommended next steps for this section."]
