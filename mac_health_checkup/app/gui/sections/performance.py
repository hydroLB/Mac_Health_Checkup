from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.power import PowerResidencyDiagnostics
from mac_health_checkup.diagnostics.thermals import ThermalSensorsDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/performance.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Performance section fields from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host fields and metrics table.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps performance rendering logic isolated.
    """
    try:
        thermals = ThermalSensorsDiagnostics.fetch()
        power = PowerResidencyDiagnostics.fetch()
        rows: list[tuple[str, str, str]] = []
        sensors = thermals.get("sensors")
        hottest_label = ""
        hottest_c: float | None = None
        if isinstance(sensors, list) and sensors:
            for item in sensors:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label", "")).strip()
                value = item.get("celsius")
                status = str(item.get("status", "info"))
                if label and isinstance(value, (int, float)):
                    rows.append((label, f"{float(value):.0f}C", status))
                    if hottest_c is None or float(value) > hottest_c:
                        hottest_c = float(value)
                        hottest_label = label
        cpu_w = power.get("cpu_w")
        gpu_w = power.get("gpu_w")
        ane_w = power.get("ane_w")
        if cpu_w is not None:
            rows.append(("CPU Power", f"{cpu_w} W", "info"))
        if gpu_w is not None:
            rows.append(("GPU Power", f"{gpu_w} W", "info"))
        if ane_w is not None:
            rows.append(("ANE Power", f"{ane_w} W", "info"))
        if hottest_c is not None:
            host.set_field("performance", f"Hottest: {hottest_c:.0f}C {hottest_label}".strip())
        else:
            power_summary = _power_summary(cpu_w=cpu_w, gpu_w=gpu_w, ane_w=ane_w)
            host.set_field("performance", power_summary or "Performance data unavailable")
        host.render_metrics_table("performance", rows, columns=2)
        return {"thermals": thermals, "power": power}
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Performance section", exc)
        ) from exc


def _power_summary(*, cpu_w: object, gpu_w: object, ane_w: object) -> str:
    """
    Summary
    Build a one-line power summary field from available component power values.

    Inputs
    cpu_w: Optional CPU watts value.
    gpu_w: Optional GPU watts value.
    ane_w: Optional ANE watts value.

    Outputs
    Summary string or empty string when no usable values exist.

    Side effects
    None.

    Error handling
    Never raises; malformed values are ignored.

    Ties to other methods
    Used by `update_section` when temperature sensors are unavailable.

    Why this exists
    Keeps the section informative without showing temperature-unavailable warnings.
    """
    parts: list[str] = []
    if isinstance(cpu_w, (int, float)):
        parts.append(f"CPU {cpu_w} W")
    if isinstance(gpu_w, (int, float)):
        parts.append(f"GPU {gpu_w} W")
    if isinstance(ane_w, (int, float)):
        parts.append(f"ANE {ane_w} W")
    if not parts:
        return ""
    return "Power: " + " | ".join(parts)
