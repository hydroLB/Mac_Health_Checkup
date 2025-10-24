from diagnostics.logging_utils import logger
from constants import CACHE_TTL, MODEL_RE
from utils import regex_extract_str, c_to_f, system_profiler_out, classify_device, na

# Shared regex helpers
from utils import (
    safe_match as regex_safe_match,
    safe_findall as regex_safe_findall,
    hz_from_text as regex_hz_from_text,
)

import time
import re
from typing import Any, Dict, List, Optional, Tuple, ClassVar
import abc

DEVICE_SUMMARY_MAX_LINES: int = 8
USB_INDENT_SPACES: int = 4
NVME_BYTES_PER_DU: float = 512_000.0  # NVMe spec: one Data Unit = 512,000 bytes
DECIMAL_K: float = 1000.0
UNKNOWN_TOKENS: tuple[str, ...] = ("?", "Unknown")


class DiagnosticSection(abc.ABC):
    """
    All ‘section’ classes inherit this.  Gives you:
      • automatic stale-data caching
      • identical .fetch() public signature across files
    """

    _cache: ClassVar[Dict[str, Tuple[float, Dict[str, Any]]]] = {}

    @classmethod
    def _cached(cls, key: str) -> Dict[str, Any] | None:
        ts, value = cls._cache.get(key, (0, {}))
        return value if (time.time() - ts) < CACHE_TTL else None

    @classmethod
    def _remember(cls, key: str, value: Dict[str, Any]) -> None:
        cls._cache[key] = (time.time(), value)

    # ------------------------------------------------------------------
    @classmethod
    def fetch(cls) -> Dict[str, Any]:
        """Template Method—don’t touch in children."""
        cached = cls._cached(cls.__name__)
        if cached:
            return cached
        data = cls._gather()
        cls._remember(cls.__name__, data)
        return data

    # Every concrete file implements this:
    @classmethod
    @abc.abstractmethod
    def debug_msg(cls, component: str, msg: str) -> None:
        """
        Standardized, concise debug log wrapper for all diagnostics sections and helpers.
        """
        try:
            logger.debug(f"[{component}] {msg}")
        except Exception:
            pass

    @classmethod
    @abc.abstractmethod
    def log_exc(cls, component: str, err: Exception) -> None:
        """
        Standardized exception logging for diagnostics sections and shared utilities.
        """
        try:
            logger.exception(f"[{component}] Exception: {err}")
        except Exception:
            pass

    #
    # ── Utility Functions (regex, parsing, formatting, safety) ──────────────
    # Shared internal helpers -------------------------------------------------
    @classmethod
    def _conversion(cls, val: Any, caster: callable) -> Optional[Any]:
        """
        Internal helper for numeric conversion used by both safe_float and safe_int.
        Attempts to convert *val* using the supplied *caster* (e.g., float or int).
        Returns None upon failure instead of raising an exception.
        """
        try:
            # Fast‑path when the value is already numeric.
            if isinstance(val, (int, float)):
                return caster(val)
            # Handle bool explicitly when int conversion is requested.
            if isinstance(val, bool) and caster is int:
                return int(val)
            s: str = str(val).strip() if val is not None else ""
            return caster(s) if s else None
        except Exception:
            return None

    @classmethod
    @abc.abstractmethod
    def safe_float(cls, val: Any) -> Optional[float]:
        """
        Safely convert val to float, or return None if not possible.
        Used across diagnostics sections for tolerant numeric parsing.
        """
        return cls._conversion(val, float)

    @classmethod
    @abc.abstractmethod
    def safe_int(cls, val: Any) -> Optional[int]:
        """
        Safely convert val to int, or return None if not possible.
        Used across diagnostics sections for tolerant integer parsing.
        """
        return cls._conversion(val, int)

    @classmethod
    @abc.abstractmethod
    def fmt_percent(cls, val: Optional[float]) -> str:
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

    @classmethod
    @abc.abstractmethod
    def _bytes_unit(cls, n: float) -> tuple[float, str]:
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

    @classmethod
    @abc.abstractmethod
    def fmt_bytes(cls, num: Any) -> str:
        """
        Human friendly decimal (10^3) bytes.
        Used for SSD lifetime/write stats and any size reporting.
        """
        v = cls.safe_float(num)
        if v is None:
            return str(num) if num is not None else "?"
        n, unit = cls._bytes_unit(v)
        if n >= 100:
            return f"{n:.0f} {unit}"
        if n >= 10:
            return f"{n:.1f} {unit}"
        return f"{n:.2f} {unit}"

    @classmethod
    @abc.abstractmethod
    def fmt_temp_c(cls, val: Any) -> str:
        """
        Format a temperature value as a string in Celsius, or '?' if not available.
        Used for SSD and sensor diagnostics.
        """
        v = cls.safe_float(val)
        return f"{v:.0f}°C" if v is not None else "?"

    @classmethod
    @abc.abstractmethod
    # --- Table rendering helpers ---
    def calc_col_widths(cls, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> tuple[int, ...]:
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

    @classmethod
    @abc.abstractmethod
    def render_table_parts(cls, headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> tuple[str, str]:
        """
        Return (header_line, body_text) for a monospace table.
        Used for CLI and debug table rendering in multiple diagnostics.
        """
        widths = cls.calc_col_widths(headers, rows)
        fmt_row = "  ".join(f"{{:<{w}}}" for w in widths)
        header_line = fmt_row.format(*headers)
        sep_line = "-" * len(header_line)
        body_lines = [fmt_row.format(*r) for r in rows]
        return header_line + "\n" + sep_line, "\n".join(body_lines)

    #
    # ── Display refresh rate parsing utility ─────────────────────────────
    @classmethod
    @abc.abstractmethod
    def hz_from_text(cls, s: str) -> Optional[str]:
        """
        Extract a display refresh rate string (e.g., '60Hz') from arbitrary text.
        Used by display diagnostics and helpers.
        """
        return regex_hz_from_text(s)

    @classmethod
    @abc.abstractmethod
    def dedupe_strings(cls, seq: List[str]) -> List[str]:
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

    @classmethod
    @abc.abstractmethod
    def classify_and_dedupe(cls, names: List[str]) -> List[str]:
        """
        Classify and deduplicate a list of device names.
        Used by multiple diagnostics sections for device lists.
        """
        return cls.dedupe_strings([classify_device(n) for n in names])

    @classmethod
    @abc.abstractmethod
    def fan_status_string(cls, fans: List[Dict[str, Any]]) -> str:
        """
        Compose a summary status string from a list of fan dicts.
        Used by FanDiagnostics and related helpers.
        """
        if not fans:
            return "Unknown"
        return " | ".join(f"{f['name']}: {f['rpm']} RPM" for f in fans if 'name' in f and 'rpm' in f)

    @classmethod
    @abc.abstractmethod
    def smartctl_temperature_str(cls, out: str) -> str:
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
    @classmethod
    @abc.abstractmethod
    def safe_match(cls, pattern: re.Pattern[str], text: str) -> Optional[re.Match[str]]:
        """
        Safe wrapper around pattern.search(text); logs and returns None on error.
        Used throughout diagnostics for robust regex extraction.
        """
        return regex_safe_match(pattern, text)

    @classmethod
    @abc.abstractmethod
    def _safe_findall(cls, pattern: re.Pattern[str], text: str) -> List[str]:
        """
        Safe wrapper around pattern.findall(text); logs and returns [] on error.
        Used throughout diagnostics for robust regex extraction.
        """
        return regex_safe_findall(pattern, text)

    @classmethod
    @abc.abstractmethod
    def nearest_fan_name(cls, stack: List[Tuple[int, str]]) -> Optional[str]:
        """
        Find the most recent fan name in a stack of (indent, name) pairs.
        Used by FanDiagnostics to label unnamed fans.
        """
        for _, name in reversed(stack):
            if "fan" in name.lower():
                return name.strip()
        return None

    @classmethod
    @abc.abstractmethod
    def get_model_identifier(cls) -> Optional[str]:
        """
        Retrieve the Mac model identifier string using system_profiler.
        Used by FanDiagnostics and other sections for model-specific logic.
        """
        try:
            sysout, _ = system_profiler_out("SPHardwareDataType", "General")
            if not sysout:
                return None
            m = cls._safe_match(MODEL_RE, sysout)
            return m.group(1).strip() if m else None
        except Exception as exc:
            cls.debug_msg("ModelId", f"fetch failed: {exc}")
            return None


# Re-export DiagnosticSection class-methods as plain functions
safe_match = DiagnosticSection.safe_match
fmt_percent = DiagnosticSection.fmt_percent
fmt_bytes = DiagnosticSection.fmt_bytes
nearest_fan_name = DiagnosticSection.nearest_fan_name
smartctl_temperature_str = DiagnosticSection.smartctl_temperature_str
get_model_identifier = DiagnosticSection.get_model_identifier
fan_status_string = DiagnosticSection.fan_status_string
debug_msg = DiagnosticSection.debug_msg
log_exc = DiagnosticSection.log_exc
classify_and_dedupe = DiagnosticSection.classify_and_dedupe
dedupe_strings = DiagnosticSection.dedupe_strings
