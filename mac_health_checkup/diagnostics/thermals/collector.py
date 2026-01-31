from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.shell import run_with_admin_prompt, safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context
from mac_health_checkup.diagnostics.thermals.authorization import (
    admin_prompt_gate,
    admin_prompt_session_active,
    record_admin_prompt_failure,
)
from mac_health_checkup.diagnostics.thermals.executables import resolve_executable
from mac_health_checkup.diagnostics.thermals.models import FanSpeedReading, TemperatureReading
from mac_health_checkup.diagnostics.thermals.parsing import (
    _istats_output_indicates_permission_error,
    _parse_istats_scan_text,
    _parse_powermetrics_smc,
    _parse_temperature_lines,
    _smc_sampler_may_be_hidden,
    _status_for_temp,
)

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/collector.py"

_ISTATS_CPU_TEMP_RE = re.compile(r"CPU temp:\s*([0-9]+(?:\.[0-9]+)?)\s*°?C", re.IGNORECASE)
_ISTATS_BATTERY_TEMP_RE = re.compile(r"Battery temp:\s*([0-9]+(?:\.[0-9]+)?)\s*°?C", re.IGNORECASE)


class ThermalSensorsDiagnostics:
    """
    Purpose: Collect thermal sensor readings when available on the host.
    Ties: Used by Performance and Fans sections to provide sensor-style rows.
    Inputs: None. Executes best-effort local tools without interactive prompts.
    Outputs: Dict with sensors, fans, and raw output.
    Side effects: Executes subprocess commands.
    Why: Some macOS builds restrict direct sensor access; this collector degrades gracefully while still surfacing actionable guidance.
    """

    _cache = Cache(get_config().timeouts.performance_cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Purpose: Fetch thermal sensor readings with caching.
        Ties: Used by section handlers to avoid repeated powermetrics calls.
        Inputs: None.
        Outputs: Dict with sensors and fans lists.
        Side effects: Executes powermetrics if cache is stale.
        Why: Keeps the UI responsive while still updating near real-time.
        """
        try:
            return cached_fetch(
                ThermalSensorsDiagnostics._cache, "thermal_sensors", ThermalSensorsDiagnostics._fetch_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "ThermalSensorsDiagnostics.fetch", "Failed to fetch thermal sensors", exc
                )
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Purpose: Fetch thermal sensor readings without caching.
        Ties: Used by cached_fetch.
        Inputs: None.
        Outputs: Dict with parsed sensors, fans, and raw output.
        Side effects: Executes powermetrics and optionally istats.
        Why: Separates IO from caching logic for testability.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("ThermalSensorsDiagnostics")

            sensors: list[TemperatureReading] = []
            fans: list[FanSpeedReading] = []
            raw_chunks: list[str] = []
            source: str | None = None

            allow_sudo = bool(get_config().fans.use_sudo)
            use_admin_prompt = bool(get_config().fans.use_admin_prompt) and admin_prompt_session_active()
            timeout = max(3, get_config().timeouts.powermetrics_timeout)
            istats_path = resolve_executable("istats")

            istats_timeout = max(2, get_config().timeouts.istats_timeout)
            if use_admin_prompt and istats_path is not None and not sensors:
                prompted = _maybe_collect_istats_scan_admin_prompt(istats_path, timeout=istats_timeout)
                sensors.extend(prompted.sensors)
                raw_chunks.extend(prompted.raw_chunks)
                source = source or prompted.source

            istats_cmd_builder = _build_istats_cmd_builder(
                istats_path=istats_path, allow_sudo=allow_sudo, use_admin_prompt=use_admin_prompt
            )

            if use_admin_prompt and istats_path is not None:
                cpu_batt = _maybe_collect_istats_cpu_battery_admin_prompt(istats_path, timeout=istats_timeout)
                sensors.extend(cpu_batt.sensors)
                raw_chunks.extend(cpu_batt.raw_chunks)
                source = source or cpu_batt.source

            if not sensors:
                out, err = safe_run(
                    ["powermetrics", "-n", "1", "--samplers", "smc"],
                    context="powermetrics_smc",
                    allow_sudo=allow_sudo,
                    timeout=timeout,
                )
                if not out and _smc_sampler_may_be_hidden(err or ""):
                    out, err = safe_run(
                        ["powermetrics", "-n", "1", "--samplers", "smc", "--unhide-info", "smc"],
                        context="powermetrics_smc_unhide",
                        allow_sudo=allow_sudo,
                        timeout=timeout,
                    )
                if out:
                    parsed_sensors, parsed_fans = _parse_powermetrics_smc(out)
                    sensors.extend(parsed_sensors)
                    fans.extend(parsed_fans)
                    raw_chunks.append(out)
                    source = source or "powermetrics_smc"
                else:
                    logger.info(
                        "powermetrics smc unavailable",
                        event="powermetrics_smc_unavailable",
                        context=context,
                        payload={"error": err or "", "allow_sudo": allow_sudo},
                    )
                    if err:
                        raw_chunks.append(err)

            should_attempt_istats_scan = istats_path is not None and (
                (allow_sudo and not use_admin_prompt) or not sensors
            )

            if should_attempt_istats_scan and istats_path is not None and not allow_sudo:
                combined = "\n\n".join(chunk for chunk in raw_chunks if chunk.strip())
                if _istats_output_indicates_permission_error(combined):
                    return _permission_required_payload(combined)

            if should_attempt_istats_scan and istats_path is not None:
                scan = _collect_istats_scan(
                    istats_cmd_builder(["scan", "--no-graphs", "--no-scale"]), timeout=istats_timeout
                )
                sensors.extend(scan.sensors)
                raw_chunks.extend(scan.raw_chunks)
                source = source or scan.source

            if not fans and istats_path is not None:
                fan_rows = _collect_istats_fans(istats_cmd_builder(["fan"]), timeout=min(istats_timeout, 4))
                fans.extend(fan_rows.fans)
                raw_chunks.extend(fan_rows.raw_chunks)
                source = source or fan_rows.source

            if not sensors:
                alt_out, alt_err = safe_run(
                    ["powermetrics", "-n", "1", "--show-all"],
                    context="powermetrics_all",
                    allow_sudo=allow_sudo,
                    timeout=timeout,
                )
                if alt_out:
                    sensors.extend(_parse_temperature_lines(alt_out))
                    raw_chunks.append(alt_out)
                    source = source or "powermetrics_all"
                if alt_err:
                    raw_chunks.append(alt_err)

            combined_raw = "\n\n".join(chunk for chunk in raw_chunks if chunk.strip())
            ok = bool(sensors or fans)
            error: str | None = None
            permission_required = False
            guidance: str | None = None
            if not ok:
                error = "No supported sensor source returned data"
            lowered = combined_raw.lower()
            if "must be invoked as the superuser" in lowered or "root" in lowered or "sudo" in lowered:
                permission_required = True
                guidance = (
                    "Temperature sensors require admin authorization on this macOS build. "
                    "Click the gear icon → Temperature Sensors → Request Access Now to show the macOS password prompt."
                )
            if _istats_output_indicates_permission_error(lowered):
                permission_required = True
            if permission_required and guidance is None:
                if allow_sudo:
                    guidance = (
                        "Thermal sensors are restricted on this macOS build. Mac Fan Control works because it uses a privileged helper. "
                        "Use the gear icon → Temperature Sensors → Request Access Now to show the macOS admin prompt."
                    )
                else:
                    guidance = (
                        "Thermal sensors are restricted on this macOS build. Mac Fan Control works because it uses a privileged helper. "
                        "Enable fans.use_admin_prompt=true in config/config.json to use the macOS admin prompt."
                    )

            return {
                "ok": ok,
                "sensors": [reading.__dict__ for reading in sensors],
                "fans": [reading.__dict__ for reading in fans],
                "source": source or "unknown",
                "raw": combined_raw,
                "permission_required": permission_required,
                "error": error,
                "guidance": guidance,
            }
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "ThermalSensorsDiagnostics._fetch_uncached",
                    "Failed to fetch thermal sensor output",
                    exc,
                )
            ) from exc


@dataclass(frozen=True)
class _SensorsCollectResult:
    sensors: list[TemperatureReading]
    raw_chunks: list[str]
    source: str | None


@dataclass(frozen=True)
class _FansCollectResult:
    fans: list[FanSpeedReading]
    raw_chunks: list[str]
    source: str | None


def _build_istats_cmd_builder(
    *, istats_path: str | None, allow_sudo: bool, use_admin_prompt: bool
) -> Callable[[list[str]], list[str]]:
    try:

        def _builder(parts: list[str]) -> list[str]:
            if istats_path is None:
                return parts
            base = [istats_path, *parts]
            if use_admin_prompt:
                return base
            return ["sudo", "-n", *base] if allow_sudo else base

        return _builder
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_build_istats_cmd_builder", "Failed to build istats cmd builder", exc)
        ) from exc


def _maybe_collect_istats_scan_admin_prompt(istats_path: str, *, timeout: int) -> _SensorsCollectResult:
    try:
        allowed, _ = admin_prompt_gate(force=False)
        if not allowed:
            return _SensorsCollectResult(sensors=[], raw_chunks=[], source=None)
        prompted_out, prompted_err = run_with_admin_prompt(
            [istats_path, "scan", "--no-graphs", "--no-scale"],
            context="istats_scan_admin",
            timeout=max(6, timeout),
        )
        sensors: list[TemperatureReading] = []
        raw_chunks: list[str] = []
        source: str | None = None
        if prompted_out and not _istats_output_indicates_permission_error(prompted_out):
            sensors.extend(_parse_istats_scan_text(prompted_out))
            raw_chunks.append(prompted_out)
            source = "istats_admin_prompt"
        if prompted_err:
            raw_chunks.append(prompted_err)
            record_admin_prompt_failure()
        return _SensorsCollectResult(sensors=sensors, raw_chunks=raw_chunks, source=source)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH, "_maybe_collect_istats_scan_admin_prompt", "Failed to run admin prompt scan", exc
            )
        ) from exc


def _maybe_collect_istats_cpu_battery_admin_prompt(
    istats_path: str, *, timeout: int
) -> _SensorsCollectResult:
    try:
        allowed, _ = admin_prompt_gate(force=False)
        if not allowed:
            return _SensorsCollectResult(sensors=[], raw_chunks=[], source=None)
        sensors: list[TemperatureReading] = []
        raw_chunks: list[str] = []
        source: str | None = None

        cpu_out, cpu_err = run_with_admin_prompt(
            [istats_path, "cpu", "--no-graphs", "--no-scale"],
            context="istats_cpu_admin",
            timeout=max(4, timeout),
        )
        if cpu_out:
            raw_chunks.append(cpu_out)
            if not _istats_output_indicates_permission_error(cpu_out):
                match = _ISTATS_CPU_TEMP_RE.search(cpu_out)
                if match:
                    value = float(match.group(1))
                    if value > 0.0:
                        sensors.append(
                            TemperatureReading(
                                label="CPU Temp", celsius=value, status=_status_for_temp(value)
                            )
                        )
                        source = source or "istats_admin_prompt"
        if cpu_err:
            raw_chunks.append(cpu_err)
            record_admin_prompt_failure()

        batt_out, batt_err = run_with_admin_prompt(
            [istats_path, "battery", "--no-graphs", "--no-scale"],
            context="istats_battery_admin",
            timeout=max(4, timeout),
        )
        if batt_out:
            raw_chunks.append(batt_out)
            if not _istats_output_indicates_permission_error(batt_out):
                match = _ISTATS_BATTERY_TEMP_RE.search(batt_out)
                if match:
                    value = float(match.group(1))
                    if value > 0.0:
                        sensors.append(
                            TemperatureReading(
                                label="Battery Temp", celsius=value, status=_status_for_temp(value)
                            )
                        )
                        source = source or "istats_admin_prompt"
        if batt_err:
            raw_chunks.append(batt_err)
            record_admin_prompt_failure()

        return _SensorsCollectResult(sensors=sensors, raw_chunks=raw_chunks, source=source)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_maybe_collect_istats_cpu_battery_admin_prompt",
                "Failed to collect istats temps",
                exc,
            )
        ) from exc


def _collect_istats_scan(cmd: list[str], *, timeout: int) -> _SensorsCollectResult:
    try:
        scan_out, scan_err = safe_run(cmd, context="istats_scan", allow_sudo=False, timeout=timeout)
        sensors: list[TemperatureReading] = []
        raw_chunks: list[str] = []
        source: str | None = None
        if scan_out:
            raw_chunks.append(scan_out)
            if not _istats_output_indicates_permission_error(scan_out):
                sensors.extend(_parse_istats_scan_text(scan_out))
                if sensors:
                    source = "istats_scan"
        if scan_err:
            raw_chunks.append(scan_err)
        return _SensorsCollectResult(sensors=sensors, raw_chunks=raw_chunks, source=source)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_collect_istats_scan", "Failed to collect istats scan output", exc)
        ) from exc


def _collect_istats_fans(cmd: list[str], *, timeout: int) -> _FansCollectResult:
    try:
        out, err = safe_run(cmd, context="fan_istats", allow_sudo=False, timeout=timeout)
        fans: list[FanSpeedReading] = []
        raw_chunks: list[str] = []
        source: str | None = None
        if out:
            raw_chunks.append(out)
            if not _istats_output_indicates_permission_error(out):
                for line in out.splitlines():
                    match = re.search(r"^([^:]+):\s*([0-9][0-9,]*)\s*RPM\b", line.strip(), re.IGNORECASE)
                    if match:
                        fans.append(
                            FanSpeedReading(
                                label=match.group(1).strip(), rpm=int(match.group(2).replace(",", ""))
                            )
                        )
                if fans:
                    source = "istats_fans"
        if err:
            raw_chunks.append(err)
        return _FansCollectResult(fans=fans, raw_chunks=raw_chunks, source=source)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_collect_istats_fans", "Failed to collect istats fans", exc)
        ) from exc


def _permission_required_payload(raw: str) -> JsonDict:
    try:
        return {
            "ok": False,
            "sensors": [],
            "fans": [],
            "raw": raw,
            "permission_required": True,
            "error": "Sensor access restricted",
            "guidance": (
                "Thermal sensors are restricted on this macOS build. Mac Fan Control works because it uses a privileged helper. "
                "Enable fans.use_sudo=true in config/config.json and run `sudo -v` before launching the UI."
            ),
        }
    except Exception as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_permission_required_payload", "Failed to build payload", exc)
        ) from exc
