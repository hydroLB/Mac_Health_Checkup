from __future__ import annotations  # keep first if you already use it

# ── standard library ───────────────────────────────────────────────
import platform
from typing import Any, Dict, Optional
from constants import MODEL_RE, SERIAL_RE
# ── internal diagnostics helpers ──────────────────────────────────
from utils import na
from diagnostics.fan import system_profiler_out  # thin wrapper around `system_profiler`
from diagnostics.base import safe_match

UNKNOWN_TOKENS: tuple[str, ...] = ("?", "Unknown")


class GeneralDiagnostics:
    """
    General system info (model, serial, OS) section builder.
    Produces a row/section with identifying info for the Mac.
    """

    @staticmethod
    def _parse_serial(text: str) -> Optional[str]:
        m = safe_match(SERIAL_RE, text)
        return m.group(1).strip() if m else None

    @staticmethod
    def _parse_model(text: str) -> Optional[str]:
        m = safe_match(MODEL_RE, text)
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
