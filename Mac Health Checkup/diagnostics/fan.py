from __future__ import annotations  # keep first if you already use it

# ── standard library ───────────────────────────────────────────────
import re
from typing import Any, Dict, List, Optional, Tuple, Final, NamedTuple

# ── internal diagnostics helpers ──────────────────────────────────
from utils import safe_run, system_profiler_out
from diagnostics.base import (
    nearest_fan_name,
    get_model_identifier,
    fan_status_string,
    debug_msg,
    log_exc,
)
from constants import FAN_NAME_MAP

ISTATS_TIMEOUT: Final[int] = 5
FAN_SPEED_RE: Final[re.Pattern[str]] = re.compile(r'^\s+Fan Speed:\s*(\d+)\s*RPM?', re.IGNORECASE)
FAN_HEADER_RE: Final[re.Pattern[str]] = re.compile(r'^(\s+)([^:\n]+):\s*$')
FAN_SPEED_INLINE_RE: Final[re.Pattern[str]] = re.compile(r'Fan Speed:\s*(\d+)\s*RPM?', re.IGNORECASE)


class FanReading(NamedTuple):
    """A (name, rpm) pair where name may be None and rpm is an int."""
    name: Optional[str]
    rpm: int


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
    def _parse_fans_with_names(text: str) -> List[FanReading]:
        """
        Parse system_profiler SPPowerDataType output into (name, rpm) pairs.
        Name may be None if macOS doesn't label that fan explicitly.
        """
        pairs: List[FanReading] = []
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
                rpm = int(m_spd.group(1))
                nm = nearest_fan_name(stack)
                pairs.append((nm, rpm))
        if not pairs:
            for rpm in FAN_SPEED_INLINE_RE.findall(text):
                pairs.append((None, int(rpm)))
        return pairs

    @staticmethod
    def _parse_istats_line(line: str) -> Optional[FanReading]:
        """
        Parse a single line of `istats fan` output and return a (name, rpm) tuple.

        Args:
            line: One raw line from `istats fan` command output.

        Returns:
            Tuple (name, rpm) if the line contains a fan reading, otherwise None.
        """
        s = line.strip()
        if not s:
            return None
        # Skip summary lines such as "Total fans: 2"
        if re.search(r'^Total\s+fans', s, flags=re.IGNORECASE):
            return None

        # Match labelled format, e.g. "Left Fan: 1700 RPM"
        m = re.search(r'^([^:]+):\s*(\d+)\s*RPM', s, flags=re.IGNORECASE)
        if m:
            return (m.group(1).strip(), int(m.group(2)))

        # Match generic format, e.g. "Fan 0 speed: 1700"
        m2 = re.search(r'^Fan\s*(\d+)\s*speed:\s*(\d+)', s, flags=re.IGNORECASE)
        if m2:
            idx, rpm_str = m2.group(1), m2.group(2)
            return (f"Fan {idx}", int(rpm_str))

        return None

    @staticmethod
    def _get_fan_speeds_istats() -> List[FanReading]:
        # First try rich, named output
        out, _ = safe_run(["istats", "fan"], context="FanIStats", timeout=ISTATS_TIMEOUT)
        pairs: List[FanReading] = []
        if out:
            for ln in out.splitlines():
                parsed = FanDiagnostics._parse_istats_line(ln)
                if parsed:
                    pairs.append(parsed)
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
        return [(None, int(rpm)) for rpm in rpms]

    @staticmethod
    def _apply_fan_defaults(pairs: List[FanReading], model: Optional[str] = None) -> List[
        Dict[str, Any]]:
        fans: List[Dict[str, Any]] = []
        count = len(pairs)
        model_id = model or get_model_identifier()
        names = FanDiagnostics._suggest_names(count, model_id)
        for idx, (name, rpm) in enumerate(pairs, start=1):
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

            pairs: List[FanReading] = []
            if out:
                pairs = FanDiagnostics._parse_fans_with_names(out)

            if not pairs:
                debug_msg("FanDiagnostics", "No fan pairs found in system_profiler, trying istats fallback")
                pairs = FanDiagnostics._get_fan_speeds_istats()

            fans = FanDiagnostics._apply_fan_defaults(pairs)
            result["fans"] = fans

            if fans:
                result["status"] = fan_status_string(fans)
            else:
                debug_msg("FanDiagnostics", f"No fans found; err={err}")
                result["status"] = f"Not accessible ({err})" if err else "No Fan Info (Apple Silicon normal)"

            return result
        except Exception as exc:
            log_exc("FanDiagnostics", exc)
            return {"status": "Fan diagnostics failed", "fans": [], "raw": ""}
