from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import fmt_bytes, fmt_percent
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils import health_from_percent
from mac_health_checkup.diagnostics.ssd import SSDDiagnostics as SSDDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/ssd.py"
__all__ = ["SSDDiagnostics", "update_section"]


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the SSD section fields from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host fields and metrics.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps SSD rendering logic isolated.
    """
    try:
        data = SSDDiagnostics.fetch()
        thresholds = get_config().thresholds
        summary = str(data.get("health_text", "SSD info unavailable"))
        host.set_field("ssd", summary)
        percent_left = data.get("percent_left")
        percent_val = float(percent_left) if isinstance(percent_left, (int, float)) else None
        health_label = (
            health_from_percent(
                percent_val,
                excellent_min=thresholds.health_excellent_min_percent,
                good_min=thresholds.health_good_min_percent,
                fair_min=thresholds.health_fair_min_percent,
            )
            if percent_val is not None
            else "unknown"
        )
        health_status = "unknown"
        if health_label in {"excellent", "good"}:
            health_status = "ok"
        elif health_label == "fair":
            health_status = "warn"
        elif health_label == "degraded":
            health_status = "bad"

        written_tb = data.get("data_written")
        written_val = float(written_tb) if isinstance(written_tb, (int, float)) else None
        read_tb = data.get("data_read")
        read_val = float(read_tb) if isinstance(read_tb, (int, float)) else None
        unsafe_shutdowns = data.get("unsafe_shutdowns")
        media_errors = data.get("media_errors")
        power_cycles = data.get("power_cycles")
        power_on_hours = data.get("power_on_hours")
        firmware = data.get("firmware")

        rows: list[tuple[str, str, str]] = []
        if percent_val is not None:
            rows.append(("Life remaining", f"{fmt_percent(percent_val)} ({health_label})", health_status))
        if read_val is not None:
            rows.append(("Total read", fmt_bytes(read_val * 1e12), "info"))
        if written_val is not None:
            rows.append(("Total written", fmt_bytes(written_val * 1e12), "info"))
        if isinstance(unsafe_shutdowns, int):
            status = "warn" if unsafe_shutdowns >= int(thresholds.ssd_unsafe_shutdowns_warn_count) else "ok"
            rows.append(("Unsafe shutdowns", f"{unsafe_shutdowns:,}", status))
        if isinstance(media_errors, int):
            status = "bad" if media_errors >= int(thresholds.ssd_media_errors_bad_count) else "ok"
            rows.append(("Media errors", f"{media_errors:,}", status))
        if isinstance(power_cycles, int):
            rows.append(("Power cycles", f"{power_cycles:,}", "info"))
        if isinstance(power_on_hours, int):
            days = power_on_hours / 24.0
            rows.append(("Power on", f"{power_on_hours:,} h ({days:.0f} d)", "info"))
        if isinstance(firmware, str) and firmware.strip():
            rows.append(("Firmware", firmware.strip(), "info"))
        if rows:
            host.render_metrics_table("ssd", rows, columns=2)
        data["ok"] = percent_val is not None or bool(rows)
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update SSD section", exc)
        ) from exc
