# ============================================================================
# Mac Diagnostics Dashboard (GUI)
#
# Table of Contents
#   0.  Module Overview
#   1.  Constants
#   2.  Logging Helpers (standardized, concise)
#   3.  Imports (stdlib, third‑party, intra‑project)
#   4.  DashboardApp class
#       4.1  Peripheral filtering & device grouping helpers
#       4.2  Rendering helpers (health rows, two‑column formatter)
#       4.3  SSD formatting helpers
#       4.4  Display extraction/normalization and table rendering
#       4.5  Refresh thread handling and widget setters
#       4.6  Section updaters: general, battery, ssd, fan, display, devices
#       4.7  Banner computation
#       4.8  Debug log window
#   5.  Program entrypoint
# ============================================================================

# ── stdlib / typing ──────────────────────────────────────────────────
from __future__ import annotations
import threading
import subprocess
import sys
from typing import Dict, List, Tuple, cast, Union
import json
from pathlib import Path
import re as _re

# ── third-party / GUI ────────────────────────────────────────────────
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, Any
from typing import Sequence

# ── intra-project ────────────────────────────────────────────────────
from constants import (  # colours, fonts, icons, window size
    COLORS,
    ICONS,
    FONT_FAMILY_DEFAULT,
    FONT_SIZE_BANNER,
    FONT_SIZE_FIELD,
    FONT_SIZE_SECTION,
    FONT_WEIGHT_BOLD,
    FONT_WEIGHT_NORMAL,
    FONT_FAMILY_MONO,
    WINDOW_SIZE,
    USE_SUDO,
)
from utils import (  # helpers shared with diagnostics
    DebugLogger,
    add_tooltip,
    banner_color,
    banner_icon,
    create_label,
    format_count_devices,
    health_color,
    health_icon,
    health_state,
    is_macos,
    log_debug,
    na,
    short,
    worst_state,
    Tooltip,
    log_exception_once,
    _parse_usb_tree,
    _strip_sysprop_prefix,
    _should_skip_label,
    _ensure_manufacturer_prefix,
    _canonical_label,
)

from diagnostics import (  # domain logic classes
    BatteryDiagnostics,
    DisplayDiagnostics,
    FanDiagnostics,
    GeneralDiagnostics,
    InputDiagnostics,
    PortsDiagnostics,
    SSDDiagnostics,
    DeviceScanner,  # used for USB tree merge
)

# =====================================================================
# 1. Constants & Utility Helpers
# =====================================================================

# ---- Constants (no magic numbers) ------------------------------------
PERIPHERAL_SKIP_KEYWORDS: tuple[str, ...] = ("hub", "billboard", "bus", "lan", "ethernet")
PERIPHERAL_ALLOW_KEYWORDS: tuple[str, ...] = ("keyboard", "mouse", "trackpad", "receiver", "gamepad", "controller")
PERIPHERAL_MAX_NAME_LEN: int = 28

MAX_DEVICES_LINES: int = 8
INDENT_SPACES: int = 4

# ---- Dashboard section definitions (centralised for easy future edits) ----
SECTION_ROWS: tuple[tuple[str, str, str], ...] = (
    ("General Info", "Model / OS", "general"),
    ("Battery", "Health", "battery"),
    ("SSD", "Health", "ssd"),
    ("Fans", "Status", "fan"),
    ("Display", "Details", "display"),
    ("Devices", "Connected", "devices"),
)
    # NOTE: Add / re‑order dashboard sections here ↑

# Scrollable rows config: key -> default text height (lines)
SCROLLABLE_ROWS: dict[str, int] = {
    "devices": 14,
}

SSD_TEXT_MIN_LINES: int = 5
SSD_TEXT_MAX_LINES: int = 10

DISP_BODY_MIN_ROWS: int = 8
DISP_BODY_MAX_ROWS: int = 16

BYTES_PER_DU: float = 512_000.0  # NVMe Data Unit size (bytes)

REFRESH_HELPER_TIMEOUT_SEC: int = 4

DISPLAY_NAME_KEYWORDS: tuple[str, ...] = (
    "display", "lcd", "retina", "macbook", "airplay", "dell", "lg", "benq",
    "acer", "samsung", "hp", "sony", "viewsonic", "asus", "aoc",
)

TOKEN_NORM_MAP: dict[str, str] = {"lan": "ethernet"}
_TOKEN_RE = _re.compile(r"[a-z0-9]+")


def _is_structural_label(s: str) -> bool:
    ls = (s or "").lower()
    return ("hub" in ls) or ("bus" in ls) or ("billboard" in ls)


def _token_set0(label: str) -> set[str]:
    toks = _TOKEN_RE.findall((label or "").lower())
    out: set[str] = set()
    for t in toks:
        if len(t) <= 1:
            continue
        out.add(TOKEN_NORM_MAP.get(t, t))
    return out


def _token_set(label: str) -> set[str]:
    # Alias kept for clarity; currently identical to _token_set0.
    return _token_set0(label)


def _dedupe_usb_items(items: list[tuple[int, Optional[str], str]]) -> list[tuple[int, Optional[str], str]]:
    """Remove duplicate *leaf* USB devices while preserving order and all structural nodes.
    Duplicates are detected via canonical labels and token-subset reasoning, preferring the
    more specific (superset) token set. Structural nodes (Bus/Hub/Billboard) are never removed.
    """
    seen_canon: set[str] = set()
    seen_token_sets: list[set[str]] = []  # only for non-structural leaves, in encounter order
    uniq: list[tuple[int, Optional[str], str]] = []

    # Map non-structural index -> position in uniq for replacement
    non_struct_pos: list[int] = []

    for ind, vend, lbl in items:
        lbl_str = lbl or ""
        if _is_structural_label(lbl_str):
            # Always keep structural entries. They don't participate in token-set indices.
            uniq.append((ind, vend, lbl))
            continue

        canon = _canonical_label(lbl_str)
        if canon in seen_canon:
            # Exact canonical duplicate; drop.
            continue

        tset = _token_set(lbl_str)
        is_dup = False
        replace_idx: Optional[int] = None
        for i, ex in enumerate(seen_token_sets):
            if tset.issubset(ex):
                # New label is less specific; drop it.
                is_dup = True
                break
            if ex.issubset(tset):
                # New label is more specific; replace the previous one.
                replace_idx = i
                break
        if is_dup:
            continue

        if replace_idx is not None:
            # Replace the corresponding previously kept leaf in uniq.
            prev_pos = non_struct_pos[replace_idx]
            uniq[prev_pos] = (ind, vend, lbl)
            seen_token_sets[replace_idx] = tset
            seen_canon.add(canon)
            continue

        # New unique leaf
        seen_canon.add(canon)
        seen_token_sets.append(tset)
        non_struct_pos.append(len(uniq))
        uniq.append((ind, vend, lbl))

    return uniq


# ---- Safe casting helpers --------------------------------------------


def _safe_float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        return float(str(val).strip())
    except Exception:
        return None


def _safe_tooltip(content: Optional[Any]) -> Optional[str]:
    """Return a short tooltip or NA if content is None/empty."""
    if not content:
        return na(None)
    return short(content)


# ---- Tk Text helpers --------------------------------------------------
def _text_set(widget: tk.Text, text: str, *, min_lines: Optional[int] = None, max_lines: Optional[int] = None) -> None:
    """Safely set text into a tk.Text and optionally clamp height by line count."""
    if widget is None:
        return
    try:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("end", text)
        if min_lines is not None or max_lines is not None:
            lines = text.count("\n") + 1
            if min_lines is None:
                min_lines = lines
            if max_lines is None:
                max_lines = lines
            widget.configure(height=min(max(lines, min_lines), max_lines))
        widget.configure(state="disabled")
    except Exception as e:
        _log_error(f"text_set failed: {e}", "Tk")
        log_exception_once(e, "TkText")


# ---- Helper: Set tk.Text widget content safely (replace contents) ----
def _set_text_widget_content(widget: tk.Text, content: str) -> None:
    """Replace contents of a tk.Text widget safely.
    Delegates to the shared `_text_set` utility to avoid duplicated widget state handling
    and ensure consistent behaviour.
    """
    _text_set(widget, content)


# ---- Helper: Set content into tk.Text or fallback to label ----
def _set_text_or_label(app: "DashboardApp", key: str, content: str, *, min_lines: Optional[int] = None,
                       max_lines: Optional[int] = None, tooltip: Optional[str] = None) -> None:
    """Set content into a tk.Text widget or fallback to label via _set_widget_field."""
    widget = app.get_widget(f"{key}_text")
    if isinstance(widget, tk.Text):
        _text_set(widget, content, min_lines=min_lines, max_lines=max_lines)
        add_tooltip(widget, tooltip)
    else:
        app.set_field(key, content, fg=COLORS["FIELD"], tooltip=tooltip)


# ---- Helper: Render a simple static text field with optional tooltip ----
def _render_text_field(app: "DashboardApp", key: str, text: str, tooltip: Optional[str] = None) -> None:
    """Render a simple field with static text and optional tooltip.
    This is a passthrough: text fields do not use status icon/color logic.
    """
    app.set_field(key, text, fg=COLORS["FIELD"], tooltip=tooltip)



# ---- Helper: Render any status field (OK/WARN or health %) ------------------
def _render_status_field(
        app: "DashboardApp",
        key: str,
        text: str,
        status: Union[bool, float, None],
        tooltip: Optional[str] = None
) -> None:
    """
    Render a field whose icon / colour depends on *status*:

        • bool  → OK / WARN mapping
        • float → health percentage (0‑100 or 0‑1) via health_color/icon
        • None  → treated as unknown / WARN

    This replaces the previous _status_icon_color, _render_icon_field
    and _render_health_row helpers.
    """
    if isinstance(status, bool):
        icon = ICONS["OK"] if status else ICONS["WARN"]
        color = COLORS["OK"] if status else COLORS["WARN"]
    else:
        icon = health_icon(status)
        color = health_color(status)
    app.set_field(key, f"{icon} {text}", fg=color, tooltip=tooltip)


# ---- Monospace table renderer ----------------------------------------
def _render_mono_table(rows: Sequence[Sequence[str]], headers: Sequence[str]) -> tuple[str, str]:
    """Return (header_with_sep, body) for aligned monospace columns."""
    try:
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(cell)))
                else:
                    widths.append(len(str(cell)))
        header_line = "  ".join(f"{h:<{widths[i]}}" for i, h in enumerate(headers))
        sep_line = "-" * len(header_line)
        body_lines = [
            "  ".join(f"{str(c):<{widths[i]}}" for i, c in enumerate(row)) for row in rows
        ]
        return header_line + "\n" + sep_line, "\n".join(body_lines)
    except Exception as e:
        log_exception_once(e, "MonoTable")
        _log_error(f"render failed: {e}", "MonoTable")
        return "  ".join(headers), "\n".join("  ".join(map(str, r)) for r in rows)


# --- CONSTANTS ---------------------------------------------------------------
# Magic numbers centralized for clarity and future maintenance.

# Two‑column text layout defaults
TWO_COL_LEFT_PAD_DEFAULT: int = 14
TWO_COL_RIGHT_PAD_DEFAULT: int = 14
TWO_COL_GAP_DEFAULT: int = 4

# Display parsing constants
DISPLAY_HEADERS: tuple[str, str, str, str, str] = (
    "Name", "Resolution", "Mirror", "Connection", "Refresh"
)
SKIP_DISPLAY_NOISE: tuple[str, ...] = (
    "sleep timer", "battery power:", "ac power:", "hibernate mode",
    "state of charge", "cycle count", "current power source",
)


# --- LOGGING HELPERS ---------------------------------------------------------
# Keep logs short and consistently prefixed. Delegate to project utilities.

def _log_debug(message: str, component: str = "Main") -> None:
    try:
        log_debug(message, component)
    except Exception:
        # Never raise on logging.
        pass


def _log_warn(message: str, component: str = "Main") -> None:
    _log_debug(f"WARN: {message}", component)


def _log_error(message: str, component: str = "Main") -> None:
    _log_debug(f"ERROR: {message}", component)


def _log_exception(err: Exception, component: str = "Main") -> None:
    try:
        log_exception_once(err, component)
    except Exception:
        pass


# ---- SUDO FLAG ----


class DashboardApp(tk.Tk):
    # ── Utility: Replace a simple value label with a scrollable monospace Text ──
    def _upgrade_to_scrollable_text(self, key: str, *, height: int = 8, row_weight: int = 1) -> None:
        """
        Convert the value label at *key* (created by _create_row) into a scrollable
        tk.Text widget. Keeps geometry identical so callers only specify *key*.
        Future devs can add more text‑heavy fields by calling this helper.
        """
        if key not in self._widgets:
            return
        old_lbl = self._widgets.pop(key)
        row_idx = old_lbl.grid_info()["row"]
        old_lbl.destroy()

        frame = tk.Frame(self, bg=COLORS["BG"])
        # Value label spanning full width, centred
        frame.grid(row=row_idx, column=0, columnspan=2, sticky="nsew", padx=6, pady=3)

        # Preserve layout weights so the Text stretches nicely.
        self.grid_rowconfigure(row_idx, weight=row_weight)
        # Both columns expand equally now that widgets span them
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Create Text + scrollbar via existing helper.
        self._add_scrollable_text(frame, key, height=height)
    # --- Helper extracted from `_display_from_raw` ---------------------------------
    @staticmethod
    def _parse_raw_display_rows(raw: str) -> List[Tuple[str, str, str, str, str]]:
        """
        Parse `system_profiler` raw display section text and return a list
        of rows with the schema: (name, resolution, mirror, connection, refresh).

        This helper encapsulates the heavy parsing logic that was previously
        in `_display_from_raw`, so that the public method can stay concise
        while the parsing logic remains testable and easy to maintain.
        The implementation below is identical to the previous inline logic,
        but references static helpers through the class (`DashboardApp`) to
        keep the method independent from an instance context.
        """
        out: List[Tuple[str, str, str, str, str]] = []
        name: Optional[str] = None
        res: Optional[str] = None
        mirror: Optional[str] = None
        conn: Optional[str] = None
        refresh: Optional[str] = None
        dtype: Optional[str] = None

        def _looks_like_display(nm: Optional[str]) -> bool:
            if not nm:
                return False
            nl = nm.strip().lower()
            return any(k in nl for k in DISPLAY_NAME_KEYWORDS)

        def push() -> None:
            nonlocal name, res, mirror, conn, refresh, dtype
            if name:
                conn_eff = conn or ("Internal" if (dtype and "built-in" in dtype.lower()) else "Unknown")
                has_meaning = (
                    (res is not None and res != "?")
                    or (conn_eff != "Unknown")
                    or (refresh is not None and refresh != "?")
                )
                if has_meaning or _looks_like_display(name):
                    out.append((name or "Display", res or "?", mirror or "N", conn_eff, refresh or "?"))
            name = res = mirror = conn = refresh = dtype = None

        for ln in (raw or "").splitlines():
            s = ln.strip()
            if not s:
                continue
            if DashboardApp._is_noise_line(s):
                continue
            ls = s.lower()

            if ls.startswith("display type:"):
                dtype = s.split(":", 1)[1].strip() if ":" in s else s
                continue

            # Section headers
            if DashboardApp._raw_is_section_header(s):
                cand = s[:-1].strip()
                cl = cand.lower()
                if DashboardApp._raw_should_skip_header(cl):
                    if name or res or mirror or conn or refresh or dtype:
                        push()
                    name = res = mirror = conn = refresh = dtype = None
                    continue
                if name or res or mirror or conn or refresh or dtype:
                    push()
                name = cand
                continue

            if "resolution" in ls and res is None:
                res = DashboardApp._norm_res(s)
                continue

            if "ui looks like" in ls:
                hz = DashboardApp._hz_from_text(s)
                if hz:
                    refresh = DashboardApp._sanitize_refresh(hz)
                continue

            if "refresh" in ls and "hz" in ls:
                hz = DashboardApp._hz_from_text(s)
                if hz:
                    refresh = DashboardApp._sanitize_refresh(hz)
                continue

            if "mirror" in ls and mirror is None:
                mv = DashboardApp._parse_mirror_value(s)
                mirror = mv or "N"
                continue

            if any(k in ls for k in ("connection type", "connection", "transport", "interface", "airplay")) and conn is None:
                cv = DashboardApp._parse_connection_value(s)
                if cv is not None:
                    conn = cv
                continue

        if name or res or mirror or conn or refresh or dtype:
            push()
        return out
    def get_widget(self, key: str) -> Optional[tk.Widget]:
        """Public accessor for widgets dict to avoid protected-member use outside."""
        return self._widgets.get(key)

    def set_field(self, key: str, text: str, fg: Optional[str] = None, tooltip: Optional[str] = None) -> None:
        """Public wrapper around _set_widget_field for external helpers."""
        self._set_widget_field(key, text, fg=fg, tooltip=tooltip)

    # --- Helper: create a scrollable monospace Text widget -------------------- #
    def _add_scrollable_text(self, container: tk.Frame, key: str, height: int) -> tk.Text:
        """
        Build a tk.Text + vertical scrollbar inside *container*, register it
        under ``self._widgets[f"{key}_text"]`` and return the Text widget.

        Args:
            container: Parent frame that already has its geometry/grid configured.
            key: Base key name (e.g. "ssd", "devices", "display_body").
            height: Default number of text lines to show.

        The widget uses the same monospace font / colours everywhere so the UI
        remains consistent.
        """
        txt = tk.Text(
            container,
            font=("Menlo", FONT_SIZE_FIELD, FONT_WEIGHT_NORMAL),
            fg=COLORS["FIELD"],
            bg=COLORS["BG"],
            height=height,
            wrap="none",
            relief="flat",
            borderwidth=0,
        )
        txt.pack(side="left", fill="both", expand=True)
        txt.configure(padx=4)
        txt.configure(pady=2)
        scroll_y = ttk.Scrollbar(container, orient="vertical", command=txt.yview)
        scroll_y.pack(side="right", fill="y")
        txt.configure(yscrollcommand=scroll_y.set, state="disabled")
        self._widgets[f"{key}_text"] = txt
        return txt

    @staticmethod
    def _device_category(label_category: str) -> str:
        l_category = (label_category or "").lower()
        if "receiver" in l_category:
            return "Wireless Mouse"
        if "keyboard" in l_category and ("built-in" in l_category or "internal" in l_category):
            return "MacBook Keyboard"
        if "trackpad" in l_category and ("built-in" in l_category or "internal" in l_category):
            return "MacBook Trackpad"
        if "keyboard" in l_category:
            return "Keyboard"
        if "mouse" in l_category:
            return "Mouse"
        if "ethernet" in l_category or "lan" in l_category:
            return "Ethernet"
        if "hub" in l_category or "billboard" in l_category:
            return "Hub"
        if "bus" in l_category:
            return "Bus"
        return "Device"

    @staticmethod
    def _friendly_label(vendor: Optional[str], friendly_label: str) -> str:
        lfl = (friendly_label or "").lower()
        # buses / hubs: leave raw
        if "bus" in lfl or "hub" in lfl:
            return friendly_label
        # generic receiver: force Logitech if vendor unknown
        if lfl == "usb receiver":
            return f"{vendor or 'Logitech'} USB Receiver"
        if vendor and not lfl.startswith((vendor or "").lower()):
            return f"{vendor} {friendly_label}"
        return friendly_label

    @staticmethod
    def _is_peripheral_device(name: str) -> bool:
        """Return True if name is a user-facing peripheral, False if hub/bus/etc."""
        if not name:
            return False
        lname = name.lower()
        if any(k in lname for k in PERIPHERAL_SKIP_KEYWORDS):
            return False
        if any(k in lname for k in PERIPHERAL_ALLOW_KEYWORDS):
            return True
        return len(name) < PERIPHERAL_MAX_NAME_LEN

    def _friendly_devices(self, devices: List[str]) -> Tuple[List[str], List[str]]:
        """
        Generate two lists of connected devices: built-in and external.
        Each list is a summary (grouped/counts, deduped, truncated).
        Returns (built_in_lines, external_lines).
        """
        from collections import Counter
        built_in = []
        external = []

        def relabel(dev):
            dl = dev.lower()
            if (
                    "internal keyboard" in dl or "apple internal keyboard" in dl
                    or ("internal" in dl and "keyboard" in dl)
            ):
                return "Built-in Keyboard", True
            if "trackpad" in dl and ("internal" in dl or "apple" in dl):
                return "Built-in Trackpad", True
            if "display" in dl and ("internal" in dl or "built-in" in dl or "apple" in dl):
                return "Built-in Display", True
            if "internal mouse" in dl:
                return "Built-in Mouse", True
            return dev, False

        # Filter out non-peripherals
        filtered = [dev for dev in devices if self._is_peripheral_device(dev)]
        labels_and_type = [relabel(dev) for dev in filtered]
        # Separate
        for dev, is_built_in in labels_and_type:
            if is_built_in:
                built_in.append(dev)
            else:
                external.append(dev)

        # Deduplicate and group counts
        def count_lines(devs):
            c = Counter(devs)
            return [f"{n} {name}" if n > 1 else name for name, n in c.items()]

        built_in_lines = count_lines(built_in) if built_in else []
        external_lines = count_lines(external) if external else []
        # Truncate each list to max MAX_DEVICES_LINES entries
        max_lines = MAX_DEVICES_LINES
        if len(built_in_lines) > max_lines:
            extra = len(built_in_lines) - max_lines
            built_in_lines = built_in_lines[:max_lines] + [f"... ({extra} more)"]
        if len(external_lines) > max_lines:
            extra = len(external_lines) - max_lines
            external_lines = external_lines[:max_lines] + [f"... ({extra} more)"]
        return built_in_lines, external_lines


    # --- SSD TWO-COLUMN RENDER HELPERS ---------------------------------
    @staticmethod
    def _fmt_percent(val: Optional[float]) -> str:
        try:
            if val is None:
                return "?"
            # Accept 0-1 or 0-100 inputs
            if 0.0 <= val <= 1.0:
                pct = val * 100.0
            else:
                pct = val
            return f"{pct:.0f}%"
        except Exception:
            return str(val)

    @staticmethod
    def _fmt_bytes(num: Any) -> str:
        try:
            n = float(num)
        except Exception:
            return str(num) if num is not None else "?"
        # Use decimal powers (k=1000) to match smartctl's [13.2 TB] style
        units = ["B", "KB", "MB", "GB", "TB", "PB"]
        idx = 0
        while n >= 1000.0 and idx < len(units) - 1:
            n /= 1000.0
            idx += 1
        if n >= 100:
            return f"{n:.0f} {units[idx]}"
        elif n >= 10:
            return f"{n:.1f} {units[idx]}"
        else:
            return f"{n:.2f} {units[idx]}"

    @staticmethod
    def _fmt_temp_c(val: Any) -> str:
        try:
            if val is None:
                return "?"
            v = float(val)
            return f"{v:.0f}°C"
        except Exception:
            return str(val)

    def _ssd_pairs(self, s: Dict[str, Any]) -> List[Tuple[str, str]]:
        """Return ordered (label, value) pairs for the SSD section.
        Uses robust fallbacks so missing keys won't crash the UI.
        This version prefers *byte* fields; if only NVMe "data units" are
        present, it converts them using the NVMe spec factor of 512,000 bytes
        per unit. Host command counters are shown separately and are **not**
        interpreted as bytes.
        """

        def _num(v: Any) -> Optional[float]:
            return float(v) if isinstance(v, (int, float)) else None

        # --- Health -----------------------------------------------------
        percent_left = (
                s.get("percent_left")
                or s.get("life_left")
                or s.get("health_percent")
                or s.get("available_spare")  # NVMe terminology
        )

        # --- Bytes read/written (prefer pretty bracketed values, then bytes, then DU conversion) -----
        raw_txt = s.get("raw") or s.get("detailed") or s.get("detailed_short")

        def _bytes_from_bracket(line_pat: str) -> Optional[float]:
            if not isinstance(raw_txt, str):
                return None
            m = _re.search(line_pat + r"\s*[0-9,]+\s*\[\s*([0-9]+(?:\.[0-9]+)?)\s*(TB|GB)\s*]", raw_txt, flags=_re.I)
            if not m:
                return None
            val = float(m.group(1))
            unit = m.group(2).upper()
            factor = 1_000_000_000_000.0 if unit == "TB" else 1_000_000_000.0
            return val * factor

        # 1) Prefer pretty bracketed values from smartctl (keeps exact TB/GB scale)
        bytes_read_val = _bytes_from_bracket(r"Data Units Read:")
        bytes_written_val = _bytes_from_bracket(r"Data Units Written:")

        # 2) If not present, try direct byte counters from our structured dict
        if bytes_read_val is None:
            bytes_read_val = _num(
                s.get("bytes_read") or s.get("data_read") or s.get("host_reads_bytes") or s.get("nvm_read_bytes"))
        if bytes_written_val is None:
            bytes_written_val = _num(
                s.get("bytes_written") or s.get("data_written") or s.get("host_writes_bytes") or s.get(
                    "nvm_write_bytes"))

        # 3) Finally, convert NVMe Data Units (each 512,000 bytes) when needed
        DUR_keys = ["data_units_read", "nvme_data_units_read", "nvm_data_units_read", "data_units_read_total"]
        DUW_keys = ["data_units_written", "nvme_data_units_written", "nvm_data_units_written",
                    "data_units_written_total"]
        dur = next((s.get(k) for k in DUR_keys if isinstance(s.get(k), (int, float))), None)
        duw = next((s.get(k) for k in DUW_keys if isinstance(s.get(k), (int, float))), None)
        if bytes_read_val is None and isinstance(dur, (int, float)):
            bytes_read_val = dur * BYTES_PER_DU
        if bytes_written_val is None and isinstance(duw, (int, float)):
            bytes_written_val = duw * BYTES_PER_DU

        # Host command counters – display separately when present
        read_cmds = s.get("host_read_commands") or s.get("host_reads")
        write_cmds = s.get("host_write_commands") or s.get("host_writes")

        # --- Other metrics ---------------------------------------------
        cycles = s.get("power_cycles") or s.get("cycles")
        temp_c = s.get("temperature_c") or s.get("temperature") or s.get("temperature_celsius")
        if temp_c is None:
            if isinstance(s.get("raw"), str):
                tm = _re.search(r"Temperature:\s*([0-9]+)\s*Celsius", s["raw"], flags=_re.I)
                if tm:
                    temp_c = int(tm.group(1))
        firmware = s.get("firmware") or s.get("firmware_version") or s.get("fw")
        poh = s.get("power_on_hours") or s.get("poh")
        unsafe = s.get("unsafe_shutdowns") or s.get("unsafe_shuts")
        errors = s.get("media_errors") or s.get("errors") or s.get("crc_errors") or s.get("media_data_integrity_errors")

        # Compute total used from byte counters only (avoid commands)
        total_used_val: Optional[float]
        if isinstance(bytes_read_val, (int, float)) or isinstance(bytes_written_val, (int, float)):
            br = bytes_read_val or 0.0
            bw = bytes_written_val or 0.0
            total_used_val = br + bw
        else:
            total_used_val = None

        pairs: List[Tuple[str, str]] = [
            ("Health Left", self._fmt_percent(percent_left) if isinstance(percent_left, (int, float)) else (
                str(percent_left) if percent_left else "?")),
            ("Power Cycles", str(cycles) if cycles is not None else "?"),
            ("Read", self._fmt_bytes(bytes_read_val) if bytes_read_val is not None else "?"),
            ("Written", self._fmt_bytes(bytes_written_val) if bytes_written_val is not None else "?"),
            ("Total Used", self._fmt_bytes(total_used_val)),
            ("Temperature", self._fmt_temp_c(temp_c)),
            ("Firmware", str(firmware) if firmware else "?"),
            ("Power on Hours", str(poh) if poh is not None else "?"),
            ("Unsafe Shutdowns", str(unsafe) if unsafe is not None else "0"),
            ("Errors", str(errors) if errors is not None else "0"),
        ]

        # Append host command counters if available
        if isinstance(read_cmds, (int, float)):
            pairs.append(("Read Cmds", f"{int(read_cmds):,}"))
        elif isinstance(read_cmds, str) and read_cmds.strip():
            pairs.append(("Read Cmds", read_cmds))
        if isinstance(write_cmds, (int, float)):
            pairs.append(("Write Cmds", f"{int(write_cmds):,}"))
        elif isinstance(write_cmds, str) and write_cmds.strip():
            pairs.append(("Write Cmds", write_cmds))

        return pairs

    @staticmethod
    def _format_two_col(pairs: List[Tuple[str, str]], left_label_pad: int = 14, right_label_pad: int = 14,
                        gap: int = 4) -> str:
        """Format (label, value) pairs into two columns, row-major.
        Example layout per row: "LabelA: valueA    LabelB: valueB"
        """
        # Build "Label: value" strings first so we can pad evenly
        items = [f"{lbl}: {val}" for lbl, val in pairs]
        # Determine widths for each column independently to keep the grid tight
        left_width = max(len(items[i]) for i in range(0, len(items), 2)) if items else 0
        right_width = max(len(items[i]) for i in range(1, len(items), 2)) if len(items) > 1 else 0
        left_width = max(left_width, left_label_pad)
        right_width = max(right_width, right_label_pad)
        lines: List[str] = []
        for i in range(0, len(items), 2):
            left_item = items[i]
            right_item = items[i + 1] if i + 1 < len(items) else ""
            line = f"{left_item:<{left_width}}" + (" " * gap) + f"{right_item:<{right_width}}"
            lines.append(line.rstrip())
        return "\n".join(lines)

    """
    Main GUI application class for Mac Diagnostics Dashboard.
    Handles layout, data fetching, and widget state.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title("Mac Diagnostics Dashboard")
        self.configure(bg=COLORS["BG"])
        self.geometry(WINDOW_SIZE)
        self.resizable(True, False)
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self._widgets: Dict[str, tk.Widget] = {}
        self._tooltips: Dict[str, Tooltip] = {}
        self._last_refresh_probe_err: Optional[str] = None
        self._build_ui()
        self._last_diag: Dict[str, Any] = {}
        self._refresh_threaded()

    # ── Modular UI builders for clarity & maintainability ──────────────────
    def _build_banner_row(self) -> int:
        """Create the top banner label and return the next grid row."""
        banner = tk.Label(
            cast(tk.Widget, self),
            text="Loading...",
            font=(FONT_FAMILY_DEFAULT, FONT_SIZE_BANNER, FONT_WEIGHT_BOLD),
            fg=COLORS["FG"],
            bg=COLORS["BG"],
            pady=10
        )
        banner.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(10, 5))
        self._widgets["banner"] = banner
        return 1  # next available grid row

    def _build_base_rows(self, start_row: int) -> int:
        """Build the summary rows listed in SECTION_ROWS starting at *start_row*; returns next row."""
        row = start_row
        for section, label_text, key in SECTION_ROWS:
            row = self._create_row(row, section, label_text, key)
        return row

    # --- SECTION: DASHBOARD ROW HELPERS ---#
    def _create_row(
            self,
            row: int,
            section: str,
            label_text: str,
            key: str
    ) -> int:
        """
        Create a titled section header plus an empty value field.

        Args:
            row: Current grid row index.
            section: Human‑readable section title.
            label_text: Static label for the value field.
            key: Dictionary key used to store the created value label.

        Returns:
            int: The next available row index.
        """
        # Section header
        header = create_label(
            cast(tk.Widget, self),
            f" {section} ",
            font=(FONT_FAMILY_DEFAULT, FONT_SIZE_SECTION, FONT_WEIGHT_BOLD),
            fg=COLORS["SECTION"],
            bg=COLORS["BG"]
        )
        header.grid(row=row, column=0, columnspan=2,
                    sticky="ew", pady=(12, 0))
        row += 1

        # Value label spanning full width, centred
        value_lbl = create_label(
            cast(tk.Widget, self),
            "...",
            font=(FONT_FAMILY_DEFAULT, FONT_SIZE_FIELD, FONT_WEIGHT_NORMAL),
            fg=COLORS["FIELD"],
            bg=COLORS["BG"],
        )
        # Center-align text once the widget exists
        value_lbl.config(justify="center", anchor="center")
        value_lbl.grid(row=row, column=0, columnspan=2,
                       sticky="n", pady=3)

        # Store reference for later updates
        self._widgets[key] = value_lbl
        return row + 1

    def _build_ui(self) -> None:
        """
        Build all UI sections and fields using utility methods.
        """
        row = self._build_banner_row()
        row = self._build_base_rows(row)
        # Upgrade any rows marked in SCROLLABLE_ROWS to scrollable Text widgets
        for key, h in SCROLLABLE_ROWS.items():
            self._upgrade_to_scrollable_text(
                key,
                height=h,
                row_weight=0 if key == "ssd" else 1,
            )
        # ── Replace the simple label for 'display' with a scrollable Text ──
        if "display" in self._widgets:
            old_disp = self._widgets.pop("display")
            disp_row_idx = old_disp.grid_info()["row"]
            old_disp.destroy()

            disp_frame = tk.Frame(self, bg=COLORS["BG"])
            disp_frame.grid(row=disp_row_idx, column=1, sticky="nsew", padx=6, pady=3)
            self.grid_rowconfigure(disp_row_idx, weight=1)
            self.grid_columnconfigure(1, weight=1)

            # Header (fixed)
            disp_header = tk.Text(
                disp_frame,
                font=("Menlo", FONT_SIZE_FIELD, FONT_WEIGHT_NORMAL),
                fg=COLORS["FIELD"],
                bg=COLORS["BG"],
                height=2,
                wrap="none",
                relief="flat",
                borderwidth=0,
            )
            disp_header.pack(side="top", fill="x")
            disp_header.configure(padx=4)
            disp_header.configure(pady=2)
            disp_header.configure(state="disabled")

            # Body (scrollable)
            disp_body_container = tk.Frame(disp_frame, bg=COLORS["BG"])
            disp_body_container.pack(side="top", fill="both", expand=True)

            disp_body = self._add_scrollable_text(disp_body_container, "display_body", height=8)
            disp_body.configure(pady=0)

            self._widgets["display_header_text"] = disp_header
            # self._widgets["display_body_text"] = disp_body  # already set by helper

        # ── Action buttons ──
        btn = ttk.Button(self, text="Refresh", command=self._refresh_threaded)
        btn.grid(row=row, column=0, columnspan=2, pady=18, sticky="ew")
        row += 1
        debug_btn = ttk.Button(self, text="Debug Log", command=self._show_debug_log)
        debug_btn.grid(row=row, column=0, columnspan=2, pady=(2, 8), sticky="ew")

    # REMOVED _render_display_table_parts; replaced with _render_display_table below.

    @staticmethod
    def _render_display_table(rows: List[Tuple[str, str, str, str, str]]) -> Tuple[str, str]:
        headers = ("Name", "Resolution", "Mirror", "Connection", "Refresh")
        return _render_mono_table(rows, headers)

    def _refresh_threaded(self) -> None:
        """
        Start background refresh thread for diagnostics, but skip if a refresh is already running.
        """
        if getattr(self, "_refresh_running", False):
            log_debug("Refresh already running; skipping.", "Main")
            return

        self._refresh_running = True

        def _run() -> None:
            try:
                self._refresh()
            finally:
                self._refresh_running = False

        threading.Thread(target=_run, daemon=True).start()

    def _set_widget_field(self, key: str, text: str, fg: Optional[str] = None, tooltip: Optional[str] = None) -> None:
        """
        Set a field's text, color, and tooltip using utilities.
        Tooltip will always be set or updated; callers do not need to check for presence.
        """
        widget = self._widgets.get(key)
        if not widget:
            return
        widget.config(text=text)
        if fg:
            widget.config(fg=fg)
        add_tooltip(widget, tooltip)

    # --- BEGIN PER-SECTION UPDATE HELPERS (ADDED) ---#
    def _update_general(self) -> Dict[str, Any]:
        """Fetch & render GeneralDiagnostics row."""
        g = GeneralDiagnostics.fetch()
        _render_text_field(
            self,
            "general",
            f"{g['model']}\nOS: {g['os']}\nSN: {g['serial']}",
        )
        return g

    def _update_battery(self) -> dict[str, any]:
        b = BatteryDiagnostics.fetch()

        pct       = _safe_float(b.get("percent_health"))
        full_cap  = _safe_float(b.get("full_capacity")  or b.get("max_capacity"))
        design_cap= _safe_float(b.get("design_capacity") or b.get("design_cap"))
        cycles    = b.get("cycle_count") or b.get("cycles")
        temp_c    = _safe_float(b.get("temperature_c") or b.get("temperature"))
        voltage   = _safe_float(b.get("voltage") or b.get("voltage_mv"))

        pairs = [
            ("Health",   f"{pct:.0f} %" if pct is not None else b.get("health_text","?")),
            ("Capacity", f"{int(full_cap):,} / {int(design_cap):,} mAh" if full_cap and design_cap else "?"),
            ("Cycles",   str(cycles) if cycles is not None else "?"),
            ("Temp",     f"{temp_c:.1f} °C" if temp_c is not None else "?"),
            ("Voltage",  f"{voltage/1000:.2f} V" if voltage and voltage>10 else
                         (f"{voltage:.0f} mV" if voltage else "?")),
        ]

        body = self._format_two_col(pairs, left_label_pad=10, right_label_pad=18, gap=4)

        _set_text_or_label(
            self, "battery", body,
            min_lines=3, max_lines=10,
            tooltip=_safe_tooltip(b.get("raw")),
        )
        return b

    def _update_ssd(self) -> Dict[str, Any]:
        """Fetch & render SSDDiagnostics as a two-column list."""
        s = SSDDiagnostics.fetch(require_sudo=USE_SUDO)

        # Build the two-column text
        pairs = self._ssd_pairs(s)
        body = self._format_two_col(pairs, left_label_pad=16, right_label_pad=16, gap=4)

        _set_text_or_label(
            self,
            "ssd",
            body,
            min_lines=SSD_TEXT_MIN_LINES,
            max_lines=SSD_TEXT_MAX_LINES,
            tooltip=_safe_tooltip(s.get("detailed") or s.get("raw") or s.get("detailed_short")),
        )

        # Keep existing overall health color/icon logic available via percent for banner usage
        return s

    def _update_fan(self) -> Dict[str, Any]:
        """Fetch & render FanDiagnostics row."""
        f = FanDiagnostics.fetch()
        fans = f.get("fans") or []
        if fans:
            text = " | ".join(
                f"{it['name']}: {it['rpm']} RPM" for it in fans
                if isinstance(it, dict) and 'name' in it and 'rpm' in it
            )
        else:
            text = f.get("status", "No Fan Info")
        _render_status_field(
            self,
            "fan",
            text,
            None,
            tooltip=short(f.get("raw")),
        )
        return f

    @staticmethod
    def _canon_disp_name(name: Optional[str]) -> str:
        return (name or "").strip().lower()

    def _extract_display_rows(self, d: Dict[str, Any]) -> List[Tuple[str, str, str, str, str]]:
        """
        Merge display info from all available sources (structured, list, raw), conservative merge.
        Returns list of rows: (name, resolution, mirror, connection, refresh).
        """
        rows_sp: List[Tuple[str, str, str, str, str]] = self._display_from_structured_parallel(d)
        rows_list: List[Tuple[str, str, str, str, str]] = self._display_from_displays_list(d)
        rows_raw: List[Tuple[str, str, str, str, str]] = []
        raw = d.get("raw") if isinstance(d, dict) else None
        if isinstance(raw, str):
            rows_raw = self._display_from_raw(raw)

        # choose a baseline order: prefer raw order, else list, else structured
        if rows_raw:
            base = rows_raw
            others = rows_list + rows_sp
        elif rows_list:
            base = rows_list
            others = rows_sp
        else:
            base = rows_sp
            others = []

        def better(a: str, b: str, unknown_tokens=("?", "Unknown")) -> str:
            if not a or a in unknown_tokens or a.strip() == "":
                return b
            return a

        # Build dict keyed by canonical name and merge fields conservatively
        merged: Dict[str, Tuple[str, str, str, str, str]] = {}
        order: List[str] = []
        for n, r, m, c, hz in base:
            key = self._canon_disp_name(n)
            merged[key] = (n, r, m, c, hz)
            order.append(key)
        for n, r, m, c, hz in others:
            key = self._canon_disp_name(n)
            if key not in merged:
                merged[key] = (n, r, m, c, hz)
                order.append(key)
            else:
                on, orr, om, oc, ohz = merged[key]
                # Mirror: prefer Y if any source says Y
                mm = "Y" if (m == "Y" or om == "Y") else (om if om in {"Y", "N"} else (m if m in {"Y", "N"} else "N"))
                merged[key] = (
                    better(on, n),
                    better(orr, r),
                    mm,
                    better(oc, c),
                    better(ohz, hz),
                )

        rows = [merged[k] for k in order]
        if not rows:
            rows.append(("Built-in Display", "?", "N", "Unknown", "?"))
        rows = self._normalize_display_rows(rows, d)
        return rows

    @staticmethod
    def _hz_from_text(s: str) -> Optional[str]:
        m = _re.search(r"@(\s*)?(\d+(?:\.\d+)?)\s*Hz", s, flags=_re.I)
        if m:
            val = m.group(2)
            # strip trailing .00
            if val.endswith(".00"):
                val = val[:-3]
            return f"{val}Hz"
        m2 = _re.search(r"(\d+(?:\.\d+)?)\s*Hz", s, flags=_re.I)
        if m2:
            val = m2.group(1)
            if val.endswith(".00"):
                val = val[:-3]
            return f"{val}Hz"
        return None

    @staticmethod
    def _is_noise_line(s: str) -> bool:
        """Return True if a raw text line is unrelated 'noise' (battery, power settings, etc.)."""
        ls = s.lower()
        return any(t in ls for t in SKIP_DISPLAY_NOISE)

    @staticmethod
    def _parse_display_type_hints(raw: str) -> Dict[str, str]:
        """Parse `Display Type:` hints keyed by section name from raw system_profiler text."""
        hints: Dict[str, str] = {}
        current: Optional[str] = None
        for ln in raw.splitlines():
            s = ln.strip()
            if not s:
                continue
            l = s.lower()
            # Section header heuristic: lines ending with ':' that aren't ordinary key/value
            if s.endswith(":") and not l.startswith("resolution") and not l.startswith("ui looks like"):
                current = s[:-1].strip()
                continue
            if current and l.startswith("display type:"):
                hints[current] = s.split(":", 1)[1].strip()
        return hints

    @staticmethod
    def _is_builtin_display(name: str, conn: Optional[str], type_hints: Dict[str, str]) -> bool:
        lname = (name or "").lower()
        if conn and str(conn).lower() == "internal":
            return True
        if "built-in" in lname or "builtin" in lname:
            return True
        if lname.startswith("color lcd"):
            return True
        t = type_hints.get(name) or ""
        return "built-in" in t.lower()

    @staticmethod
    def _sanitize_refresh(hz: Optional[str]) -> Optional[str]:
        if not hz:
            return hz
        s = str(hz)
        if s.endswith(".00Hz"):
            return s.replace(".00Hz", "Hz")
        return s

    @staticmethod
    def _coerce_internal_connection(conn: Optional[str], builtin_flag: bool) -> str:
        if builtin_flag and (not conn or conn == "Unknown"):
            return "Internal"
        return conn or "Unknown"

    @staticmethod
    def _raw_is_section_header(s: str) -> bool:
        l = s.strip().lower()
        return s.endswith(":") and not l.startswith("resolution") and not l.startswith("ui looks like")

    @staticmethod
    def _raw_should_skip_header(cl: str) -> bool:
        """Return True if a section header `cl` (lowercased) is a non-display header we should skip."""
        return (
                cl in {"displays", "graphics/displays"}
                or cl.startswith("graphics/")
                or cl.startswith("chipset model")
                or cl.startswith("type: gpu")
                or cl.startswith("bus:")
                or cl.startswith("vendor:")
                or cl.startswith("metal support")
                or (cl.startswith("apple m") and ("display" not in cl and "macbook" not in cl))
        )

    @staticmethod
    def _parse_mirror_value(s: str) -> Optional[str]:
        if ":" in s:
            val = s.split(":", 1)[1].strip().lower()
            return "Y" if val in {"on", "yes", "true", "1"} else "N"
        return None

    @staticmethod
    def _parse_connection_value(s: str) -> Optional[str]:
        ls = s.lower()
        if "airplay" in ls:
            return "AirPlay"
        if "internal" in ls:
            return "Internal"
        if ":" in s:
            v = s.split(":", 1)[1].strip()
            return v or "Unknown"
        # fallback: if line is clearly a connection descriptor, return it
        if any(k in ls for k in ("connection type", "connection", "transport", "interface")):
            return s.strip() or "Unknown"
        return None

    @staticmethod
    def _norm_res(s: str) -> str:
        s = s.replace("×", "x").replace("X", "x")
        # keep only first width x height occurrence
        m = _re.search(r"(\d{3,5})\s*x\s*(\d{3,5})", s)
        return f"{m.group(1)}x{m.group(2)}" if m else s.strip()

    def _display_from_structured_parallel(self, d: Dict[str, Any]) -> List[Tuple[str, str, str, str, str]]:
        out: List[Tuple[str, str, str, str, str]] = []
        names = d.get("names") if isinstance(d, dict) else None
        if not isinstance(names, list) or not names:
            return out
        resolutions = d.get("resolutions") if isinstance(d, dict) else None
        mirrors = d.get("mirrors") if isinstance(d, dict) else None
        connections = d.get("connections") if isinstance(d, dict) else None
        refreshes = d.get("refresh") if isinstance(d, dict) else None
        n = len(names)

        def _get(lst, i, default=None):
            return lst[i] if isinstance(lst, list) and i < len(lst) else default

        for idx in range(n):
            name = str(_get(names, idx, "Display"))
            res = self._norm_res(str(_get(resolutions, idx, "?"))) if _get(resolutions, idx, None) is not None else "?"
            mir_v = _get(mirrors, idx, False)
            mirror = "Y" if (isinstance(mir_v, bool) and mir_v) or (
                    isinstance(mir_v, str) and mir_v.strip().lower() in {"y", "yes", "true", "1"}) else "N"
            conn = str(_get(connections, idx, "Unknown"))
            # heuristic: mark internal if name mentions built-in or Color LCD
            if (not conn or conn == "Unknown") and ("built-in" in name.lower() or name.lower().startswith("color lcd")):
                conn = "Internal"
            ref = _get(refreshes, idx, None)
            ref_s = str(ref) if ref is not None else "?"
            # if refresh is embedded like "1920x1080 @ 60Hz"
            if "Hz" in ref_s and "@" in ref_s:
                hz = self._hz_from_text(ref_s)
                if hz:
                    ref_s = hz
            elif ref_s and ref_s.isdigit():
                ref_s = f"{ref_s}Hz"
            elif ref_s == "?":
                ref_s = "?"
            out.append((name, res, mirror, conn, ref_s))
        return out

    def _display_from_displays_list(self, d: Dict[str, Any]) -> List[Tuple[str, str, str, str, str]]:
        out: List[Tuple[str, str, str, str, str]] = []
        disp_list = d.get("displays") if isinstance(d, dict) else None
        if not isinstance(disp_list, list):
            return out
        for item in disp_list:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("display_name") or item.get("model") or "Display")
            res = self._norm_res(str(item.get("resolution") or item.get("size") or "?"))
            mir_val = item.get("mirror")
            mirror = "Y" if (isinstance(mir_val, bool) and mir_val) or (
                    isinstance(mir_val, str) and mir_val.strip().lower() in {"y", "yes", "true", "1"}) else "N"
            conn = str(item.get("connection") or item.get("connection_type") or item.get("transport") or "Unknown")
            dtype = str(item.get("display_type") or "")
            if not conn or conn == "Unknown":
                if "built-in" in dtype.lower():
                    conn = "Internal"
            # refresh: allow numeric or embedded
            refresh = item.get("refresh") or item.get("ui_looks_like") or item.get("hz") or "?"
            hz = self._hz_from_text(str(refresh)) if isinstance(refresh, str) else None
            ref_s = hz or (f"{refresh}Hz" if isinstance(refresh, (int, float)) else "?")
            out.append((name, res, mirror, conn, ref_s))
        return out

    def _display_from_raw(self, raw: str) -> List[Tuple[str, str, str, str, str]]:
        # Delegated to helper for readability & future maintenance.
        return DashboardApp._parse_raw_display_rows(raw)

    def _ensure_refresh_helper(self) -> Optional[Path]:
        """Compile helpers/refresh_rate.swift to a small CLI if needed. Returns path or None on failure."""
        try:
            proj_root = Path(__file__).resolve().parent
            src = proj_root / "helpers" / "refresh_rate.swift"
            if not src.exists():
                alt = Path("/mnt/data/refresh_rate.swift")
                if alt.exists():
                    src = alt
            if not src.exists():
                msg = f"refresh helper source missing: {src}"
                log_debug(msg, "DisplayRefresh")
                self._last_refresh_probe_err = msg
                return None
            # Place binary alongside source when using /mnt/data fallback
            if src.as_posix().startswith("/mnt/data/"):
                bin_path = Path("/mnt/data/refresh_rate")
            else:
                bin_path = proj_root / "helpers" / "refresh_rate"
            needs_build = (not bin_path.exists()) or (bin_path.stat().st_mtime < src.stat().st_mtime)
            if needs_build:
                cmd = [
                    "xcrun", "swiftc", str(src),
                    "-O",
                    "-framework", "CoreGraphics",
                    "-framework", "CoreVideo",
                    "-o", str(bin_path),
                ]
                log_debug(f"Compiling refresh helper… cmd={' '.join(cmd)}", "DisplayRefresh")
                proc = subprocess.run(cmd, capture_output=True, text=True)
                if proc.returncode != 0:
                    err = (proc.stderr or "").strip()
                    out = (proc.stdout or "").strip()
                    msg = f"swiftc failed rc={proc.returncode}: {err or out}"
                    log_debug(msg, "DisplayRefresh")
                    self._last_refresh_probe_err = msg
                    return None
                log_debug("Compiled refresh helper OK", "DisplayRefresh")
            return bin_path
        except Exception as e:
            msg = f"ensure_refresh_helper error: {e}"
            log_exception_once(e, "DisplayRefresh")
            self._last_refresh_probe_err = msg
            return None

    def _probe_builtin_refresh_rate(self) -> Optional[str]:
        bin_path = self._ensure_refresh_helper()
        if not bin_path:
            return None
        try:
            r = subprocess.run([str(bin_path)], capture_output=True, text=True, timeout=REFRESH_HELPER_TIMEOUT_SEC)
            if r.returncode != 0:
                msg = f"helper rc={r.returncode} stderr={(r.stderr or '').strip()}"
                _log_error(msg, "DisplayRefresh")
                self._last_refresh_probe_err = msg
                return None
            data = (r.stdout or "").strip()
            _log_debug(f"helper stdout: {data}", "DisplayRefresh")
            if not data:
                self._last_refresh_probe_err = "empty stdout from helper"
                return None
            try:
                obj = json.loads(data)
            except Exception as je:
                msg = f"json decode error: {je}; stdout starts: {data[:200]}"
                _log_error(msg, "DisplayRefresh")
                self._last_refresh_probe_err = msg
                return None
            val = obj.get("builtin_hz_actual") or obj.get("builtin_hz_nominal")
            if isinstance(val, (int, float)) and val > 0:
                s = f"{val:.2f}".rstrip("0").rstrip(".")
                return f"{s}Hz"
            self._last_refresh_probe_err = f"no hz in json: {obj}"
            return None
        except Exception as e:
            msg = f"run helper error: {e}"
            log_exception_once(e, "DisplayRefresh")
            self._last_refresh_probe_err = msg
            return None

    @staticmethod
    def _get_computer_name() -> Optional[str]:
        """Return ComputerName from scutil, fallback to GeneralDiagnostics."""
        try:
            r = subprocess.run(["scutil", "--get", "ComputerName"], capture_output=True, text=True, check=False)
            name = (r.stdout or "").strip()
            if name:
                return name
        except Exception:
            pass
        try:
            g = GeneralDiagnostics.fetch()
            return g.get("computer") or g.get("model")
        except Exception:
            return None

    def _normalize_display_rows(
            self,
            rows: List[Tuple[str, str, str, str, str]],
            d: Dict[str, Any]
    ) -> List[Tuple[str, str, str, str, str]]:
        comp_name = self._get_computer_name() or "Built-in Display"
        raw = d.get("raw") if isinstance(d, dict) else None
        type_hints: Dict[str, str] = self._parse_display_type_hints(raw) if isinstance(raw, str) else {}

        augmented: List[Tuple[str, str, str, str, str, bool]] = []
        for (n, r, m, c, hz) in rows:
            builtin = self._is_builtin_display(n, c, type_hints)
            c = self._coerce_internal_connection(c, builtin)
            if builtin:
                n = comp_name
                if not hz or hz == "?":
                    probed = self._probe_builtin_refresh_rate()
                    if probed:
                        hz = probed
            hz = self._sanitize_refresh(hz) or "?"
            augmented.append((n, r, m, c, hz, builtin))

        augmented.sort(key=lambda x: (0 if x[5] else 1, x[0].lower()))
        return [(n, r, m, c, hz) for (n, r, m, c, hz, _) in augmented]

    # (removed previous _render_display_table, replaced above)

    def _update_display(self) -> Dict[str, Any]:
        d = DisplayDiagnostics.fetch()
        rows = self._extract_display_rows(d)
        header_str, body_str = self._render_display_table(rows)
        disp_header: Optional[tk.Text] = self._widgets.get("display_header_text")  # type: ignore
        disp_body: Optional[tk.Text] = self._widgets.get("display_body_text")  # type: ignore
        if disp_header and disp_body:
            _set_text_widget_content(disp_header, header_str)
            _set_text_widget_content(disp_body, body_str)
            # adjust body height: start at 8, grow up to 16 rows
            rows_count = len(rows)
            disp_body.configure(height=min(max(rows_count, 8), 16))
            # attach tooltip to the body (most content)
            tip = short(d.get("raw"))
            # Send refresh helper errors to terminal / debug log, not the tooltip box
            if self._last_refresh_probe_err:
                msg = "[Refresh probe] " + self._last_refresh_probe_err
                try:
                    print(msg, file=sys.stderr)
                except Exception:
                    pass
                log_debug(msg, "DisplayRefresh")
            add_tooltip(disp_body, tip)
        else:
            # Fallback to single label using full table
            header_str, body_str = self._render_display_table(rows)
            table_text = f"{header_str}\n{body_str}"
            self._set_widget_field(
                "display",
                table_text,
                fg=COLORS["FIELD"],
                tooltip=short(d.get("raw")),
            )
        return d

    def _update_devices(self) -> dict[str, any]:
        """
        Build a two‑column USB device tree (left: name with hierarchy indent,
        right: category), then render into a monospace label so spacing is
        pixel‑perfect. Extra non‑USB peripherals discovered elsewhere are
        appended at root indent level.
        """
        # 1) Parse USB tree from system_profiler ---------------------------
        usb_items = _parse_usb_tree()  # [(indent, vendor, label), …]

        # 2) Merge additional peripherals not in the tree -----------------
        # We only want to *add* peripherals that aren't already represented by
        # the system_profiler USB tree. Structural nodes (Bus/Hub/BILLBOARD)
        # should always come from system_profiler, so we skip structural labels
        # discovered by other scanners. We also avoid adding near-duplicates
        # using the same token-subset heuristic we later use for de-dupe so that
        # extra "Usb3.1 Hub" / "Usb 2.0 Billboard" etc. do not appear.
        tree_labels = {lbl for _, _, lbl in usb_items}
        tree_canon = {_canonical_label(lbl) for lbl in tree_labels}

        existing_leaf_token_sets: list[set[str]] = [
            _token_set0(lbl) for lbl in tree_labels if not _is_structural_label(lbl)
        ]

        for raw in DeviceScanner.scan_all():
            label = _strip_sysprop_prefix(raw)
            if not label or _should_skip_label(label):
                continue
            if _is_structural_label(label):
                # Never introduce structural nodes from auxiliary scanners.
                continue
            label = _ensure_manufacturer_prefix(label)
            key = _canonical_label(label)
            if key in tree_canon:
                continue
            tset = _token_set0(label)
            is_dup = any(tset.issubset(ex) or ex.issubset(tset) for ex in existing_leaf_token_sets)
            if is_dup:
                continue
            usb_items.append((0, None, label))
            tree_labels.add(label)
            tree_canon.add(key)
            existing_leaf_token_sets.append(tset)

        # 2b) Remove duplicates – keep every Bus/Hub, dedupe only leaf devices
        usb_items = _dedupe_usb_items(usb_items)

        if not usb_items:
            self._set_widget_field(
                "devices",
                f"{ICONS['WARN']}  No USB devices",
                fg=COLORS["WARN"],
                tooltip=None,
            )
            return {"devices": [], "lines": []}

        # 3) Build (indent, label, category) tuples -----------------------
        triplets: list[tuple[int, str, str]] = [
            (indent, self._friendly_label(vendor, lbl), self._device_category(lbl))
            for indent, vendor, lbl in usb_items
        ]

        # 4) Pretty‑print into aligned columns (monospace) ----------------
        labels_with_indent = [
            " " * (indent * INDENT_SPACES) + label for indent, label, _ in triplets
        ]
        pad = max(len(s) for s in labels_with_indent) + 2
        formatted_lines = [f"{lbl:<{pad}}{cat}" for lbl, (_, _, cat) in zip(labels_with_indent, triplets)]

        value_string = "\n".join(formatted_lines)

        txt: tk.Text = self._widgets.get("devices_text")  # type: ignore
        if txt:
            _set_text_widget_content(txt, value_string)

        return {"devices": [lbl for _, _, lbl in usb_items], "lines": formatted_lines}

    def _update_ports(self) -> Dict[str, Any]:
        """Fetch & render PortsDiagnostics row."""
        p = PortsDiagnostics.fetch()
        ndev = len(p["devices"])
        _render_status_field(
            self,
            "ports",
            f"{format_count_devices(ndev)} detected",
            bool(ndev),
            tooltip=_safe_tooltip(", ".join(p["devices"])),
        )
        return p

    def _update_input(self) -> Dict[str, Any]:
        """Fetch & render InputDiagnostics row."""
        i = InputDiagnostics.fetch()
        built_in_lines, external_lines = self._friendly_devices(i["details"])
        groups = []
        # Use bolder/more distinct section labels, and add separator if both sections present
        if built_in_lines:
            groups.append("BUILT-IN DEVICES:\n" + "\n".join(built_in_lines))
        if external_lines:
            if built_in_lines:
                groups.append("—" * 18)
            groups.append("EXTERNAL DEVICES:\n" + "\n".join(external_lines))
        if not groups:
            groups = ["Not detected"]
        # Icon and color depend on detection
        is_detected = (built_in_lines or external_lines) and groups != ["Not detected"]
        icon = ICONS["OK"] if is_detected else ICONS["WARN"]
        status_string = f"{icon}\n" + "\n\n".join(groups)
        _render_status_field(
            self,
            "input",
            status_string,
            is_detected,
            tooltip=_safe_tooltip("\n".join(i['details'])),
        )
        return i

    def _update_banner(self, b: Dict[str, Any], s: Dict[str, Any]) -> None:
        """Compute and render the top banner using battery & SSD data with consistent threshold logic."""
        # Use health_state() for both battery and SSD
        bat_state = health_state(b.get('percent_health'))
        ssd_state = health_state(s.get('percent_left'))
        # Use the new worst_state helper to get worst state and affected components
        worst, affected = worst_state(battery=bat_state, ssd=ssd_state)
        self._widgets["banner"].config(
            text=f"{banner_icon(worst)} System Health: {worst.upper()}  "
                 + (f"({', '.join([x.capitalize() for x in affected])})" if affected else ""),
            fg=COLORS["FG"],
            bg=banner_color(worst)
        )

    def _refresh(self) -> None:  # noqa: C901
        """Fetch all diagnostics and update widgets. Broken into helpers for clarity."""
        try:
            if not is_macos():
                self._widgets["banner"].config(
                    text=f"{ICONS['BAD']} Not running on macOS! Exiting.",
                    fg=COLORS["BAD"], bg=COLORS["BG"])
                return
            diagnostics: Dict[str, Any] = {}
            # Dynamically call _update_<key>() methods based on SECTION_ROWS
            for *_, key in SECTION_ROWS:
                updater = getattr(self, f"_update_{key}", None)
                if callable(updater):
                    diagnostics[key] = updater()
                else:
                    _log_warn(f"No updater for section '{key}'", "Main")
            self._last_diag = diagnostics
            self._update_banner(
                diagnostics.get("battery", {}),
                diagnostics.get("ssd", {})
            )
        except Exception as e:  # defensive: never crash the UI
            log_exception_once(e, "MainThread")
            messagebox.showerror("Diagnostics Error", str(e))

    # --- END PER-SECTION UPDATE HELPERS (ADDED) ---#

    def _show_debug_log(self) -> None:
        """
        Show the debug log window.
        """
        win = tk.Toplevel(self)
        win.title("Debug Log")
        win.configure(bg="#101114")
        txt = tk.Text(
            win,
            wrap="word",
            bg="#101114",
            fg="#00f6ff",
            font=(FONT_FAMILY_MONO, 11)
        )
        txt.pack(expand=True, fill="both", padx=10, pady=10)
        txt.insert("end", DebugLogger.get())
        txt.config(state="disabled")
        win.geometry("700x400")


if __name__ == "__main__":
    log_debug("Starting Mac Diagnostics Dashboard", "Main")
    DashboardApp().mainloop()
