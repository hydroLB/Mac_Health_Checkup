from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.security import SecurityPostureDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/security.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Security section from diagnostics.

    Inputs
    host: Section host.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host field and metrics.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails unexpectedly.

    Ties to other methods
    Used by the dashboard section handler registry.

    Why this exists
    Security posture flags are important health signals and should be visible without digging through settings.
    """
    try:
        data = SecurityPostureDiagnostics.fetch()
        rows: list[tuple[str, str, str]] = []

        filevault = data.get("filevault")
        fv_enabled = filevault.get("enabled") if isinstance(filevault, dict) else None
        fv_status = "unknown"
        if fv_enabled is True:
            fv_status = "ok"
        elif fv_enabled is False:
            fv_status = "warn"
        rows.append(("FileVault", "On" if fv_enabled else ("Off" if fv_enabled is False else "?"), fv_status))

        sip = data.get("sip")
        sip_enabled = sip.get("enabled") if isinstance(sip, dict) else None
        sip_status = "unknown"
        if sip_enabled is True:
            sip_status = "ok"
        elif sip_enabled is False:
            sip_status = "bad"
        rows.append(
            ("SIP", "Enabled" if sip_enabled else ("Disabled" if sip_enabled is False else "?"), sip_status)
        )

        gatekeeper = data.get("gatekeeper")
        gk_enabled = gatekeeper.get("enabled") if isinstance(gatekeeper, dict) else None
        gk_status = "unknown"
        if gk_enabled is True:
            gk_status = "ok"
        elif gk_enabled is False:
            gk_status = "warn"
        rows.append(
            (
                "Gatekeeper",
                "Enabled" if gk_enabled else ("Disabled" if gk_enabled is False else "?"),
                gk_status,
            )
        )

        firewall = data.get("firewall")
        fw_enabled = firewall.get("enabled") if isinstance(firewall, dict) else None
        fw_status = "unknown"
        if fw_enabled is True:
            fw_status = "ok"
        elif fw_enabled is False:
            fw_status = "warn"
        rows.append(("Firewall", "On" if fw_enabled else ("Off" if fw_enabled is False else "?"), fw_status))

        host.render_metrics_table("security", rows, columns=2)
        summary = " | ".join(f"{label}: {value}" for label, value, _status in rows)
        host.set_field("security", summary)
        data["ok"] = bool(data.get("ok"))
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Security section", exc)
        ) from exc
