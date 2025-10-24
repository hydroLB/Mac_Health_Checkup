"""
Mac Health Diagnostics Subsystem

Last updated: 2025-07

Overview
--------
This module defines the diagnostics layer for the Mac Health Dashboard.
Each diagnostics class provides a 'fetch()' method that acts as a section builder,
returning a dict of summary and raw fields suitable for row/section rendering in
the GUI, CLI, or other reporting systems.

Design Conventions
------------------
- All fetch() results are normalized dicts with summary, details, and raw output keys.
- Utilities are shared at module level for formatting, parsing, and table rendering.
- Logging is standardized via debug_msg/log_exc for consistent, robust diagnostics.

Sections
--------
  1. Imports & Logging
  2. Module Constants
  3. Utility Functions (regex, parsing, formatting, safety)
  4. BatteryDiagnostics
  5. SSDDiagnostics
  6. FanDiagnostics
  7. DisplayDiagnostics
  8. DeviceScanner
  9. PortsDiagnostics
 10. InputDiagnostics
 11. GeneralDiagnostics
"""

#

#
# ── stdlib ───────────────────────────────────────────────────────────
from __future__ import annotations
import logging
import platform
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Final, Iterable
import re as _re

#
# ── intra-project ────────────────────────────────────────────────────
from constants import (
    CACHE_TTL,
    USE_SUDO,
    FAN_NAME_MAP,
    DEBUG_LOG_PREFIX,
)
from utils import (  # big helper toolkit
    c_to_f,
    classify_by_ids,
    classify_device,
    _TB_IGNORES,
    na,
    regex_extract_float,
    regex_extract_int,
    regex_extract_str,
    safe_run,
    system_profiler_out,
    update_result_with_defaults,
)

#
# ── Logging ───────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# Configure logging format once, using constants.DEBUG_LOG_PREFIX if available
_def_log_configured: bool = False

# Prefer a shared logging bootstrap from logging_utils.py; fallback locally if missing
try:
    from logging_utils import configure_logging_once as _configure_logger_once  # type: ignore
except Exception:
    def _configure_logger_once() -> None:  # fallback local bootstrap
        global _def_log_configured
        if _def_log_configured:
            return
        root = logging.getLogger()
        if root.handlers:
            _def_log_configured = True
            return
        try:
            prefix = DEBUG_LOG_PREFIX
            fmt_prefix = (
                prefix.replace("{timestamp}", "%(asctime)s")
                .replace("{level}", "%(levelname)s")
                .replace("{context}", " %(name)s")
            )
            fmt = f"{fmt_prefix} %(message)s"
        except Exception:
            fmt = "[%(asctime)s %(levelname)s %(name)s] %(message)s"
        logging.basicConfig(level=logging.INFO, format=fmt)
        _def_log_configured = True

# Run once at import time
_configure_logger_once()

# ── UI, Layout, and Misc Constants ──────────────────────────────
DEVICE_SUMMARY_MAX_LINES: int = 8
USB_INDENT_SPACES: int = 4
NVME_BYTES_PER_DU: float = 512_000.0  # NVMe spec: one Data Unit = 512,000 bytes
DECIMAL_K: float = 1000.0
UNKNOWN_TOKENS: tuple[str, ...] = ("?", "Unknown")

# ── module constants ─────────────────────────────────────────────────
ISTATS_TIMEOUT: Final[int] = 5
FAN_SPEED_RE: Final[re.Pattern[str]] = re.compile(r'^\s+Fan Speed:\s*(\d+)\s*RPM?', re.IGNORECASE)
FAN_HEADER_RE: Final[re.Pattern[str]] = re.compile(r'^(\s+)([^:\n]+):\s*$')
FAN_SPEED_INLINE_RE: Final[re.Pattern[str]] = re.compile(r'Fan Speed:\s*(\d+)\s*RPM?', re.IGNORECASE)
USB_VENDOR_PRODUCT_RE: Final[re.Pattern[str]] = re.compile(
    r'"idVendor" = 0x([0-9a-fA-F]+).*?"idProduct" = 0x([0-9a-fA-F]+)', re.DOTALL
)
USB_PRODUCT_NAME_RE: Final[re.Pattern[str]] = re.compile(r'"USB Product Name" = "([^"]+)"')
USB_PRODUCT_LINE_RE: Final[re.Pattern[str]] = re.compile(r'Product Name:\s*(.+)', re.IGNORECASE)
BT_CONNECTED_NAME_RE: Final[re.Pattern[str]] = re.compile(r'^\s+(.+?):\s+Connected: Yes', re.MULTILINE)
NETWORK_HARDWARE_RE: Final[re.Pattern[str]] = re.compile(r'Hardware:\s+(.+)')
DISPLAY_NAME_RE: Final[re.Pattern[str]] = re.compile(r'^\s{8,}([^\n:]+):\s*$', re.MULTILINE)
DISPLAY_RES_RE: Final[re.Pattern[str]] = re.compile(r'^\s{12,}Resolution:\s*(.+)$', re.MULTILINE)
DISPLAY_CONN_RE: Final[re.Pattern[str]] = re.compile(r'^\s{12,}Connection Type:\s*(.+)$', re.MULTILINE)
DISPLAY_BUILTIN_RE: Final[re.Pattern[str]] = re.compile(r'^\s{12}Built-?In:\s*Yes\b', re.MULTILINE | re.IGNORECASE)
SERIAL_RE: Final[re.Pattern[str]] = re.compile(r"Serial Number.*?: (.+)")

MODEL_RE: Final[re.Pattern[str]] = re.compile(r"Model Identifier: (.+)")

# Additional module constants
INPUT_KEYWORD_MAP: Final[dict[str, str]] = {
    "keyboard" : "Keyboard",
    "trackpad" : "Trackpad",
    "mouse"    : "Mouse",
    "touch bar": "Touch Bar",
}


def debug_msg(component: str, msg: str) -> None:
    """
    Standardized, concise debug log wrapper for all diagnostics sections and helpers.
    """
    try:
        logger.debug(f"[{component}] {msg}")
    except Exception:
        pass


def log_exc(component: str, err: Exception) -> None:
    """
    Standardized exception logging for diagnostics sections and shared utilities.
    """
    try:
        logger.exception(f"[{component}] Exception: {err}")
    except Exception:
        pass


#
# ── Utility Functions (regex, parsing, formatting, safety) ──────────────

def safe_float(val: Any) -> Optional[float]:
    """
    Safely convert val to float, or return None if not possible.
    Used across diagnostics sections for tolerant numeric parsing.
    """
    try:
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip() if val is not None else ""
        return float(s) if s else None
    except Exception:
        return None


def safe_int(val: Any) -> Optional[int]:
    """
    Safely convert val to int, or return None if not possible.
    Used across diagnostics sections for tolerant integer parsing.
    """
    try:
        if isinstance(val, bool):
            return int(val)
        if isinstance(val, int):
            return val
        if isinstance(val, float):
            return int(val)
        s = str(val).strip() if val is not None else ""
        return int(s) if s else None
    except Exception:
        return None


def fmt_percent(val: Optional[float]) -> str:
    """
    Format a 0–1 or 0–100 value as a whole-percent string.
    Used in multiple diagnostics sections for health/lifetime summaries.
    """
    try:
        if val is None:
            return "?"
        pct = val * 100.0 if 0.0 <= val <= 1.0 else val
        return f"{pct:.0f}%"
    except Exception:
        return "?"


def _bytes_unit(n: float) -> tuple[float, str]:
    """
    Helper for fmt_bytes: returns (scaled_value, unit_label) for decimal units.
    Used for SSD and other storage diagnostics.
    """
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while n >= DECIMAL_K and idx < len(units) - 1:
        n /= DECIMAL_K
        idx += 1
    return n, units[idx]


def fmt_bytes(num: Any) -> str:
    """
    Human friendly decimal (10^3) bytes.
    Used for SSD lifetime/write stats and any size reporting.
    """
    v = safe_float(num)
    if v is None:
        return str(num) if num is not None else "?"
    n, unit = _bytes_unit(v)
    if n >= 100:
        return f"{n:.0f} {unit}"
    if n >= 10:
        return f"{n:.1f} {unit}"
    return f"{n:.2f} {unit}"


def fmt_temp_c(val: Any) -> str:
    """
    Format a temperature value as a string in Celsius, or '?' if not available.
    Used for SSD and sensor diagnostics.
    """
    v = safe_float(val)
    return f"{v:.0f}°C" if v is not None else "?"


# --- Table rendering helpers ---
def calc_col_widths(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> tuple[int, ...]:
    """
    Return the max width for each column, given headers and rows.
    Used in CLI table rendering for diagnostics output.
    """
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(cell))
    return tuple(widths)


def render_table_parts(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> tuple[str, str]:
    """
    Return (header_line, body_text) for a monospace table.
    Used for CLI and debug table rendering in multiple diagnostics.
    """
    widths = calc_col_widths(headers, rows)
    fmt_row = "  ".join(f"{{:<{w}}}" for w in widths)
    header_line = fmt_row.format(*headers)
    sep_line = "-" * len(header_line)
    body_lines = [fmt_row.format(*r) for r in rows]
    return header_line + "\n" + sep_line, "\n".join(body_lines)


#
# ── Display refresh rate parsing utility ─────────────────────────────


def hz_from_text(s: str) -> Optional[str]:
    """
    Extract a display refresh rate string (e.g., '60Hz') from arbitrary text.
    Used by display diagnostics and helpers.
    """
    m = _re.search(r"@\s*(\d+(?:\.\d+)?)\s*Hz", s, flags=_re.I)
    if not m:
        m = _re.search(r"(\d+(?:\.\d+)?)\s*Hz", s, flags=_re.I)
    if not m:
        return None
    val = m.group(1)
    if val.endswith(".00"):
        val = val[:-3]
    return f"{val}Hz"


def _classify_and_dedupe(names: List[str]) -> List[str]:
    """
    Classify and deduplicate a list of device names.
    Used by multiple diagnostics sections for device lists.
    """
    return _dedupe_strings([classify_device(n) for n in names])


def _fan_status_string(fans: List[Dict[str, Any]]) -> str:
    """
    Compose a summary status string from a list of fan dicts.
    Used by FanDiagnostics and related helpers.
    """
    if not fans:
        return "Unknown"
    return " | ".join(f"{f['name']}: {f['rpm']} RPM" for f in fans if 'name' in f and 'rpm' in f)


def _smartctl_temperature_str(out: str) -> str:
    """
    Return temperature string like "35°C / 95°F" or "N/A" if missing.
    Used by SSDDiagnostics and other SMART-based diagnostics.
    """
    temp_c_str = regex_extract_str(out, rf"{re.escape('Temperature')}:\s+([^\n]+)")
    try:
        m = re.search(r"\d+", temp_c_str) if temp_c_str else None
        temp_c = int(m.group(0)) if m else None
    except Exception:
        temp_c = None
    temp_f = c_to_f(temp_c)
    if temp_c is not None and temp_f is not None:
        return f"{temp_c}°C / {temp_f}°F"
    return na(None)


#
# ── Miscellaneous Utilities (regex safety, dedupe, model lookup) ─────────────
def _safe_match(pattern: re.Pattern[str], text: str) -> Optional[re.Match[str]]:
    """
    Safe wrapper around pattern.search(text); logs and returns None on error.
    Used throughout diagnostics for robust regex extraction.
    """
    try:
        return pattern.search(text)
    except Exception as exc:
        debug_msg("Regex", f"search failed: {exc}")
        return None


def _safe_findall(pattern: re.Pattern[str], text: str) -> List[str]:
    """
    Safe wrapper around pattern.findall(text); logs and returns [] on error.
    Used throughout diagnostics for robust regex extraction.
    """
    try:
        return [m for m in pattern.findall(text)]  # type: ignore[return-value]
    except Exception as exc:
        debug_msg("Regex", f"findall failed: {exc}")
        return []


def _dedupe_strings(seq: List[str]) -> List[str]:
    """
    Deduplicate a list of strings while preserving order.
    Used by device, input, and port diagnostics for clean UI lists.
    """
    seen: set[str] = set()
    out: List[str] = []
    for s in seq:
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _nearest_fan_name(stack: List[Tuple[int, str]]) -> Optional[str]:
    """
    Find the most recent fan name in a stack of (indent, name) pairs.
    Used by FanDiagnostics to label unnamed fans.
    """
    for _, name in reversed(stack):
        if "fan" in name.lower():
            return name.strip()
    return None


def _get_model_identifier() -> Optional[str]:
    """
    Retrieve the Mac model identifier string using system_profiler.
    Used by FanDiagnostics and other sections for model-specific logic.
    """
    try:
        sysout, _ = system_profiler_out("SPHardwareDataType", "General")
        if not sysout:
            return None
        m = _safe_match(MODEL_RE, sysout)
        return m.group(1).strip() if m else None
    except Exception as exc:
        debug_msg("ModelId", f"fetch failed: {exc}")
        return None


#
# ── Diagnostics Section Builders ────────────────────────────────────────
# Each major diagnostics class below provides a fetch() method that acts as a
# 'section builder' for the main dashboard. These fetch methods return
# dictionaries with normalized keys suitable for row/section rendering in
# downstream code (UI or CLI).
#
# The output from each fetch() is always a dict, usually containing:
# - a human-readable summary ("health_text", "status", etc)
# - raw output ("raw")
# - and detailed, structured values (counts, percents, device lists, etc)
#
# This convention allows the GUI and other consumers to assemble sections
# of the dashboard by composing fetch() results directly into tables/rows.

class BatteryDiagnostics:
    """
    Battery health and cycle diagnostics section builder.
    Produces a row/section summarizing battery health, cycle count, and state.
    """

    @staticmethod
    def fetch() -> Dict[str, Any]:
        """
        Fetch battery health info and return a normalized section dict.

        Returns:
            Dict[str, Any] with keys:
                - "present": bool
                - "percent_health": float or None
                - "cycle_count": int or None
                - "health_text": str (row summary)
                - "raw": str (source)
        """
        result: Dict[str, Any] = {}
        defaults = {
            "present"       : False,
            "percent_health": None,
            "cycle_count"   : None,
            "health_text"   : "Battery Not Found",
            "raw"           : ""
        }
        try:
            out, err = safe_run(["ioreg", "-r", "-c", "AppleSmartBattery"], "Battery")
            if not out:
                debug_msg("BatteryDiagnostics", f"No battery info found; err={err}")
                result["health_text"] = f"Not accessible ({err})"
                update_result_with_defaults(result, defaults)
                return result
            result["raw"] = out
            dc = regex_extract_int(out, r'"DesignCapacity" = (\d+)')
            mc = regex_extract_int(out, r'"AppleRawMaxCapacity" = (\d+)')
            cc = regex_extract_int(out, r'"CycleCount" = (\d+)')
            if dc and mc:
                percent = mc / dc * 100
                result.update({
                    "present"       : True,
                    "percent_health": percent,
                    "cycle_count"   : cc,
                    "health_text"   : f"{percent:.1f}% ({mc}/{dc}) | Cycles: {cc}"
                })
            else:
                debug_msg("BatteryDiagnostics", "Battery info incomplete (missing dc or mc)")
                result["health_text"] = "Battery info incomplete"
            update_result_with_defaults(result, defaults)
            return result
        except Exception as exc:
            log_exc("BatteryDiagnostics", exc)
            result["health_text"] = "Battery diagnostics failed"
            update_result_with_defaults(result, defaults)
            return result


class SSDDiagnostics:
    """
    SSD health and lifetime diagnostics section builder.
    Produces a row/section summarizing SMART health, lifetime writes, and stats.
    """

    @staticmethod
    def fetch(require_sudo: bool = USE_SUDO) -> Dict[str, Any]:
        """
        Fetch SSD SMART info and return a normalized section dict.

        Args:
            require_sudo (bool): Permission to escalate to sudo **after** a plain attempt
                fails. When False, the command will never use sudo.

        Returns:
            Dict[str, Any] with keys like:
                - "percent_left": float or None
                - "health_text": str (row summary)
                - "data_written": float or None
                - "raw": str (source)
                - plus various SSD statistics
        """
        result: Dict[str, Any] = {}
        defaults = {
            "percent_left": None,
            "health_text" : "Unavailable",
            "data_written": None,
            "raw"         : ""
        }
        # Always run plain first; allow sudo escalation only if permitted
        try:
            out, err = safe_run(["smartctl", "-a", "/dev/disk0"], "SSD", allow_sudo=require_sudo)
            if not out:
                debug_msg("SSDDiagnostics", f"No SMART info found; err={err}")
                result["health_text"] = f"Not accessible ({err})"
                update_result_with_defaults(result, defaults)
                return result
            result["raw"] = out
            percent_used = regex_extract_int(out, r'Percentage Used:\s*(\d+)%')
            written = regex_extract_float(out, r'Data Units Written:\s+[\d,]+\s*\[([0-9.]+) TB]')
            read = regex_extract_float(out, r'Data Units Read:\s+[\d,]+\s*\[([0-9.]+) TB]')
            result["data_read"] = read
            # Additional fields from smartctl output
            result["firmware"] = regex_extract_str(out, rf"{re.escape('Firmware Version')}:\s+([^\n]+)")
            result["available_spare"] = regex_extract_int(out, rf"{re.escape('Available Spare')}:\s+([^\n]+)")
            result["spare_threshold"] = regex_extract_int(out, rf"{re.escape('Available Spare Threshold')}:\s+([^\n]+)")
            result["power_cycles"] = regex_extract_int(out, rf"{re.escape('Power Cycles')}:\s+([^\n]+)")
            result["power_on_hours"] = regex_extract_int(out, rf"{re.escape('Power On Hours')}:\s+([^\n]+)")
            result["unsafe_shutdowns"] = regex_extract_int(out, rf"{re.escape('Unsafe Shutdowns')}:\s+([^\n]+)")
            result["media_errors"] = regex_extract_int(out,
                                                       rf"{re.escape('Media and Data Integrity Errors')}:\s+([^\n]+)")
            result["error_log_entries"] = regex_extract_int(out,
                                                            rf"{re.escape(
                                                                'Error Information Log Entries')}:\s+([^\n]+)")
            result["host_read_commands"] = regex_extract_int(out, rf"{re.escape('Host Read Commands')}:\s+([^\n]+)")
            result["host_write_commands"] = regex_extract_int(out, rf"{re.escape('Host Write Commands')}:\s+([^\n]+)")
            result["controller_busy_time"] = regex_extract_int(out, rf"{re.escape('Controller Busy Time')}:\s+([^\n]+)")
            if percent_used is not None:
                percent_left = 100 - percent_used
                est_life_tb = None
                if written is not None and percent_used > 0:
                    est_life_tb = written * (100 / percent_used)
                result.update({
                    "percent_left": percent_left,
                    "data_written": written,
                    "health_text" : (
                            f"{fmt_percent(percent_left)} left | "
                            f"{fmt_bytes(written * 1e12) if written is not None else '?'} written"
                            + (f" | Est. lifetime: {est_life_tb:.1f} TB" if est_life_tb else "")
                    )
                })
            else:
                debug_msg("SSDDiagnostics", "SMART info missing (no percent_used)")
                result["health_text"] = "SMART info missing"
            update_result_with_defaults(result, defaults)
            # Compose a detailed string for the tooltip
            result["detailed"] = (
                f"Firmware: {na(result.get('firmware'))}\n"
                f"Available Spare: {fmt_percent(result.get('available_spare'))} "
                f"(Threshold: {fmt_percent(result.get('spare_threshold'))})\n"
                f"Power Cycles: {na(result.get('power_cycles'))}\n"
                f"Power On Hours: {na(result.get('power_on_hours'))}\n"
                f"Unsafe Shutdowns: {na(result.get('unsafe_shutdowns'))}\n"
                f"Media/Data Integrity Errors: {na(result.get('media_errors'))}\n"
                f"Error Log Entries: {na(result.get('error_log_entries'))}\n"
                f"Host Read Commands: {na(result.get('host_read_commands'))}\n"
                f"Host Write Commands: {na(result.get('host_write_commands'))}\n"
                f"Controller Busy Time: "
                f"{na(result.get('controller_busy_time'))} min"
            )
            # --- BEGIN TEMPERATURE LOGIC ---
            temp_str = _smartctl_temperature_str(out)
            # --- END TEMPERATURE LOGIC ---
            result["detailed_short"] = (
                f"Firmware: {na(result.get('firmware'))},\n"
                f"Temperature: {temp_str},\n"
                f"Read: {fmt_bytes(read * 1e12) if read is not None else na(result.get('data_read'))},\n"
                f"Power Cycles: {na(result.get('power_cycles'))},\n"
                f"POH: {na(result.get('power_on_hours'))}h,\n"
                f"Unsafe Shutdowns: {na(result.get('unsafe_shutdowns'))},\n"
                f"Errors: {na(result.get('media_errors'))}"
            )
            return result
        except Exception as exc:
            log_exc("SSDDiagnostics", exc)
            result["health_text"] = "SSD diagnostics failed"
            update_result_with_defaults(result, defaults)
            return result


class FanDiagnostics:
    """
    Fan status diagnostics section builder.
    Produces a row/section summarizing current fan speeds and labels.
    """

    @staticmethod
    def _parse_fan_speeds(text: str) -> List[str]:
        # Parse all fan speeds from system_profiler output.
        return FAN_SPEED_INLINE_RE.findall(text)

    @staticmethod
    def _parse_fans_with_names(text: str) -> List[Tuple[Optional[str], str]]:
        """
        Parse system_profiler SPPowerDataType output into (name, rpm) pairs.
        Name may be None if macOS doesn't label that fan explicitly.
        """
        pairs: List[Tuple[Optional[str], str]] = []
        lines = text.splitlines()
        stack: List[Tuple[int, str]] = []  # (indent, name)
        for ln in lines:
            m_hdr = FAN_HEADER_RE.match(ln)
            if m_hdr:
                indent = len(m_hdr.group(1))
                name = m_hdr.group(2).strip()
                while stack and stack[-1][0] >= indent:
                    stack.pop()
                stack.append((indent, name))
                continue
            m_spd = FAN_SPEED_RE.match(ln)
            if m_spd:
                rpm = m_spd.group(1)
                nm = _nearest_fan_name(stack)
                pairs.append((nm, rpm))
        if not pairs:
            for rpm in FAN_SPEED_INLINE_RE.findall(text):
                pairs.append((None, rpm))
        return pairs

    @staticmethod
    def _get_fan_speeds_istats() -> List[Tuple[Optional[str], str]]:
        # First try rich, named output
        out, _ = safe_run(["istats", "fan"], context="FanIStats", timeout=ISTATS_TIMEOUT)
        pairs: List[Tuple[Optional[str], str]] = []
        if out:
            for ln in out.splitlines():
                s = ln.strip()
                if not s:
                    continue
                if re.search(r'^Total\s+fans', s, flags=re.IGNORECASE):
                    continue
                m = re.search(r'^([^:]+):\s*(\d+)\s*RPM', s, flags=re.IGNORECASE)
                if m:
                    name = m.group(1).strip()
                    rpm = m.group(2)
                    pairs.append((name, rpm))
                    continue
                m2 = re.search(r'^Fan\s*(\d+)\s*speed:\s*(\d+)', s, flags=re.IGNORECASE)
                if m2:
                    idx, rpm = m2.group(1), m2.group(2)
                    pairs.append((f"Fan {idx}", rpm))
        if pairs:
            return pairs
        # Fallback: value-only
        out2, _ = safe_run(["istats", "fan", "--value-only"], context="FanIStats", timeout=ISTATS_TIMEOUT)
        if not out2:
            return []
        nums = [ln.strip() for ln in out2.splitlines() if ln.strip().isdigit()]
        if len(nums) <= 1:
            return []
        rpms = nums[1:]
        return [(None, rpm) for rpm in rpms]

    @staticmethod
    def _apply_fan_defaults(pairs: List[Tuple[Optional[str], str]], model: Optional[str] = None) -> List[
        Dict[str, Any]]:
        fans: List[Dict[str, Any]] = []
        count = len(pairs)
        model_id = model or _get_model_identifier()
        names = FanDiagnostics._suggest_names(count, model_id)
        for idx, (name, rpm_str) in enumerate(pairs, start=1):
            try:
                rpm = int(rpm_str)
            except Exception:
                continue
            raw_name = (name.strip() if isinstance(name, str) else None)
            if raw_name and re.fullmatch(r'(?i)fan\s*\d+', raw_name):
                raw_name = None
            label = raw_name or (names[idx - 1] if idx - 1 < len(names) else f"Fan {idx}")
            fans.append({"name": label, "rpm": rpm})
        return fans

    @staticmethod
    def _suggest_names(count: int, model: Optional[str]) -> list[str]:
        model_id = (model or "").strip()
        for pattern, names in FAN_NAME_MAP:
            if re.match(pattern, model_id):
                if count <= len(names):
                    return names[:count]
                extra = [f"Fan {i}" for i in range(len(names) + 1, count + 1)]
                return names + extra
        if count <= 0:
            return []
        if count == 1:
            return ["Main fan"]
        if count == 2:
            return ["Left side", "Right side"]
        if count == 3:
            return ["Left", "Middle", "Right"]
        return [f"Fan {i}" for i in range(1, count + 1)]

    @staticmethod
    def fetch() -> Dict[str, Any]:
        """
        Fetch fan info and return a normalized section dict.

        Returns:
            Dict[str, Any] with keys:
                - "status": str (row summary, e.g. "Left Fan: 1200 RPM | ...")
                - "fans": List[Dict[str, Any]] (each with "name" and "rpm")
                - "raw": str (source)
        If macOS provides no fan details (common on some Apple Silicon),
        returns an empty list with a friendly status message.
        """
        try:
            out, err = system_profiler_out("SPPowerDataType", "Fan")
            result: Dict[str, Any] = {"status": "Unknown", "fans": [], "raw": out or ""}

            pairs: List[Tuple[Optional[str], str]] = []
            if out:
                pairs = FanDiagnostics._parse_fans_with_names(out)

            if not pairs:
                debug_msg("FanDiagnostics", "No fan pairs found in system_profiler, trying istats fallback")
                pairs = FanDiagnostics._get_fan_speeds_istats()

            fans = FanDiagnostics._apply_fan_defaults(pairs)
            result["fans"] = fans

            if fans:
                result["status"] = _fan_status_string(fans)
            else:
                debug_msg("FanDiagnostics", f"No fans found; err={err}")
                result["status"] = f"Not accessible ({err})" if err else "No Fan Info (Apple Silicon normal)"

            return result
        except Exception as exc:
            log_exc("FanDiagnostics", exc)
            return {"status": "Fan diagnostics failed", "fans": [], "raw": ""}


class DisplayDiagnostics:
    @staticmethod
    def _conn_group(label: Optional[str]) -> str:
        l = (label or "").strip().lower()
        if not l:
            return "other"
        if l.startswith("wireless") or "airplay" in l or "sidecar" in l:
            return "wireless"
        if l == "internal":
            return "internal"
        if l == "wired" or l in ("hdmi", "displayport", "usb-c", "usb", "thunderbolt", "usb (displaylink)"):
            return "wired"
        return "other"

    @staticmethod
    def _group_connections(connections: list[str]) -> Dict[str, Any]:
        counts = {"wired": 0, "wireless": 0, "internal": 0, "other": 0}
        buckets: Dict[str, list[int]] = {k: [] for k in counts}
        for idx, c in enumerate(connections):
            g = DisplayDiagnostics._conn_group(c)
            if g not in counts:
                g = "other"
            counts[g] += 1
            buckets[g].append(idx)
        return {"counts": counts, "buckets": buckets}

    @staticmethod
    def _status_from_groups(total: int, groups: Dict[str, Any]) -> str:
        counts = groups.get("counts", {}) if isinstance(groups, dict) else {}
        wired = int(counts.get("wired", 0) or 0)
        wireless = int(counts.get("wireless", 0) or 0)
        internal = int(counts.get("internal", 0) or 0)
        return f"{total} display(s): {wired} wired, {wireless} wireless, {internal} internal"
    """
    Display name and resolution diagnostics section builder.
    Produces a row/section summarizing display names and resolutions.
    """

    @staticmethod
    def _normalize_connection(val: Optional[str]) -> Optional[str]:
        if not val:
            return None
        v = str(val).strip()
        low = v.lower()
        # Treat unknown/empty-like values as missing so we can fall back sanely
        if not v or low in ("unknown", "?", "n/a", "na") or low.strip("-–— ") == "":
            return None
        # Wireless first
        if "airplay" in low or "sidecar" in low:
            return "Wireless (AirPlay)"
        # Common wired transports
        if "displayport" in low or low == "dp":
            return "DisplayPort"
        if "thunderbolt" in low:
            return "Thunderbolt"
        if "usb-c" in low or "usbc" in low or ("usb" in low and "displaylink" not in low):
            return "USB-C" if ("usb-c" in low or "usbc" in low) else "USB"
        if "hdmi" in low:
            return "HDMI"
        if "displaylink" in low:
            return "USB (DisplayLink)"
        if "internal" in low or "built" in low:
            return "Internal"
        if "wired" in low:
            return "Wired"
        # Unknown value: return as-is to avoid overfitting
        return v

    @staticmethod
    def _parse_all_displays(text: str):
        names = [(m.group(1).strip(), m.start()) for m in DISPLAY_NAME_RE.finditer(text)]
        out = []
        for idx, (nm, pos) in enumerate(names):
            end = names[idx + 1][1] if idx + 1 < len(names) else len(text)
            sub = text[pos:end]
            # Resolution
            res_m = DISPLAY_RES_RE.search(sub)
            res = res_m.group(1).strip() if res_m else None
            # Built-in?
            is_builtin = bool(DISPLAY_BUILTIN_RE.search(sub))
            # Explicit connection value
            conn = None
            conn_m = DISPLAY_CONN_RE.search(sub)
            if conn_m:
                conn = DisplayDiagnostics._normalize_connection(conn_m.group(1))
                # Normalize unknowns to None so we prefer a sane fallback
                if isinstance(conn, str) and conn.lower() in ("unknown", "?", "n/a", "na"):
                    conn = None
            # Decide connection label
            if is_builtin:
                conn_label = "Internal"
            elif conn:
                conn_label = conn
            else:
                conn_label = "Wired"
            out.append((nm, res, conn_label))
        return out

    @staticmethod
    def _detail_string(name: str, res: Optional[str], conn: str) -> str:
        name_s = name.strip() if name else "Display"
        res_s = (res.strip() if isinstance(res, str) else "?") or "?"
        conn_s = conn.strip() if conn else "?"
        if res_s == "?":
            return f"{name_s} • {conn_s}"
        return f"{name_s} • {res_s} • {conn_s}"

    @staticmethod
    def fetch() -> Dict[str, Any]:
        """
        Fetch display info and return a normalized section dict.

        Returns:
            Dict[str, Any] with keys:
                - "names": List[str] (display names/resolutions)
                - "connections": List[str] (connection types)
                - "raw": str (source)
        """
        out, err = system_profiler_out("SPDisplaysDataType", "Display")
        if out:
            disp = DisplayDiagnostics._parse_all_displays(out)
            names = [f"{n} ({r})" if r else n for n, r, _c in disp] or ["Built-in/Unknown"]
            connections = [_c for _n, _r, _c in disp] or ["Internal"]
            details = [DisplayDiagnostics._detail_string(n, r, c) for n, r, c in disp]
            groups = DisplayDiagnostics._group_connections(connections)
            return DisplayDiagnostics._build_row_section(names, connections, details, groups, out)
        else:
            names = ["Unavailable"]
            connections = ["Wired"]
            disp = [("Unavailable", None, "Wired")]
            details = [DisplayDiagnostics._detail_string(n, r, c) for n, r, c in disp]
            groups = DisplayDiagnostics._group_connections(connections)
            return DisplayDiagnostics._build_row_section(names, connections, details, groups, out or out or "")

    @staticmethod
    def _build_row_section(
        names: list[str],
        connections: list[str],
        details: list[str],
        groups: Dict[str, Any],
        raw: str
    ) -> dict[str, Any]:
        total = len(names)
        status = DisplayDiagnostics._status_from_groups(total, groups)
        return {
            "names": names,
            "connections": connections,
            "details": details,
            "groups": groups,
            "status": status,
            "raw": raw,
        }

    @staticmethod
    def _parse_resolution(text: str) -> Optional[str]:
        # Extract display resolution from system_profiler output.
        m = _safe_match(re.compile(r'^\s*Resolution: (.+)', re.MULTILINE), text)
        return m.group(1).strip() if m else None

    @staticmethod
    def _parse_display_name(text: str) -> Optional[str]:
        # Extract display serial/model from system_profiler output.
        m = _safe_match(re.compile(r'^\s*Display Serial Number: (.+)', re.MULTILINE), text)
        return m.group(1).strip() if m else None


class DeviceScanner:
    """
    Unified, cached peripheral scanner for USB, Bluetooth, Thunderbolt and
    CDC-ECM network dongles.
    Used as a row/section builder for connected device lists.
    """
    _cache_ttl = CACHE_TTL
    _cache: Dict[str, Tuple[float, List[str]]] = {}

    # ─── cache helpers ──────────────────────────────────────────
    @staticmethod
    def _cached(key: str) -> Optional[List[str]]:
        entry = DeviceScanner._cache.get(key)
        if entry and time.time() - entry[0] < DeviceScanner._cache_ttl:
            return entry[1]
        return None

    @staticmethod
    def _store(key: str, devices: List[str]) -> None:
        DeviceScanner._cache[key] = (time.time(), devices)

    # ─── individual bus scanners ────────────────────────────────
    @staticmethod
    def scan_usb() -> List[str]:
        cached = DeviceScanner._cached("usb")
        if cached is not None:
            return cached
        out, _ = safe_run(["ioreg", "-p", "IOUSB", "-l"], "USBScan")
        devices: List[str] = []
        if out:
            pairs = USB_VENDOR_PRODUCT_RE.findall(out)
            for vend, prod in pairs:
                label = classify_by_ids(vend, prod)
                if label:
                    devices.append(label)
            names = USB_PRODUCT_NAME_RE.findall(out)
            devices.extend([classify_device(n) for n in names])
        devices = _classify_and_dedupe(devices)
        DeviceScanner._store("usb", devices)
        return devices

    @staticmethod
    def scan_bluetooth() -> List[str]:
        cached = DeviceScanner._cached("bt")
        if cached is not None:
            return cached
        out, _ = safe_run(["system_profiler", "SPBluetoothDataType"], "BTScan")
        names = BT_CONNECTED_NAME_RE.findall(out or "")
        devices = _classify_and_dedupe(names)
        DeviceScanner._store("bt", devices)
        return devices

    @staticmethod
    def _filter_tb_label(label: str) -> bool:
        """Return True if this Thunderbolt label should be kept (not ignored)."""
        try:
            low = label.lower().strip()
        except Exception:
            return False
        return not any(k in low for k in _TB_IGNORES)

    @staticmethod
    def _iter_tb_labels(text: str) -> Iterable[str]:
        """Yield Thunderbolt header labels from system_profiler output."""
        for line in text.splitlines():
            m = re.match(r'^\s{8,}([^\n:]+):\s*$', line)
            if not m:
                continue
            label = m.group(1).strip()
            if DeviceScanner._filter_tb_label(label):
                yield label

    # --- Replace DeviceScanner.scan_thunderbolt ---
    @staticmethod
    def scan_thunderbolt() -> List[str]:
        cached = DeviceScanner._cached("tb")
        if cached is not None:
            return cached
        out, _ = safe_run(["system_profiler", "SPThunderboltDataType"], "TBScan")
        if not out:
            return []
        names: List[str] = [classify_device(label) for label in DeviceScanner._iter_tb_labels(out)]
        DeviceScanner._store("tb", DeviceScanner._dedupe(names))
        return DeviceScanner._cached("tb") or []

    @staticmethod
    def scan_network() -> List[str]:
        cached = DeviceScanner._cached("net")
        if cached is not None:
            return cached
        out, _ = safe_run(["system_profiler", "SPNetworkDataType"], "NETScan")
        names = NETWORK_HARDWARE_RE.findall(out or "")
        devices = _classify_and_dedupe(names)
        DeviceScanner._store("net", devices)
        return devices

    # ─── public aggregate ───────────────────────────────────────
    @staticmethod
    def scan_all() -> List[str]:
        return DeviceScanner._dedupe(
            DeviceScanner.scan_usb()
            + DeviceScanner.scan_bluetooth()
            + DeviceScanner.scan_thunderbolt()
            + DeviceScanner.scan_network()
        )

    # ─── helpers ────────────────────────────────────────────────
    @staticmethod
    def _dedupe(seq: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for item in seq:
            if item and item not in seen:
                out.append(item)
                seen.add(item)
        return out


class PortsDiagnostics:
    """
    USB port device diagnostics section builder.
    Produces a row/section listing connected USB devices.
    """

    @staticmethod
    def _parse_usb_products(text: str) -> List[str]:
        """
        Extract and classify USB product names from raw system_profiler text.

        Returns:
            List[str]: De‑duplicated, order‑preserving list of friendly device
            labels suitable for UI presentation.
        """
        raw_names = re.findall(r'Product Name:\s*(.+)', text)
        friendly = [classify_device(n) for n in raw_names]
        return _dedupe_strings(friendly)

    @staticmethod
    def fetch() -> Dict[str, Any]:
        """
        Fetch connected USB device info and return a normalized section dict.

        Returns:
            Dict[str, Any] with keys:
                - "devices": List[str] (USB device labels)
                - "raw": str (source, always empty here)
        """
        try:
            devices = DeviceScanner.scan_usb()
            debug_msg("PortsDiagnostics", f"USB devices detected: {len(devices)}")
            return PortsDiagnostics._build_row_section(devices, "")
        except Exception as exc:
            log_exc("PortsDiagnostics", exc)
            return PortsDiagnostics._build_row_section([], "")

    @staticmethod
    def _build_row_section(devices: list[str], raw: str) -> dict[str, Any]:
        """Assemble the canonical output dict for PortsDiagnostics."""
        return {
            "devices": devices,
            "raw"    : raw,
        }


class InputDiagnostics:
    """
    Input device (keyboard/trackpad) diagnostics section builder.
    Produces a row/section listing discovered input devices.
    """

    @staticmethod
    def _parse_input_devices(text: str) -> List[str]:
        """
        Identify input peripherals using both explicit USB/HID product names
        and broader keyword heuristics, then classify them to user‑friendly
        labels.
        """
        found: List[str] = []

        # 1) Explicit product names reported by system_profiler / ioreg
        raw_products = re.findall(r'Product Name:\s*(.+)', text, flags=re.IGNORECASE)
        for prod in raw_products:
            friendly = classify_device(prod)
            found.append(friendly)

        # 2) Keyword fallback for built-in devices that may lack Product Name
        lower = text.lower()
        for key, label in INPUT_KEYWORD_MAP.items():
            if key in lower:
                found.append(label)

        return _dedupe_strings(found)

    @staticmethod
    def fetch() -> Dict[str, Any]:
        """
        Discover connected input devices and return a normalized section dict.

        Returns:
            Dict[str, Any] with keys:
                - "input_found": bool
                - "details": List[str] (device labels)
                - "raw": str (concatenated command outputs, trimmed)
        """
        try:
            commands = [
                ["system_profiler", "SPUSBDataType"],
                ["system_profiler", "SPUSBDataType", "-detailLevel", "full"],
                ["system_profiler", "SPHumanInterfaceDeviceDataType"],
                ["ioreg", "-p", "IOUSB", "-l"],
            ]

            combined_raw: List[str] = []
            detected: List[str] = []

            for idx, cmd in enumerate(commands, start=1):
                out, _ = safe_run(cmd, f"Input{idx}")
                if not out:
                    continue
                combined_raw.append(f"----- {' '.join(cmd)} -----\n{out}")
                detected = InputDiagnostics._parse_input_devices(out)
                if detected:
                    break  # Stop on first successful detection

            # Merge peripherals discovered through DeviceScanner (USB/Bluetooth/etc.)
            for dev in DeviceScanner.scan_all():
                if dev not in detected:
                    detected.append(dev)

            detected = _classify_and_dedupe(detected)
            return InputDiagnostics._build_row_section(
                bool(detected), detected, "\n\n".join(combined_raw).strip()
            )
        except Exception as exc:
            log_exc("InputDiagnostics", exc)
            return InputDiagnostics._build_row_section(False, [], "")

    @staticmethod
    def _build_row_section(input_found: bool, details: list[str], raw: str) -> dict[str, Any]:
        """
        Assemble the canonical output dict for InputDiagnostics.
        """
        return {
            "input_found": input_found,
            "details"    : details,
            "raw"        : raw,
        }


class GeneralDiagnostics:
    """
    General system info (model, serial, OS) section builder.
    Produces a row/section with identifying info for the Mac.
    """

    @staticmethod
    def _parse_serial(text: str) -> Optional[str]:
        m = _safe_match(SERIAL_RE, text)
        return m.group(1).strip() if m else None

    @staticmethod
    def _parse_model(text: str) -> Optional[str]:
        m = _safe_match(MODEL_RE, text)
        return m.group(1).strip() if m else None

    @staticmethod
    def fetch() -> Dict[str, Any]:
        """
        Fetch general hardware info and return a normalized section dict.

        Returns:
            Dict[str, Any] with keys:
                - "serial": str
                - "model": str
                - "os": str
        """
        sysout, _ = system_profiler_out("SPHardwareDataType", "General")
        uname = platform.uname()
        serial = GeneralDiagnostics._parse_serial(sysout or "") if sysout else None
        model = GeneralDiagnostics._parse_model(sysout or "") if sysout else None
        return {
            "serial": na(serial, UNKNOWN_TOKENS[1]),
            "model" : na(model, uname.machine),
            "os"    : f"{platform.system()} {platform.release()}",
        }
