from __future__ import annotations          # keep first, per PEP 563

# ── standard library ───────────────────────────────────────────────
import re                                   # for the regex patterns that follow
from typing import Any, Dict, Optional, Final

# ── internal diagnostics helpers ──────────────────────────────────
from utils import system_profiler_out

from diagnostics.base import safe_match                       # safe regex search helper
# ── regex indentation constants ─────────────────────────────────────
_INDENT_NAME: Final[str] = r'\s{8,}'
_INDENT_FIELD: Final[str] = r'\s{12,}'


DISPLAY_NAME_RE: Final[re.Pattern[str]] = re.compile(fr'^{_INDENT_NAME}([^\n:]+):\s*$', re.MULTILINE)
DISPLAY_RES_RE: Final[re.Pattern[str]] = re.compile(fr'^{_INDENT_FIELD}Resolution:\s*(.+)$', re.MULTILINE)
DISPLAY_CONN_RE: Final[re.Pattern[str]] = re.compile(fr'^{_INDENT_FIELD}Connection Type:\s*(.+)$', re.MULTILINE)
DISPLAY_BUILTIN_RE: Final[re.Pattern[str]] = re.compile(fr'^{_INDENT_FIELD}Built-?In:\s*Yes\b', re.MULTILINE | re.IGNORECASE)


class DisplayDiagnostics:
    @staticmethod
    def _conn_group(label: Optional[str]) -> str:
        label_norm = (label or "").strip().lower()
        if not label_norm:
            return "other"
        if label_norm.startswith("wireless") or "airplay" in label_norm or "sidecar" in label_norm:
            return "wireless"
        if label_norm == "internal":
            return "internal"
        if label_norm == "wired" or label_norm in ("hdmi", "displayport", "usb-c", "usb", "thunderbolt", "usb ("
                                                                                                         "displaylink)"):
            return "wired"
        return "other"

    @staticmethod
    def _group_connections(connections: list[str]) -> Dict[str, Any]:
        """Re‑added local helper: bucket connection labels and counts per category."""
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

    @staticmethod
    def _build_row_section(
            names: list[str],
            connections: list[str],
            details: list[str],
            groups: Dict[str, Any],
            raw: str,
    ) -> dict[str, Any]:
        """Re‑added local helper: build canonical diagnostics section dict."""
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
    def _split_display_blocks(text: str) -> list[str]:
        """Split raw system_profiler output into individual per‑display blocks."""
        starts = [m.start() for m in DISPLAY_NAME_RE.finditer(text)]
        if not starts:
            return []
        blocks: list[str] = []
        for idx, s in enumerate(starts):
            e = starts[idx + 1] if idx + 1 < len(starts) else len(text)
            blocks.append(text[s:e])
        return blocks

    @staticmethod
    def _parse_display_block(block: str) -> tuple[str, Optional[str], str]:
        """Parse a single display block and return (name, resolution, connection)."""
        name_m = DISPLAY_NAME_RE.search(block)
        name = name_m.group(1).strip() if name_m else "Display"

        res_m = DISPLAY_RES_RE.search(block)
        res = res_m.group(1).strip() if res_m else None

        is_builtin = bool(DISPLAY_BUILTIN_RE.search(block))

        conn: Optional[str] = None
        conn_m = DISPLAY_CONN_RE.search(block)
        if conn_m:
            conn = DisplayDiagnostics._normalize_connection(conn_m.group(1))
            if isinstance(conn, str) and conn.lower() in ("unknown", "?", "n/a", "na"):
                conn = None

        if is_builtin:
            conn_label = "Internal"
        elif conn:
            conn_label = conn
        else:
            conn_label = "Wired"

        return name, res, conn_label

    @staticmethod
    def _parse_all_displays(text: str):
        """Return a list of (name, resolution, connection) tuples for each display."""
        blocks = DisplayDiagnostics._split_display_blocks(text)
        return [DisplayDiagnostics._parse_display_block(b) for b in blocks]

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
    def _parse_resolution(text: str) -> Optional[str]:
        # Extract display resolution from system_profiler output.
        m = safe_match(re.compile(r'^\s*Resolution: (.+)', re.MULTILINE), text)
        return m.group(1).strip() if m else None

    @staticmethod
    def _parse_display_name(text: str) -> Optional[str]:
        # Extract display serial/model from system_profiler output.
        m = safe_match(re.compile(r'^\s*Display Serial Number: (.+)', re.MULTILINE), text)
        return m.group(1).strip() if m else None
