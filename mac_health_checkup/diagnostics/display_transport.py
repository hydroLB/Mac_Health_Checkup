from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.shell import system_profiler_out
from mac_health_checkup.diagnostics.base import get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/display_transport.py"


class DisplayTransportDiagnostics:
    """
    Summary
    Estimate display transport labels from display output.

    Inputs
    Optional base dict with raw display output.

    Outputs
    Dict with display transport list and raw.

    Side effects
    May execute system_profiler if raw is not provided.

    Error handling
    Returns empty display lists when output is missing; raises `RuntimeError` with module and method context when
    parsing fails unexpectedly.

    Ties to other methods
    Used by the display section to show transport per display.

    Why this exists
    Provides transport hints without extra tooling.
    """

    @staticmethod
    def fetch(base: JsonDict | None = None) -> JsonDict:
        """
        Summary
        Fetch display transport labels and bandwidth estimates.

        Inputs
        base: Optional dict that may contain raw display output.

        Outputs
        Dict with displays list and raw output.

        Side effects
        Executes system_profiler if raw is not provided.

        Error handling
        Raises `RuntimeError` with module and method context when fetching or parsing fails.

        Ties to other methods
        Used by display section handler.

        Why this exists
        Keeps transport estimates and parsing centralized.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("DisplayTransportDiagnostics")
            raw = None
            if base is not None:
                raw_value = base.get("raw")
                raw = raw_value if isinstance(raw_value, str) else None
            if not raw:
                raw, err = system_profiler_out("SPDisplaysDataType", context="display_transport")
                if not raw:
                    logger.warning(
                        "display transport output empty",
                        event="display_transport_empty",
                        context=context,
                        payload={"error": err or ""},
                    )
                    return {"displays": [], "raw": ""}
            transports = _parse_transports(raw)
            estimates = _estimate_bandwidths(raw)
            merged = _merge_transports(transports, estimates)
            return {"displays": merged, "raw": raw}
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DisplayTransportDiagnostics.fetch", "Failed to fetch transport", exc
                )
            ) from exc


def _parse_transports(raw: str) -> list[str]:
    """
    Summary
    Parse transport labels from display output.

    Inputs
    raw: Display output string.

    Outputs
    List of transport labels.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by `DisplayTransportDiagnostics`.

    Why this exists
    Keeps transport parsing logic isolated and testable.
    """
    try:
        transports: list[str] = []
        for match in re.finditer(r"Connection Type:\s*(.+)", raw):
            label = match.group(1).strip()
            transports.append(_normalize_transport(label))
        if not transports:
            transports.append("?")
        return transports
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_transports", "Failed to parse transports", exc)
        ) from exc


def _normalize_transport(label: str) -> str:
    """
    Summary
    Normalize a connection label into a transport hint.

    Inputs
    label: Raw connection label.

    Outputs
    Normalized transport label.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when normalization fails unexpectedly.

    Ties to other methods
    Used by `_parse_transports`.

    Why this exists
    Keeps transport labels consistent for the UI.
    """
    try:
        lower = label.lower()
        if "internal" in lower or "built" in lower:
            return "Internal"
        if "thunderbolt" in lower or "displayport" in lower:
            return "DisplayPort"
        if "hdmi" in lower:
            return "HDMI"
        if "usb" in lower:
            return "USB"
        if "airplay" in lower or "wireless" in lower:
            return "Wireless"
        return label.strip()
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_normalize_transport", "Failed to normalize transport", exc)
        ) from exc


def _estimate_bandwidths(raw: str) -> list[float | None]:
    """
    Summary
    Estimate display bandwidth from resolution and refresh rate.

    Inputs
    raw: Display output string.

    Outputs
    List of bandwidth estimates in Gbps or None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when estimation fails unexpectedly.

    Ties to other methods
    Used by `DisplayTransportDiagnostics` to enrich transport labels.

    Why this exists
    Provides a tunable transport estimate using config values.
    """
    try:
        cfg = get_config().display_transport
        estimates: list[float | None] = []
        blocks = _split_display_blocks(raw)
        for block in blocks:
            width, height = _parse_resolution(block)
            refresh = _parse_refresh_hz(block)
            if width is None or height is None or refresh is None:
                estimates.append(None)
                continue
            pixels = width * height
            bits_per_second = pixels * refresh * cfg.default_bpp * cfg.overhead_factor
            gbps = bits_per_second / 1_000_000_000
            estimates.append(gbps)
        return estimates
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_estimate_bandwidths", "Failed to estimate bandwidth", exc)
        ) from exc


def _merge_transports(transports: list[str], estimates: list[float | None]) -> list[str]:
    """
    Summary
    Merge transport labels with optional bandwidth estimates.

    Inputs
    transports: Transport labels.
    estimates: Bandwidth estimates aligned to transports.

    Outputs
    List of merged transport labels.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when merging fails unexpectedly.

    Ties to other methods
    Used by `DisplayTransportDiagnostics` to format display strings.

    Why this exists
    Keeps transport output readable while adding useful context.
    """
    try:
        merged: list[str] = []
        for idx, label in enumerate(transports):
            estimate = estimates[idx] if idx < len(estimates) else None
            if estimate is None:
                merged.append(label)
            else:
                merged.append(f"{label} {estimate:.2f} Gbps")
        return merged
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_merge_transports", "Failed to merge transports", exc)
        ) from exc


def _split_display_blocks(raw: str) -> list[str]:
    """
    Summary
    Split display output into per-display blocks.

    Inputs
    raw: Display output string.

    Outputs
    List of display block strings.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when splitting fails unexpectedly.

    Ties to other methods
    Used by `_estimate_bandwidths` for parsing.

    Why this exists
    Keeps display parsing deterministic without external helpers.
    """
    try:
        starts = [match.start() for match in re.finditer(r"^\s{4}[^:\n]+:\s*$", raw, re.MULTILINE)]
        if not starts:
            return []
        blocks: list[str] = []
        for idx, start in enumerate(starts):
            end = starts[idx + 1] if idx + 1 < len(starts) else len(raw)
            blocks.append(raw[start:end])
        return blocks
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_split_display_blocks", "Failed to split blocks", exc)
        ) from exc


def _parse_resolution(block: str) -> tuple[int | None, int | None]:
    """
    Summary
    Parse resolution width and height from a display block.

    Inputs
    block: Display block string.

    Outputs
    Tuple of (width, height) or (None, None).

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by `_estimate_bandwidths`.

    Why this exists
    Provides resolution data for bandwidth estimation.
    """
    try:
        match = re.search(r"Resolution:\s*(\d+)\s*x\s*(\d+)", block)
        if not match:
            return None, None
        return int(match.group(1)), int(match.group(2))
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_resolution", "Failed to parse resolution", exc)
        ) from exc


def _parse_refresh_hz(block: str) -> float | None:
    """
    Summary
    Parse refresh rate from a display block.

    Inputs
    block: Display block string.

    Outputs
    Refresh rate as float or None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by `_estimate_bandwidths`.

    Why this exists
    Provides refresh data for bandwidth estimation.
    """
    try:
        match = re.search(r"Refresh Rate:\s*([0-9.]+)\s*Hz", block)
        if not match:
            return None
        return float(match.group(1))
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_parse_refresh_hz", "Failed to parse refresh", exc)
        ) from exc
