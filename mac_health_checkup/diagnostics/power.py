from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import (
    format_error,
    regex_extract_float,
    regex_extract_int,
    safe_run,
    system_profiler_out,
)
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/power.py"


class ThermalDiagnostics:
    """
    Summary
    Collect thermal state signals from the system.

    Inputs
    None. Executes pmset.

    Outputs
    Dict with thermal state and raw output.

    Side effects
    Executes pmset.

    Error handling
    Returns unknown state when output is missing; raises `RuntimeError` with module and method context when parsing
    fails unexpectedly.

    Ties to other methods
    Used by the Performance section in the GUI.

    Why this exists
    Provides a lightweight thermal state signal.
    """

    _cache = Cache(get_config().timeouts.performance_cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch thermal state with caching.

        Inputs
        None.

        Outputs
        Dict with thermal state and raw output.

        Side effects
        Executes pmset when the cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by performance section handler.

        Why this exists
        Avoids repeated thermal polling.
        """
        try:
            return cached_fetch(ThermalDiagnostics._cache, "thermal", ThermalDiagnostics._fetch_uncached)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ThermalDiagnostics.fetch", "Failed to fetch thermal", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch thermal state without caching.

        Inputs
        None.

        Outputs
        Dict with thermal state and raw output.

        Side effects
        Executes pmset.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Separates IO from caching logic for testing.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("ThermalDiagnostics")
            out, err = safe_run(
                ["pmset", "-g", "thermlog"],
                context="thermal",
                allow_sudo=False,
                timeout=get_config().timeouts.default_cmd_timeout,
            )
            if not out:
                logger.warning(
                    "pmset thermlog empty",
                    event="thermal_empty",
                    context=context,
                    payload={"error": err or ""},
                )
                return {"state": "unknown", "raw": ""}
            state = _parse_thermal_state(out)
            return {"state": state, "raw": out}
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ThermalDiagnostics._fetch_uncached", "Thermal parsing failed", exc)
            ) from exc


class PowerResidencyDiagnostics:
    """
    Summary
    Collect power residency and power draw metrics.

    Inputs
    None. Executes powermetrics.

    Outputs
    Dict with CPU and GPU power stats.

    Side effects
    Executes powermetrics.

    Error handling
    Returns ok=false and permission hints when output is missing; raises `RuntimeError` with module and method
    context when parsing fails unexpectedly.

    Ties to other methods
    Used by the Performance section in the GUI.

    Why this exists
    Provides a snapshot of current power use.
    """

    _cache = Cache(get_config().timeouts.performance_cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch power residency metrics with caching.

        Inputs
        None.

        Outputs
        Dict with power metrics.

        Side effects
        Executes powermetrics when the cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by the performance section handler.

        Why this exists
        Avoids repeated powermetrics calls.
        """
        try:
            return cached_fetch(
                PowerResidencyDiagnostics._cache, "power_residency", PowerResidencyDiagnostics._fetch_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "PowerResidencyDiagnostics.fetch", "Failed to fetch power", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch power residency metrics without caching.

        Inputs
        None.

        Outputs
        Dict with power metrics.

        Side effects
        Executes powermetrics.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Separates IO from caching logic for testing.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("PowerResidencyDiagnostics")
            timeout = get_config().timeouts.powermetrics_timeout
            allow_sudo = bool(get_config().fans.use_sudo)
            out, err = safe_run(
                ["powermetrics", "-n", "1", "--samplers", "cpu_power"],
                context="powermetrics",
                allow_sudo=allow_sudo,
                timeout=timeout,
            )
            if not out:
                logger.warning(
                    "powermetrics empty",
                    event="power_empty",
                    context=context,
                    payload={"error": err or "", "allow_sudo": allow_sudo},
                )
                permission_required = False
                lowered = (err or "").lower()
                if "superuser" in lowered or "root" in lowered or "sudo" in lowered:
                    permission_required = True
                return {
                    "cpu_w": None,
                    "gpu_w": None,
                    "ane_w": None,
                    "raw": "",
                    "ok": False,
                    "permission_required": permission_required,
                }
            cpu_w = regex_extract_float(out, r"CPU Power:\s*([0-9.]+)\s*W")
            gpu_w = regex_extract_float(out, r"GPU Power:\s*([0-9.]+)\s*W")
            ane_w = regex_extract_float(out, r"ANE Power:\s*([0-9.]+)\s*W")
            return {"cpu_w": cpu_w, "gpu_w": gpu_w, "ane_w": ane_w, "raw": out, "ok": True}
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "PowerResidencyDiagnostics._fetch_uncached", "Power parsing failed", exc
                )
            ) from exc


class PowerAdapterDiagnostics:
    """
    Summary
    Collect power adapter metrics from system_profiler.

    Inputs
    None. Executes system_profiler.

    Outputs
    Dict with adapter watts, voltage, current, charging state.

    Side effects
    Executes system_profiler.

    Error handling
    Returns unknown adapter values when output is missing; raises `RuntimeError` with module and method context when
    parsing fails unexpectedly.

    Ties to other methods
    Used by the Power section in the GUI.

    Why this exists
    Provides charging state and adapter capacity details.
    """

    _cache = Cache(get_config().timeouts.power_sp_cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch adapter data with caching.

        Inputs
        None.

        Outputs
        Dict with adapter metrics.

        Side effects
        Executes system_profiler when the cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by the Power section handler.

        Why this exists
        Avoids repeated adapter queries.
        """
        try:
            return cached_fetch(
                PowerAdapterDiagnostics._cache, "adapter", PowerAdapterDiagnostics._fetch_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "PowerAdapterDiagnostics.fetch", "Failed to fetch adapter", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch adapter data without caching.

        Inputs
        None.

        Outputs
        Dict with adapter metrics.

        Side effects
        Executes system_profiler.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Separates IO from caching logic for testing.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("PowerAdapterDiagnostics")
            out, err = system_profiler_out("SPPowerDataType", context="adapter")
            if not out:
                logger.warning(
                    "adapter output empty",
                    event="adapter_empty",
                    context=context,
                    payload={"error": err or ""},
                )
                return {
                    "adapter_w": None,
                    "adapter_v": None,
                    "adapter_ma": None,
                    "is_charging": None,
                    "raw": "",
                }
            adapter_w = regex_extract_int(out, r"Wattage \(W\):\s*(\d+)")
            adapter_v = regex_extract_int(out, r"Voltage \(mV\):\s*(\d+)")
            adapter_ma = regex_extract_int(out, r"Amperage \(mA\):\s*(\d+)")
            is_charging = _parse_charging_state(out)
            return {
                "adapter_w": adapter_w,
                "adapter_v": adapter_v,
                "adapter_ma": adapter_ma,
                "is_charging": is_charging,
                "raw": out,
            }
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "PowerAdapterDiagnostics._fetch_uncached", "Adapter parsing failed", exc
                )
            ) from exc


class USBPowerDiagnostics:
    """
    Summary
    Collect USB power headroom from system_profiler.

    Inputs
    None. Executes system_profiler.

    Outputs
    Dict with hub power headroom entries.

    Side effects
    Executes system_profiler.

    Error handling
    Returns empty hubs when output is missing; raises `RuntimeError` with module and method context when parsing fails
    unexpectedly.

    Ties to other methods
    Used by the Power section in the GUI.

    Why this exists
    Provides visibility into USB power availability.
    """

    _cache = Cache(get_config().timeouts.power_sp_cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch USB power info with caching.

        Inputs
        None.

        Outputs
        Dict with hub power info.

        Side effects
        Executes system_profiler when the cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by the Power section handler.

        Why this exists
        Avoids repeated USB power queries.
        """
        try:
            return cached_fetch(USBPowerDiagnostics._cache, "usb_power", USBPowerDiagnostics._fetch_uncached)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "USBPowerDiagnostics.fetch", "Failed to fetch USB power", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch USB power info without caching.

        Inputs
        None.

        Outputs
        Dict with hub power info.

        Side effects
        Executes system_profiler.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Separates IO from caching logic for testing.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("USBPowerDiagnostics")
            out, err = system_profiler_out("SPUSBDataType", context="usb_power")
            if not out:
                logger.warning(
                    "usb power output empty",
                    event="usb_power_empty",
                    context=context,
                    payload={"error": err or ""},
                )
                return {"hubs": [], "raw": ""}
            hubs = _parse_usb_power(out)
            return {"hubs": hubs, "raw": out}
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "USBPowerDiagnostics._fetch_uncached", "USB power parsing failed", exc
                )
            ) from exc


def _parse_thermal_state(raw: str) -> str:
    """
    Summary
    Parse thermal state from pmset output.

    Inputs
    raw: pmset output.

    Outputs
    Thermal state string.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by `ThermalDiagnostics`.

    Why this exists
    Keeps thermal parsing logic isolated.
    """
    try:
        match = re.search(r"Thermal Level:\s*(\w+)", raw, re.IGNORECASE)
        if match:
            return match.group(1).lower()
        return "unknown"
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_thermal_state", "Failed to parse thermal state", exc)
        ) from exc


def _parse_charging_state(raw: str) -> bool | None:
    """
    Summary
    Parse charging state from power output.

    Inputs
    raw: system_profiler output.

    Outputs
    True if charging, false if not, None if unknown.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by `PowerAdapterDiagnostics`.

    Why this exists
    Keeps charging parsing logic isolated.
    """
    try:
        match = re.search(r"Charging:\s*(Yes|No)", raw, re.IGNORECASE)
        if not match:
            return None
        return match.group(1).lower() == "yes"
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_charging_state", "Failed to parse charging state", exc)
        ) from exc


def _parse_usb_power(raw: str) -> list[JsonDict]:
    """
    Summary
    Parse USB power headroom entries.

    Inputs
    raw: system_profiler output.

    Outputs
    List of hub dicts with headroom and devices.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by `USBPowerDiagnostics`.

    Why this exists
    Provides a readable USB power breakdown.
    """
    try:
        hubs: list[JsonDict] = []
        current_hub: JsonDict | None = None
        current_devices: list[JsonDict] | None = None
        for line in raw.splitlines():
            if re.match(r"^\s{12,}[^:\n]+:\s*$", line):
                device_name = line.strip().rstrip(":")
                if current_hub is not None and current_devices is not None:
                    current_devices.append({"name": device_name})
                continue
            if re.match(r"^\s{8,}[^:\n]+:\s*$", line):
                name = line.strip().rstrip(":")
                devices: list[JsonDict] = []
                current_hub = {"name": name, "devices": devices}
                current_devices = devices
                hubs.append(current_hub)
                continue
            if current_hub is None:
                continue
            available = regex_extract_int(line, r"Current Available \(mA\):\s*(\d+)")
            required = regex_extract_int(line, r"Current Required \(mA\):\s*(\d+)")
            if available is not None:
                current_hub["available_ma"] = available
            if required is not None:
                avail_value = current_hub.get("available_ma")
                avail_int = int(avail_value) if isinstance(avail_value, int) else None
                current_hub["required_ma"] = required
                current_hub["headroom_ma"] = avail_int - required if avail_int is not None else None
        return hubs
    except (RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_usb_power", "Failed to parse USB power", exc)
        ) from exc
