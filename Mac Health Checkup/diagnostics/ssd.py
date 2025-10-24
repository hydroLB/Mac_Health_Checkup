from __future__ import annotations          # keep first, if already present

# ── standard library ───────────────────────────────────────────────
import re
from typing import Any, Dict

# ── internal diagnostics helpers & constants ──────────────────────
from constants import USE_SUDO                     # sudo-escalation flag
from diagnostics.logging_utils import logger                   # noqa: F401  (import for side-effect)
from utils import (                                # regex + shell helpers
    safe_run,
    regex_extract_float,
    update_result_with_defaults,
    regex_extract_int,
    regex_extract_str,
    na,
)
from diagnostics.base import (                                 # shared formatters & utils
    fmt_percent,
    fmt_bytes,
    debug_msg,
    log_exc,
    smartctl_temperature_str
)


NVME_BYTES_PER_DU: float = 512_000.0  # NVMe spec: one Data Unit = 512,000 bytes


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
            temp_str = smartctl_temperature_str(out)
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
