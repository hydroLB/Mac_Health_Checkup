from __future__ import annotations

import re
from dataclasses import dataclass

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils import safe_run, system_profiler_out
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/fan.py"

FAN_SPEED_RE = re.compile(r"Fan Speed:\s*(\d+)\s*RPM", re.IGNORECASE)
FAN_HEADER_RE = re.compile(r"^(\s+)([^:\n]+):\s*$")


@dataclass(frozen=True)
class FanReading:
    """
    Summary
    Represent a fan reading with name and rpm.

    Inputs
    name: Fan label.
    rpm: Fan speed.

    Outputs
    Immutable fan reading.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `FanDiagnostics` parsing helpers.

    Why this exists
    Keeps parsed fan data strongly typed.
    """

    name: str
    rpm: int


class FanDiagnostics:
    """
    Summary
    Collect fan speed and status data.

    Inputs
    None. Executes system_profiler and optional istats.

    Outputs
    Dict with fan list and status.

    Side effects
    Executes system_profiler and may run istats.

    Error handling
    Returns empty fan lists when tools are unavailable; raises `RuntimeError` with module and method context when
    parsing fails unexpectedly.

    Ties to other methods
    Used by the Fan section in the GUI.

    Why this exists
    Provides fan status summary for the dashboard.
    """

    _cache = Cache(get_config().timeouts.performance_cache_ttl)

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch fan data with caching.

        Inputs
        None.

        Outputs
        Dict with fans list and summary status.

        Side effects
        Executes system_profiler or istats when the cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by the Fan section handler.

        Why this exists
        Avoids repeated IO while keeping fan data fresh.
        """
        try:
            return cached_fetch(FanDiagnostics._cache, "fan", FanDiagnostics._fetch_uncached)
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "FanDiagnostics.fetch", "Failed to fetch fans", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch fan data without caching.

        Inputs
        None.

        Outputs
        Dict with fans list and status.

        Side effects
        Executes system_profiler or istats.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Separates IO from caching logic for testing.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("FanDiagnostics")
            out, err = system_profiler_out("SPPowerDataType", context="fan")
            readings = FanDiagnostics._parse_system_profiler(out or "") if out else []
            if not readings:
                readings = FanDiagnostics._parse_istats()
            if not readings:
                logger.warning(
                    "no fan readings", event="fan_empty", context=context, payload={"error": err or ""}
                )
                return {"status": "No fan data", "fans": [], "raw": out or ""}
            status = " | ".join(f"{reading.name}: {reading.rpm} RPM" for reading in readings)
            return {"status": status, "fans": [reading.__dict__ for reading in readings], "raw": out or ""}
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "FanDiagnostics._fetch_uncached", "Fan parsing failed", exc)
            ) from exc

    @staticmethod
    def _parse_system_profiler(raw: str) -> list[FanReading]:
        """
        Summary
        Parse fan readings from system_profiler output.

        Inputs
        raw: system_profiler output.

        Outputs
        List of FanReading values.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `_fetch_uncached`.

        Why this exists
        Extracts fan data without extra dependencies.
        """
        try:
            readings: list[FanReading] = []
            current_label: str | None = None
            for line in raw.splitlines():
                header_match = FAN_HEADER_RE.match(line)
                if header_match:
                    current_label = header_match.group(2).strip()
                    continue
                speed_match = FAN_SPEED_RE.search(line)
                if speed_match:
                    rpm = int(speed_match.group(1))
                    label = current_label or f"Fan {len(readings) + 1}"
                    readings.append(FanReading(name=label, rpm=rpm))
            return readings
        except (RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "FanDiagnostics._parse_system_profiler", "Failed to parse fan output", exc
                )
            ) from exc

    @staticmethod
    def _parse_istats() -> list[FanReading]:
        """
        Summary
        Parse fan readings from istats if available.

        Inputs
        None.

        Outputs
        List of FanReading values.

        Side effects
        Executes istats.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `_fetch_uncached` when system_profiler has no data.

        Why this exists
        Provides a fallback for fan speed parsing.
        """
        try:
            timeout = get_config().timeouts.istats_timeout
            candidates: list[tuple[list[str], str]] = [
                (["istats", "fan"], "fan_istats"),
                (["istats", "fan", "speed"], "fan_istats_speed"),
                (["istats", "fan", "speed", "--value-only"], "fan_istats_speed_value_only"),
            ]
            for cmd, context in candidates:
                out, _err = safe_run(cmd, context=context, allow_sudo=False, timeout=timeout)
                if not out:
                    continue
                parsed = FanDiagnostics._parse_istats_output(out)
                if parsed:
                    return parsed
            return []
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "FanDiagnostics._parse_istats", "Failed to parse istats", exc)
            ) from exc

    @staticmethod
    def _parse_istats_output(out: str) -> list[FanReading]:
        """
        Summary
        Parse fan speed readings from an istats output blob.

        Inputs
        out: istats stdout text.

        Outputs
        List of FanReading values.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `_parse_istats` for multiple istats subcommands.

        Why this exists
        istats supports multiple output shapes (labeled and value-only) across versions.
        """
        try:
            readings: list[FanReading] = []
            for line in out.splitlines():
                text = line.strip()
                match = re.search(r"^([^:]+):\s*([0-9][0-9,]*)\s*RPM\b", text, re.IGNORECASE)
                if match:
                    rpm = int(match.group(2).replace(",", ""))
                    label = match.group(1).strip()
                    if label:
                        readings.append(FanReading(name=label, rpm=rpm))
            if readings:
                return readings

            value_only: list[int] = []
            for line in out.splitlines():
                text = line.strip()
                if not text:
                    continue
                match = re.search(r"^([0-9][0-9,]*)\s*(?:RPM\b)?$", text, re.IGNORECASE)
                if match:
                    value_only.append(int(match.group(1).replace(",", "")))
            if value_only:
                return [FanReading(name=f"Fan {idx}", rpm=rpm) for idx, rpm in enumerate(value_only)]

            return []
        except (RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "FanDiagnostics._parse_istats_output", "Failed to parse istats output", exc
                )
            ) from exc
