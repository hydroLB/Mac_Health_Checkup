from __future__ import annotations  # forward-refs in type hints

# ── stdlib ───────────────────────────────────────────────────────────
import logging
import os
import json
import pty
import re
import subprocess
import sys
import traceback
import time
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Callable

# ── internal constants / aliases ─────────────────────────────────────
CmdList = List[str]            # Type alias for command vectors
PTY_READ_MAX = 65_536          # Std. read size for PTY capture – avoid magic numbers

# Pre‑compiled regexes reused across helpers
HEADER_RE = re.compile(r"^(\s*)([^:\n]+):\s*$")
PROP_RE   = re.compile(r"^(\s*)([^:\n]+):\s*(.+)$")
from enum import Enum, auto

# ── third-party / GUI ────────────────────────────────────────────────
import tkinter as tk  # Tooltip & label helpers

# ── intra-project ────────────────────────────────────────────────────
from constants import (  # colour/font/icon constants and shared state/sets
    COLORS, ICONS, LOG_MAX_LINES,
    TOOLTIP_BG, TOOLTIP_FG, TOOLTIP_FONT,
    COLOR_BG, COLOR_FG,
    FONT_FAMILY_DEFAULT, FONT_SIZE_FIELD, FONT_WEIGHT_NORMAL,
    # Newly imported shared flags / caches / sets / maps
    USE_SUDO,
    _last_exception_msgs, _last_shell_error,
    TB_IGNORES, _NOISE_LABELS, _USB_DEVICE_IGNORES,
    DEVICE_KEYWORD_MAP, _DEVICE_MAP_PATH, DEFAULT_ID_MAP,
)


class DebugLogger:
    """
    Debug log buffer for diagnostics dashboard.
    Keeps a rolling buffer of log entries up to LOG_MAX_LINES.
    """
    _buffer: List[str] = []

    @classmethod
    def log(cls, msg: str) -> None:
        # Always keep buffer size <= LOG_MAX_LINES.
        if len(cls._buffer) >= LOG_MAX_LINES:
            cls._buffer.pop(0)
        cls._buffer.append(msg)

    @classmethod
    def get(cls) -> str:
        return "\n".join(cls._buffer)


class _BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        DebugLogger.log(msg)


# --- CENTRAL LOGGING CONFIG ---#
logger = logging.getLogger("mac_dash")
logger.setLevel(logging.DEBUG)

_buffer_handler = _BufferHandler()
_format = logging.Formatter("[%(asctime)s %(levelname)s%(context)s] %(message)s", "%H:%M:%S")
_buffer_handler.setFormatter(_format)
if not any(isinstance(h, _BufferHandler) for h in logger.handlers):
    logger.addHandler(_buffer_handler)


def _log(msg: str, level: str = "DEBUG", context: Optional[str] = None) -> None:
    logger.log(
        getattr(logging, level.upper(), logging.DEBUG),
        msg,
        extra={"context": f" | {context}" if context else ""}
    )


def log_debug(msg: str, context: Optional[str] = None) -> None:
    """
    Log a debug message to the debug logger.
    """
    _log(msg, "DEBUG", context)


def log_error(msg: str, context: Optional[str] = None) -> None:
    """
    Log an error message to the debug logger.
    """
    _log(msg, "ERROR", context)


def log_exception_once(exc: Exception, context: str = "") -> None:
    """
    Log an exception with traceback, but never log the same error more than once per context.
    Avoids repeated tracebacks for the same error/context pair, preventing log spam.
    Args:
        exc: Exception object to log.
        context: Context string for the error.
    Edge cases:
        - If the same exception is raised repeatedly in the same context, only the first is logged.
        - If a new exception occurs in the same context, it will be logged.
    """
    key = f"{context}:{type(exc).__name__}:{str(exc)}"
    if _last_exception_msgs.get(context) == key:
        return  # Don't spam same error per context
    _last_exception_msgs[context] = key
    tb = traceback.format_exc()
    log_error(f"Exception: {exc}\nTraceback:\n{tb}", context)


# --- END PASSWORD PROMPT UTILS ---#

# --- SECTION: SHELL EXECUTION UTILS ---#
def _format_cmd(cmd: List[str]) -> str:
    """
    Format a shell command list for pretty logging.
    """
    return " ".join(cmd)


def _normalize_shell_error(err: Exception) -> str:
    """
    Normalize all shell-related error messages to a consistent string,
    so that different error types don't spam the log with different text.
    """
    if isinstance(err, subprocess.TimeoutExpired):
        return f"Timeout ({err.timeout}s): {err}"
    elif isinstance(err, subprocess.CalledProcessError):
        return f"Shell failed: {getattr(err, 'output', str(err))}"
    return str(err)


# --- Inserted centralized exception/shell error handlers ---#
def _handle_cmd_exception(e: Exception, context: str) -> str:
    """
    Centralised handler for command‑runner exceptions.
    Normalises the error message and ensures tracebacks are logged only once per context.
    Returns the normalised error message.
    """
    err_msg = _normalize_shell_error(e)
    if _last_shell_error.get(context, "") != err_msg:
        log_exception_once(e, context)
    return err_msg


def _set_shell_error(err_msg: str, context: str) -> None:
    """
    Record a shell error and emit a log line only when the message
    for this context changes. Keeps `_run_cmd_*` noise‑free.
    """
    if _last_shell_error.get(context, "") != err_msg:
        log_error(err_msg, context)
        _last_shell_error[context] = err_msg


# --- Unified command runner for this module ---#

# --- INTERNAL RUNNERS (split from _run_cmd) -------------------------#
def _run_cmd_plain(cmd: CmdList, timeout: int, context: str) -> tuple[str | None, str | None]:
    """Execute *cmd* without sudo and return (stdout, err)."""
    log_debug(f"Running: {_format_cmd(cmd)}", context)
    try:
        stdout = subprocess.check_output(
            cmd,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            text=True,
        )
        _last_shell_error[context] = ""
        return stdout, None

    except subprocess.CalledProcessError as e:
        if e.output:                       # non‑zero exit but usable stdout
            _last_shell_error[context] = ""
            return e.output, None
        err_msg = _normalize_shell_error(e)

    except Exception as e:
        err_msg = _handle_cmd_exception(e, context)

    _set_shell_error(err_msg, context)
    return None, err_msg


def _run_cmd_sudo(cmd: CmdList, timeout: int, context: str) -> tuple[str | None, str | None]:
    """Execute *cmd* via sudo in a PTY and return (stdout, err)."""
    full_cmd = ["sudo"] + cmd
    log_debug(f"Running with sudo: {_format_cmd(full_cmd)}", context)

    try:
        # PTY prevents sudo from blocking on password prompt
        master, slave = pty.openpty()
        proc = subprocess.Popen(
            full_cmd,
            stdin=slave,
            stdout=slave,
            stderr=slave,
            text=True,
            close_fds=True,
        )
        os.close(slave)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            return None, f"Timeout ({timeout}s): Command took too long."

        stdout = os.read(master, PTY_READ_MAX).decode("utf-8", errors="replace")
        _last_shell_error[context] = ""
        return stdout, None

    except subprocess.CalledProcessError as e:
        if e.output:
            _last_shell_error[context] = ""
            return e.output, None
        err_msg = _normalize_shell_error(e)

    except Exception as e:
        err_msg = _handle_cmd_exception(e, context)

    _set_shell_error(err_msg, context)
    return None, err_msg
def _run_cmd(
    cmd: CmdList,
    timeout: int = 10,
    context: str = "",
    use_sudo: bool = False,
) -> tuple[str | None, str | None]:
    """
    Dispatch to the appropriate runner.

    The heavy‑lifting now lives in :func:`_run_cmd_plain` and
    :func:`_run_cmd_sudo`; this wrapper simply selects the correct
    implementation.  Its public signature is unchanged, so all call‑sites
    remain valid.
    """
    runner = _run_cmd_sudo if use_sudo else _run_cmd_plain
    return runner(cmd, timeout=timeout, context=context)



def _run_plain(cmd: list[str], timeout: int = 10, context: str = "") -> tuple[str | None, str | None]:
    # Deprecated – kept for backward‑compatibility
    return _run_cmd_plain(cmd, timeout=timeout, context=context)


def _run_sudo_via_pty(cmd: list[str], timeout: int = 10, context: str = "") -> tuple[str | None, str | None]:
    # Deprecated – kept for backward‑compatibility
    return _run_cmd_sudo(cmd, timeout=timeout, context=context)


def safe_run(
        cmd: List[str],
        context: str = "",
        allow_sudo: bool = USE_SUDO,
        timeout: int = 10
) -> Tuple[Optional[str], Optional[str]]:
    """
    Run a shell command **without sudo first**. If the plain attempt fails, and
    ``allow_sudo`` is True, retry the same command via sudo.

    Failure definition:
        • non‑zero return code, or
        • raised exception, or
        • empty / whitespace‑only stdout.

    Args:
        cmd: Command vector to execute.
        context: Short tag used for structured logging and error de‑duplication.
        allow_sudo: Permit a sudo retry when the plain attempt fails. Global
            ``USE_SUDO`` can disable escalation project‑wide; both must be True
            for a sudo attempt to run.
        timeout: Seconds before a command is killed.

    Returns:
        (stdout, error_message) — on success ``error_message`` is ``None``.
        When both attempts fail, the *last* error message is returned.
    """
    # 1) Plain attempt -------------------------------------------------
    out, err = _run_cmd(cmd, timeout=timeout, context=context, use_sudo=False)
    if out and out.strip():
        return out, None

    # Not allowed to escalate?
    if not (allow_sudo and USE_SUDO):
        return None, err or "Empty output from command"

    # 2) Sudo fallback --------------------------------------------------
    out2, err2 = _run_cmd(cmd, timeout=timeout, context=context, use_sudo=True)
    if out2 and out2.strip():
        return out2, None

    return None, err2 or err or "Command failed"


# The get_sudo_password function is no longer needed (admin dialog is handled by osascript)

# ==== END SHELL EXECUTION UTILS ====


# ----------------------------------------------------------------------
# Unified Health enum (replaces scattered helper tables)
# ----------------------------------------------------------------------
class Health(Enum):
    GOOD = auto()
    WARN = auto()
    BAD = auto()

    @classmethod
    def from_percent(cls, pct: Optional[float]) -> "Health":
        """
        Convert a percentage (0‑100) to a Health enum:
          • None   → WARN (unknown is treated as caution)
          • ≥90    → GOOD
          • ≥70    → WARN
          • else   → BAD
        """
        if pct is None:
            return cls.WARN
        if pct >= 90:
            return cls.GOOD
        if pct >= 70:
            return cls.WARN
        return cls.BAD

    # ----- Presentation helpers ----------------------------------------
    def __str__(self) -> str:        # e.g. "good"
        return self.name.lower()

    @property
    def color(self) -> str:
        return {
            Health.GOOD: COLORS["OK"],
            Health.WARN: COLORS["WARN"],
            Health.BAD: COLORS["BAD"],
        }[self]

    @property
    def icon(self) -> str:
        return {
            Health.GOOD: ICONS["OK"],
            Health.WARN: ICONS["WARN"],
            Health.BAD: ICONS["BAD"],
        }[self]

    @property
    def banner_color(self) -> str:
        return {
            Health.GOOD: COLORS["BANNER_GOOD"],
            Health.WARN: COLORS["BANNER_WARN"],
            Health.BAD: COLORS["BANNER_BAD"],
        }[self]

    @property
    def banner_icon(self) -> str:
        return {
            Health.GOOD: ICONS["OK"],
            Health.WARN: ICONS["WARN"],
            Health.BAD: ICONS["BAD"],
        }[self]

def health_state(percent: Optional[float]) -> str:
    return str(Health.from_percent(percent))


def worst_state(**states) -> tuple[str, list[str]]:
    """
    Given named component states (e.g. battery="good", ssd="warn"), return:
    - The worst state (bad > warn > good)
    - List of component names whose state is not "good"
    Example: worst_state(battery="warn", ssd="bad") -> ("bad", ["battery", "ssd"])
    """
    # Define state priorities
    priority = {"good": 0, "warn": 1, "bad": 2}
    state_items = list(states.items())
    # Determine the worst state by priority
    worst = max((s for _, s in state_items), key=lambda st: priority.get(st, -1), default="good")
    # List which components are not good
    affected = [name for name, state in state_items if state != "good"]
    return worst, affected


def health_color(percent: Optional[float]) -> str:
    return Health.from_percent(percent).color


def health_icon(percent: Optional[float]) -> str:
    return Health.from_percent(percent).icon


def banner_color(state: str) -> str:
    try:
        return Health[state.upper()].banner_color
    except KeyError:
        return COLORS["BANNER_BAD"]


def banner_icon(state: str) -> str:
    try:
        return Health[state.upper()].banner_icon
    except KeyError:
        return ICONS["UNKNOWN"]


def is_macos() -> bool:
    """
    Detect macOS platform.
    Returns:
        bool: True if running on macOS, else False.
    """
    return sys.platform == "darwin"


def create_label(
        parent: tk.Widget,
        text: str,
        font: Tuple[str, int, str] = (FONT_FAMILY_DEFAULT, FONT_SIZE_FIELD, FONT_WEIGHT_NORMAL),
        fg: str = COLOR_FG,
        bg: str = COLOR_BG,
        sticky: str = "w",
        padx: int = 6,
        pady: int = 3,
        tooltip: Optional[str] = None
) -> tk.Label:
    """
    Create a Tkinter label with given options and optional tooltip.
    All font/color values are constants.
    Args:
        parent: Parent Tkinter widget.
        text: Label text.
        font: Font tuple.
        fg: Foreground color.
        bg: Background color.
        sticky: Grid sticky.
        padx: Grid x padding.
        pady: Grid y padding.
        tooltip: Tooltip text or None. Tooltip will be attached if provided or None/empty is ignored.
    Returns:
        tk.Label: The created label.
    """
    lbl = tk.Label(parent, text=text, font=font, fg=fg, bg=bg)
    lbl.grid(sticky=sticky, padx=padx, pady=pady)
    add_tooltip(lbl, tooltip)
    return lbl


def add_tooltip(widget: tk.Widget, text: str) -> None:
    """
    Attach a tooltip to a widget, if not already present.
    Callers may always pass None or empty text; does nothing in that case.
    Checks for existing tooltip to avoid multiple attachments.
    Args:
        widget: Tkinter widget to attach tooltip.
        text: Tooltip text (may be None or empty; in that case, does nothing).
    Edge cases:
        - If tooltip already attached, does nothing.
    """
    if not text:
        return
    if not hasattr(widget, "_tooltip") or not getattr(widget, "_tooltip", None):
        widget._tooltip = Tooltip(widget, text)


class Tooltip:
    """
    Tkinter Tooltip - Mouse-over help for widgets.
    Handles bbox failures robustly.
    Only one tooltip per widget.
    """

    def __init__(self, widget: tk.Widget, text: str = "") -> None:
        self.widget = widget
        self.text = text
        self.tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", lambda event: self.show())
        widget.bind("<Leave>", lambda event: self.hide())

    def show(self) -> None:
        if self.tip or not self.text:
            return
        try:
            bbox = self.widget.bbox(None)
            x, y = bbox[:2] if bbox else (0, 0)
        except Exception:
            x, y = 0, 0
        try:
            x = x + self.widget.winfo_rootx() + 50
            y = y + self.widget.winfo_rooty() + 10
        except Exception:
            x, y = 100, 100
        self.tip = tw = tk.Toplevel(self.widget)
        tw.overrideredirect(True)
        tw.geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify='left',
            background=TOOLTIP_BG,
            fg=TOOLTIP_FG,
            relief='solid',
            borderwidth=1,
            font=TOOLTIP_FONT
        )
        label.pack(ipadx=6, ipady=2)

    def hide(self) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


def update_result_with_defaults(result: Dict[str, Any], defaults: Dict[str, Any]) -> None:
    """
    Merge defaults into result dict if missing.
    Ensures all required keys are present.
    Args:
        result: The result dictionary to update.
        defaults: The defaults dictionary.
    Edge cases:
        - If result already has a key, it is not overwritten.
    """
    for k, v in defaults.items():
        if k not in result:
            result[k] = v


# ----------------------------------------------------------------------
# Lightweight TTL memoisation decorator (used by DeviceScanner, etc.)
# ----------------------------------------------------------------------
def memo_ttl(ttl_seconds: int):
    """
    Simple memoisation decorator with a time‑to‑live cache.

    Example
    -------
        @memo_ttl(60)
        def heavy_computation(x):
            ...

    The cache key is built from function positional and keyword arguments.
    """
    def decorator(func: Callable):
        _cache: Dict[Tuple, Tuple[float, Any]] = {}

        @wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            entry = _cache.get(key)
            if entry and now - entry[0] < ttl_seconds:
                return entry[1]
            result = func(*args, **kwargs)
            _cache[key] = (now, result)
            return result

        return wrapper
    return decorator


# ==== END DICTIONARY UPDATE UTILS ====

# --- SECTION: SHARED HELPER UTILITIES (ADDED) ---#


def c_to_f(temp_c: Optional[float]) -> Optional[int]:
    """Convert Celsius to Fahrenheit, returns int or None."""
    if temp_c is None:
        return None
    return int(round((temp_c * 9 / 5) + 32))


# Null-aware string for UI display fields
def na(val, placeholder="N/A"):
    """Null-aware string for all UI display fields, replaces None (and optionally empty string) with a placeholder."""
    if val is None:
        return placeholder
    return val


def _strip_sysprop_prefix(label: str) -> str:
    """
    Remove noisy prefixes such as 'Vendor Name:', 'Device Name:' or 'Uid:'
    that sometimes leak from `system_profiler` output. If the remaining text
    is empty or just a hex UID, return an empty string so the caller can
    ignore it.
    """
    cleaned = re.sub(r'^(Vendor|Device|Uid)[^:]*:\s*', '', label,
                     flags=re.IGNORECASE).strip()
    # Drop pure hex UIDs like 0x05A9…
    if re.fullmatch(r'0[xX][0-9a-fA-F]+', cleaned):
        return ""
    return cleaned


def _ensure_manufacturer_prefix(label: str) -> str:
    """
    Ensure the label starts with a manufacturer rather than a generic noun.
    If the first token is generic (USB, Receiver, Hub, Device) and a second
    token exists, prepend that token as a pseudo‑manufacturer.  We never
    duplicate a word that is already present.
    """
    parts = label.split()
    if len(parts) < 2:
        return label
    generic_first = {"usb", "receiver", "hub", "device"}
    if parts[0].lower() in generic_first:
        manu = parts[1]
        # Skip if manu has no alphabetic characters (e.g. "2.0" or "10_100")
        if not any(ch.isalpha() for ch in manu):
            return label
        if not label.lower().startswith(manu.lower()):
            return f"{manu} {' '.join(parts)}"
    return label


def _canonical_label(label: str) -> str:
    """
    Create a canonical form for de‑duplication:
      • lower‑case
      • underscores → spaces
      • collapse runs of whitespace
      • strip punctuation
    """
    s = label.lower().replace("_", " ")
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^\w\s]", "", s)
    return s.strip()


def _should_skip_label(label: str) -> bool:
    """
    Return True for labels we never want to show in the Devices list:
        • Pure hex UIDs (already handled earlier, but guard anyway)
        • Host‑centric vendor strings like "Apple Inc." or "MacBook Pro"
    """
    l_skip = label.strip().lower()
    if any(k in l_skip for k in TB_IGNORES):
        return True
    if not l_skip or l_skip in _NOISE_LABELS:
        return True
    if re.fullmatch(r'0[xX][0-9a-fA-F]+', l_skip):
        return True
    return False


def _is_usb_tree_device_line(label: str) -> bool:
    """
    Return True if a line from `system_profiler SPUSBDataType` represents a
    device/bus we want to show (and not a property such as “Product ID:”).
    """
    l_bus = label.lower().strip(":")
    if not l_bus or l_bus in _NOISE_LABELS:
        return False
    if any(l_bus.startswith(p) for p in _USB_DEVICE_IGNORES):
        return False
    # Skip long hex/UUID‑like strings
    if re.fullmatch(r"[0-9a-f]{8,}", l_bus) or re.fullmatch(r"[0-9a-f-]{30,}", l_bus):
        return False
    return True


def _extract_usb_tree_items(out: str) -> list[dict[str, Any]]:
    """
    Internal helper for :func:`_parse_usb_tree`. Splits the raw
    `system_profiler SPUSBDataType` output into a list of dict nodes:
        {"indent": int, "label": str, "vendor": Optional[str]}.

    The implementation keeps the original on‑screen ordering exactly as
    produced by `system_profiler`, while a light‑weight state machine
    attaches any subsequent vendor/manufacturer property lines to the
    most‑recently emitted header node.  This isolates the heavy parsing
    logic so the public‐facing :func:`_parse_usb_tree` wrapper remains
    concise and unit‑testable.
    """

    items: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []

    for line in out.splitlines():
        # ── Header line (new node) ─────────────────────────────────────
        m = HEADER_RE.match(line)
        if m:
            indent_spaces, label = m.group(1), m.group(2).strip()
            # Skip the super‑root “USB:” entry shown by system_profiler
            if label.lower() == "usb" and len(indent_spaces) == 0:
                continue
            indent = len(indent_spaces) // 4 - 1  # shift tree one level left

            # Collapse stack to the parent of this node
            while stack and stack[-1]["indent"] >= indent:
                stack.pop()

            node = {"indent": indent, "label": label, "vendor": None}
            items.append(node)
            stack.append(node)
            continue

        # ── Property line (maybe vendor/manufacturer) ─────────────────
        m = PROP_RE.match(line)
        if m and stack:
            _indent_spaces, key, val = m.groups()
            if key.lower().strip() in {"vendor name", "manufacturer"} and val.strip():
                stack[-1]["vendor"] = val.strip()

    return items


def _parse_usb_tree() -> list[tuple[int, Optional[str], str]]:
    """
    Parse `system_profiler SPUSBDataType` output into a list of
    (indent, vendor, label) tuples.  A tiny state‑machine keeps a stack
    of open nodes so vendor/manufacturer lines are attached only to the
    correct parent.

    Robust against unknown devices: if no vendor found the vendor field
    is None and handled later by _friendly_label().
    """
    out, _ = safe_run(["system_profiler", "SPUSBDataType"], "USBTree")
    if not out:
        return []

    items = _extract_usb_tree_items(out)

    # Filter out noise lines and convert to the public tuple format
    return [
        (n["indent"], n["vendor"], n["label"])
        for n in items
        if _is_usb_tree_device_line(n["label"])
    ]


# --- END USB TREE PARSING HELPERS -----------------------------------


# --- REGEX FIELD EXTRACTOR ---
def regex_extract(text: str, pattern: str, cast_func=lambda x: x) -> Optional[Any]:
    """
    One-liner regex field parser: finds the first group from `pattern` in `text`, returns cast_func(group).
    Args:
        text: Raw string to search.
        pattern: Regex pattern, must contain one group.
        cast_func: Callable to cast group (default str).
    Returns:
        Optional[Any]: Cast group or None.
    """
    pat = re.compile(pattern)
    m = safe_match(pat, text)
    return cast_func(m.group(1)) if m else None



# --- REGEX FIELD EXTRACTOR HELPERS ---

def _to_int_safe(val: str) -> Optional[int]:
    """
    Convert a numeric‑looking string to int.

    Accepts strings with commas, percent signs or floats
    (e.g. '95.0', '1,024', '42%'). Returns None on any
    parse error so callers don’t need try/except blocks.
    """
    if val is None:
        return None
    cleaned = val.strip().replace('%', '').replace(',', '')
    # Direct integer string?
    if re.fullmatch(r'[-+]?\d+', cleaned):
        try:
            return int(cleaned)
        except Exception:
            return None
    # Acceptable float fallback (e.g. "95.0")
    try:
        return int(float(cleaned))
    except Exception:
        return None


def regex_extract_int(text: str, pattern: str) -> Optional[int]:
    """
    Regex int extractor that delegates to :func:`regex_extract`
    using the shared `_to_int_safe` helper.
    """
    return regex_extract(text, pattern, _to_int_safe)


def regex_extract_float(text: str, pattern: str) -> Optional[float]:
    return regex_extract(text, pattern, float)


def regex_extract_str(text: str, pattern: str) -> Optional[str]:
    return regex_extract(text, pattern, str)


# --- SHARED REGEX / TEXT‑PARSING HELPERS (moved from DiagnosticSection) ---

def safe_match(pattern: re.Pattern[str], text: str):
    """
    Safe wrapper around pattern.search(text); returns None on error.
    Mirrors DiagnosticSection.safe_match but is usable project‑wide.
    """
    try:
        return pattern.search(text)
    except Exception as exc:
        logger.debug(f"[Regex] search failed: {exc}")
        return None


def safe_findall(pattern: re.Pattern[str], text: str):
    """
    Safe wrapper around pattern.findall(text); returns [] on error.
    Mirrors DiagnosticSection._safe_findall for shared use.
    """
    try:
        return [m for m in pattern.findall(text)]  # type: ignore[return-value]
    except Exception as exc:
        logger.debug(f"[Regex] findall failed: {exc}")
        return []


def hz_from_text(s: str):
    """
    Extract a display refresh‑rate string (e.g., '60Hz') from arbitrary text.

    Returns:
        str like "60Hz", or None if no Hz value is found.
    """
    m = re.search(r"@\s*(\d+(?:\.\d+)?)\s*Hz", s, flags=re.I)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*Hz", s, flags=re.I)
    if not m:
        return None
    val = m.group(1)
    if val.endswith(".00"):
        val = val[:-3]
    return f"{val}Hz"


def classify_device(raw_name: str) -> str:
    """
    Convert a raw device/product string to a friendly label.

    The matching strategy is:
        1. Iterate DEVICE_KEYWORD_MAP in declaration order and return the first
           friendly label whose regex matches ``raw_name`` (case‑insensitive).
        2. Fallback – title‑case the original string.

    Args:
        raw_name: Product string as reported by system_profiler/ioreg.

    Returns:
        str: Friendly label suitable for UI display.
    """
    name_lower = raw_name.lower()
    for pattern, friendly in DEVICE_KEYWORD_MAP.items():
        if re.search(pattern, name_lower):
            return friendly
    return raw_name.strip().title()


def _load_external_id_map() -> dict[tuple, Any]:
    """
    Load an optional JSON file with keys like '046d/c52b' → label.
    Silently ignores any problems and returns {}.
    """
    try:
        with open(_DEVICE_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                tuple(k.lower().split("/")): v
                for k, v in data.items()
                if "/" in k
            }
    except Exception:
        return {}


ID_MAP: Dict[Tuple[str, str], str] = {**DEFAULT_ID_MAP, **_load_external_id_map()}


def classify_by_ids(vendor: str, product: str) -> Optional[str]:
    """Return friendly label for a vendor/product hex pair, or None."""
    return ID_MAP.get((vendor.lower(), product.lower()))


def system_profiler_out(datatype: str, context: str) -> Tuple[Optional[str], Optional[str]]:
    """Small convenience wrapper around :func:`safe_run` for system_profiler calls.
    Keeps call sites concise and consistent.
    Args:
        datatype: e.g. "SPHardwareDataType", "SPDisplaysDataType".
        context: Logging context string.
    Returns: (stdout, error_message) tuple directly from :func:`safe_run`.
    """
    return safe_run(["system_profiler", datatype], context)


def short(text: Optional[str], limit: int = 1200, fallback: str = "No details") -> str:
    """Return a truncated tooltip‑safe string.
    Ensures we never index None and centralises the slice logic that was repeated.
    """
    if not text:
        return fallback
    if len(text) <= limit:
        return text
    return text[:limit]


def format_count_devices(n: int, singular: str = "device", plural: str = "devices") -> str:
    """Utility for consistent singular/plural formatting used in multiple places."""
    return f"{n} {singular if n == 1 else plural}"
