from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.diagnostics.startup import StartupItemsDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/startup.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Startup section from diagnostics.

    Inputs
    host: Section host.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host field and table.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails unexpectedly.

    Ties to other methods
    Used by the dashboard section handler registry.

    Why this exists
    Startup items explain many background behaviors. Listing launch agents and daemons is a high-value, read-only signal.
    """
    try:
        cfg = get_config().gui
        data = StartupItemsDiagnostics.fetch()
        rows: list[tuple[str, ...]] = []

        def add(scope: str, items: object) -> None:
            if not isinstance(items, list):
                return
            for label in items:
                text = str(label).strip()
                if not text:
                    continue
                rows.append((scope, text))

        add("User Agents", data.get("user_agents"))
        add("System Agents", data.get("system_agents"))
        add("System Daemons", data.get("system_daemons"))

        max_rows = int(cfg.startup_max_rows)
        headers = ("Scope", "Label")
        if rows:
            shown = rows[:max_rows]
            host.set_field("startup", f"{len(rows)} items (showing {len(shown)})")
            host.render_table("startup", headers, shown)
            data["ok"] = True
            return data

        host.set_field("startup", "No launch items detected")
        host.render_table("startup", headers, [])
        data["ok"] = False
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Startup section", exc)
        ) from exc
