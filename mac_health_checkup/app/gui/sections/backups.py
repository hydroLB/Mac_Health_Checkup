from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.backups import TimeMachineDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/backups.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Backups section (Time Machine recency) from diagnostics.

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
    Backup recency is one of the most practical health signals. Surfacing it makes the tool more useful day-to-day.
    """
    try:
        thresholds = get_config().thresholds
        data = TimeMachineDiagnostics.fetch()

        age = data.get("latest_backup_age_days")
        age_val = float(age) if isinstance(age, (int, float)) else None
        running = data.get("running")

        rows: list[tuple[str, str, str]] = []
        status = "unknown"
        if age_val is not None:
            status = "ok"
            if age_val >= float(thresholds.backup_bad_days):
                status = "bad"
            elif age_val >= float(thresholds.backup_warn_days):
                status = "warn"
            rows.append(("Latest backup", f"{age_val:.1f} days ago", status))
        else:
            rows.append(("Latest backup", "?", "unknown"))
        if isinstance(running, bool):
            rows.append(("Running", "Yes" if running else "No", "info"))

        host.render_metrics_table("backups", rows, columns=2)
        if age_val is not None:
            host.set_field("backups", f"Latest backup: {age_val:.1f} days ago")
        else:
            guidance = data.get("guidance")
            host.set_field(
                "backups", str(guidance).strip() if isinstance(guidance, str) else "No backups detected"
            )
        data["ok"] = bool(data.get("ok"))
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Backups section", exc)
        ) from exc
