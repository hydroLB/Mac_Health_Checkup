from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.thermals.models import FanSpeedReading, TemperatureReading

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/parsing.py"

_TEMP_RE = re.compile(
    r"^\s*(?P<label>[^:]{2,}?)\s*:\s*(?P<value>-?[0-9]+(?:\.[0-9]+)?)\s*(?:°?\s*)?(?:C|c)\b"
)
_FAN_RE = re.compile(r"^\s*(?P<label>[^:]{2,}?)\s*:\s*(?P<rpm>[0-9]+)\s*RPM\b", re.IGNORECASE)
_ISTATS_PERMISSION_HINTS = ("ioserviceopen", "e00002e2", "not permitted", "operation not permitted")


def _smc_sampler_may_be_hidden(error_text: str) -> bool:
    """
    Summary
    Detect whether powermetrics may support a hidden SMC sampler.

    Inputs
    error_text: Stderr from a failed powermetrics invocation.

    Outputs
    True when retrying with `--unhide-info smc` is likely to help.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when text inspection fails unexpectedly.

    Ties to other methods
    Used by `ThermalSensorsDiagnostics` to decide when to retry powermetrics with additional flags.

    Why this exists
    Some macOS builds hide samplers for compatibility but still support them behind `--unhide-info`.
    """
    try:
        text = (error_text or "").lower()
        hints = (
            "unknown sampler",
            "unknown samplers",
            "invalid sampler",
            "sampler not supported",
            "unrecognized sampler",
        )
        return any(hint in text for hint in hints)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_smc_sampler_may_be_hidden", "Failed to inspect error text", exc)
        ) from exc


def _status_for_temp(temp_c: float) -> str:
    """
    Summary
    Map a temperature to an ok, warn, bad status string using config thresholds.

    Inputs
    temp_c: Temperature in Celsius.

    Outputs
    Status string used by the UI.

    Side effects
    Reads thresholds from `get_config()`.

    Error handling
    Raises `RuntimeError` with module and method context when mapping fails.

    Ties to other methods
    Used by temperature parsing helpers to attach statuses to rows.

    Why this exists
    Keeps temperature severity consistent and centrally tunable.
    """
    try:
        cfg = get_config().thresholds
        if temp_c >= cfg.temp_bad_c:
            return "bad"
        if temp_c >= cfg.temp_warn_c:
            return "warn"
        return "ok"
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_status_for_temp", "Failed to map temperature to status", exc)
        ) from exc


def _parse_powermetrics_smc(raw: str) -> tuple[list[TemperatureReading], list[FanSpeedReading]]:
    """
    Summary
    Parse powermetrics SMC sampler output for temperatures and fan RPM.

    Inputs
    raw: powermetrics output string.

    Outputs
    Tuple of (temperature readings, fan readings).

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by `ThermalSensorsDiagnostics` when powermetrics returns SMC rows.

    Why this exists
    Enables a Mac Fan Control style sensor table without external dependencies.
    """
    try:
        temps: list[TemperatureReading] = []
        fans: list[FanSpeedReading] = []
        seen_temp: set[str] = set()
        seen_fan: set[str] = set()

        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            fan_match = _FAN_RE.match(line)
            if fan_match:
                label = fan_match.group("label").strip()
                rpm = int(fan_match.group("rpm"))
                if label and label.lower() not in seen_fan:
                    seen_fan.add(label.lower())
                    fans.append(FanSpeedReading(label=label, rpm=rpm))
                continue

            temp_match = _TEMP_RE.match(line)
            if temp_match:
                label = temp_match.group("label").strip()
                value = float(temp_match.group("value"))
                if not label:
                    continue
                key = label.lower()
                if key in seen_temp:
                    continue
                seen_temp.add(key)
                temps.append(TemperatureReading(label=label, celsius=value, status=_status_for_temp(value)))
                continue

        temps.sort(key=lambda item: item.celsius, reverse=True)
        fans.sort(key=lambda item: item.label.lower())
        return temps, fans
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH, "_parse_powermetrics_smc", "Failed to parse powermetrics smc output", exc
            )
        ) from exc


def _parse_istats_scan_text(raw: str) -> list[TemperatureReading]:
    """
    Summary
    Parse `istats scan` output into temperature readings.

    Inputs
    raw: istats scan output string.

    Outputs
    List of `TemperatureReading`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by `ThermalSensorsDiagnostics` as a richer fallback for per-sensor readings.

    Why this exists
    Some hosts expose a sensor inventory via iStats even when powermetrics is restricted.
    """
    try:
        return _parse_temperature_lines(raw)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_istats_scan_text", "Failed to parse istats scan output", exc)
        ) from exc


def _parse_temperature_lines(raw: str) -> list[TemperatureReading]:
    """
    Summary
    Parse generic `label: <value> C` temperature lines into readings.

    Inputs
    raw: Text output from a tool.

    Outputs
    List of `TemperatureReading` values sorted by temperature descending.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by powermetrics and iStats parsing fallbacks.

    Why this exists
    Keeps temperature parsing consistent across multiple tool sources.
    """
    try:
        temps: list[TemperatureReading] = []
        seen: set[str] = set()
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            match = _TEMP_RE.match(line)
            if not match:
                continue
            label = match.group("label").strip()
            value = float(match.group("value"))
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            temps.append(TemperatureReading(label=label, celsius=value, status=_status_for_temp(value)))
        temps.sort(key=lambda item: item.celsius, reverse=True)
        return temps
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_temperature_lines", "Failed to parse temperature lines", exc)
        ) from exc


def _istats_output_indicates_permission_error(raw: str) -> bool:
    """
    Summary
    Detect whether an iStats output blob indicates restricted sensor access.

    Inputs
    raw: stdout or stderr text from an iStats invocation.

    Outputs
    True when output contains known permission restriction hints.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when inspection fails unexpectedly.

    Ties to other methods
    Used by thermals authorization and collection to decide when to guide the user to authorize privileged access.

    Why this exists
    iStats can print permission errors to stdout while still exiting 0, so return codes alone are not reliable.
    """
    try:
        text = (raw or "").lower()
        return any(hint in text for hint in _ISTATS_PERMISSION_HINTS)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_istats_output_indicates_permission_error",
                "Failed to inspect istats output",
                exc,
            )
        ) from exc
