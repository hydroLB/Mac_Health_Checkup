"""
Mac Health Checkup — constants

Purpose
    Centralize colors, icons, fonts, UI sizes, logging formats, timeouts, and
    device‑parsing constants. Kept stable and well‑typed to make future changes safe.

Table of Contents
  1. Colors
  2. Icons
  3. Fonts & Tooltips
  4. General UI / Logging / Timeouts
  5. Utilities: parsing labels & ignores
  6. Diagnostics: fan name map
"""

from __future__ import annotations

import os
from typing import Dict, Tuple, Optional, Final, Mapping
import re

# =============================== 1. COLORS ===============================
COLOR_BG: Final[str] = "#23272e"
COLOR_FG: Final[str] = "#ffffff"
COLOR_OK: Final[str] = "#2ecc40"
COLOR_WARN: Final[str] = "#ffdc00"
COLOR_BAD: Final[str] = "#ff4136"
COLOR_SECTION: Final[str] = "#339af0"
COLOR_LABEL: Final[str] = "#f1c40f"
COLOR_FIELD: Final[str] = "#daf6ff"
COLOR_BANNER_GOOD: Final[str] = "#28a745"
COLOR_BANNER_WARN: Final[str] = "#ffc107"
COLOR_BANNER_BAD: Final[str] = "#dc3545"

COLORS: Dict[str, str] = {
    "BG"         : COLOR_BG,
    "FG"         : COLOR_FG,
    "OK"         : COLOR_OK,
    "WARN"       : COLOR_WARN,
    "BAD"        : COLOR_BAD,
    "SECTION"    : COLOR_SECTION,
    "LABEL"      : COLOR_LABEL,
    "FIELD"      : COLOR_FIELD,
    "BANNER_GOOD": COLOR_BANNER_GOOD,
    "BANNER_WARN": COLOR_BANNER_WARN,
    "BANNER_BAD" : COLOR_BANNER_BAD,
}

# =============================== 2. ICONS ================================
ICON_OK: Final[str] = "🟢"
ICON_WARN: Final[str] = "🟡"
ICON_BAD: Final[str] = "🔴"
ICON_UNKNOWN: Final[str] = "⚪️"

ICONS: Dict[str, str] = {
    "OK"     : ICON_OK,
    "WARN"   : ICON_WARN,
    "BAD"    : ICON_BAD,
    "UNKNOWN": ICON_UNKNOWN,
}

# ======================== 3. FONTS & TOOLTIPS ===========================
FONT_FAMILY_DEFAULT: Final[str] = "Helvetica"
FONT_FAMILY_MONO: Final[str] = "Consolas"
FONT_SIZE_SECTION: Final[int] = 16
FONT_SIZE_BANNER: Final[int] = 18
FONT_SIZE_FIELD: Final[int] = 13
FONT_SIZE_TOOLTIP: Final[int] = 10
FONT_WEIGHT_BOLD: Final[str] = "bold"
FONT_WEIGHT_NORMAL: Final[str] = "normal"

TOOLTIP_BG: Final[str] = "#1a1c20"
TOOLTIP_FG: Final[str] = "#f0f0f0"

TOOLTIP_FONT: Final[tuple[str, int, str]] = (
    FONT_FAMILY_DEFAULT,
    FONT_SIZE_TOOLTIP,
    FONT_WEIGHT_NORMAL,
)

# ================= 4. GENERAL UI / LOGGING / TIMEOUTS ===================
WINDOW_SIZE: Final[str] = "790x850"
LOG_MAX_LINES: Final[int] = 500
DEBUG_LOG_PREFIX: Final[str] = "[{timestamp} {level}{context}]"
DEBUG_LOG_TRUNCATE_LEN: Final[int] = 1000
CACHE_TTL: Final[int] = 30          # seconds; DeviceScanner cache TTL
DEFAULT_CMD_TIMEOUT: Final[int] = 10  # seconds; generic subprocess timeout
SMARTCTL_TIMEOUT: Final[int] = 10     # seconds; smartctl subprocess timeout
SUDO_PTY_TIMEOUT: Final[int] = 10     # seconds for sudo pty commands

# ===================== 5. UTILITIES: LABELS & IGNORES ====================
TB_IGNORES: set[str] = {
    "domain uuid", "route string", "receptacle", "port",
    "status", "link status", "speed",
}

_USB_DEVICE_IGNORES: set[str] = {
    "product id",
    "vendor id",
    "location id",
    "serial number",
    "manufacturer",
    "current available",
    "current required",
    "extra operating current",
    "bus power",
    "connection",
    "resources",
    "port",
    "route string",
    "domain uuid",
    "descriptor",
    "speed",
    "host controller driver",
    "receptacle",
    "link status",
    "status",
}

_last_exception_msgs: Dict[str, str] = {}
_NOISE_LABELS: set[str] = {"apple inc.", "macbook pro"}

# Regex pattern (case-insensitive) -> human-friendly device label
DEVICE_KEYWORD_MAP: Dict[str, str] = {
    r"usb[\\s\\-]*hub"                      : "USB Hub",
    r"ethernet.*(adapter|controller|dongle)": "Ethernet Adapter",
    r"logitech.*mouse"                      : "Logitech Mouse",
    r"logitech.*keyboard"                   : "Logitech Keyboard",
    r"razer.*mouse"                         : "Razer Mouse",
    r"razer.*keyboard"                      : "Razer Keyboard",
    r"magic.*mouse"                         : "Apple Magic Mouse",
    r"magic.*keyboard"                      : "Apple Magic Keyboard",
    r"trackpad"                             : "Trackpad",
    r"internal.*keyboard"                   : "Internal Keyboard",
    r"internal.*mouse"                      : "Internal Mouse",
    r"keyboard"                             : "Keyboard",
    r"mouse"                                : "Mouse",
}
_DEVICE_MAP_PATH: Final[str] = os.path.join(os.path.dirname(__file__), "device_map.json")

# Fallback map of (idVendor, idProduct) ➜ friendly label
DEFAULT_ID_MAP: Dict[Tuple[str, str], str] = {
    ("046d", "c52b"): "Logitech Unifying Receiver",
    ("05ac", "8102"): "Apple Internal Keyboard/Trackpad",
}
_last_shell_error: Dict[str, str] = {}
_admin_password: Optional[str] = None

# ======================= 6. DIAGNOSTICS: FAN MAP ========================
USE_SUDO: Final[bool] = False  # Global toggle to allow or disallow sudo use
#
# Model→friendly fan names. These are best‑effort defaults used when macOS/iStats
# do not provide human‑readable labels. Keys are regex patterns that match
# the **Model Identifier** (e.g. "Mac14,6", "MacBookPro18,2").
FAN_NAME_MAP: list[tuple[str, list[str]]] = [
    (r"^Mac14,(6|10)$", ["Left side", "Right side"]),            # MBP 16" (2023, M2 Pro/Max)
    (r"^MacBookPro18,\d+$", ["Left side", "Right side"]),        # MBP 16" (2021, M1 Pro/Max)
    (r"^MacBookPro16,1$", ["Left side", "Right side"]),          # MBP 16" (2019, Intel)
    (r"^MacBookPro1[345],\d+$", ["Left", "Right"]),             # Older 13"/15" Pros
    (r"^MacBookAir", ["Main fan"]),                                # Most Airs have a single fan
    (r"^iMacPro1,1$", ["Intake", "Exhaust"]),                     # iMac Pro 2017
    (r"^iMac", ["Left", "Right", "Exhaust"]),                     # Generic iMac multi‑fan layout
    (r"^MacPro", ["Fan 1", "Fan 2", "Fan 3", "Fan 4"])          # Generic Mac Pro
]

SERIAL_RE: Final[re.Pattern[str]] = re.compile(r"Serial Number.*?: (.+)")

MODEL_RE: Final[re.Pattern[str]] = re.compile(r"Model Identifier: (.+)")
