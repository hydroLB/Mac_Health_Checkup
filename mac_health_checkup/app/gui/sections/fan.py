from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.fan import FanDiagnostics
from mac_health_checkup.diagnostics.thermals import ThermalSensorsDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/fan.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Purpose: Update the Fan section fields from diagnostics.
    Ties: Used by dashboard section handler.
    Inputs: host implements SectionHost.
    Outputs: Diagnostics dict for the section.
    Side effects: Updates host metrics table.
    Why: Keeps fan rendering logic isolated.
    """
    try:
        thermals = ThermalSensorsDiagnostics.fetch()
        rows: list[tuple[str, str, str]] = []
        merged: dict[str, int] = {}
        sources: list[str] = []

        fans_from_thermals = thermals.get("fans")
        if isinstance(fans_from_thermals, list) and fans_from_thermals:
            sources.append(str(thermals.get("source") or "thermals"))
            for item in fans_from_thermals:
                if not isinstance(item, dict):
                    continue
                label = str(item.get("label", "Fan")).strip()
                rpm = item.get("rpm")
                if label and isinstance(rpm, int):
                    merged.setdefault(label, rpm)

        data = FanDiagnostics.fetch()
        fans_from_diag = data.get("fans")
        if isinstance(fans_from_diag, list) and fans_from_diag:
            sources.append("fallback")
            for fan in fans_from_diag:
                if not isinstance(fan, dict):
                    continue
                name = str(fan.get("name", "Fan")).strip()
                rpm = fan.get("rpm")
                if name and isinstance(rpm, int):
                    merged.setdefault(name, rpm)

        for name in sorted(merged.keys(), key=lambda v: v.lower()):
            rows.append((name, f"{merged[name]} RPM", "info"))
        host.render_metrics_table("fan", rows, columns=2)
        if rows:
            host.set_field("fan", " | ".join(f"{label}: {value}" for label, value, _ in rows))
            return {
                "fans": [{"label": name, "rpm": rpm} for name, rpm in merged.items()],
                "source": "+".join([s for s in sources if s]) or "unknown",
                "ok": True,
            }
        guidance = thermals.get("guidance")
        guidance_text = str(guidance).strip() if isinstance(guidance, str) else ""
        host.set_field("fan", guidance_text or "Fan speeds unavailable")
        data["ok"] = False
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Fan section", exc)
        ) from exc
