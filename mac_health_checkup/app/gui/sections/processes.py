from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.diagnostics.processes import TopProcessesDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/processes.py"


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Processes section from diagnostics.

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
    Showing top CPU and memory offenders makes performance issues immediately actionable.
    """
    try:
        cfg = get_config().gui
        data = TopProcessesDiagnostics.fetch()
        top_cpu = data.get("top_cpu")
        top_mem = data.get("top_mem")
        rows: list[tuple[str, ...]] = []

        def append_rows(kind: str, items: object) -> None:
            """
            Summary
            Execute `append_rows` for its module-level responsibility.

            Inputs
            kind: `str` parameter from the function signature.
            items: `object` parameter from the function signature.

            Outputs
            None.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `mac_health_checkup/app/gui/sections/processes.py:append_rows` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `mac_health_checkup/app/gui/sections/processes.py`.

            Why this exists
            Keeps `append_rows` explicit, testable, and maintainable.
            """
            if not isinstance(items, list):
                return
            for item in items[: int(cfg.processes_max_rows)]:
                if not isinstance(item, dict):
                    continue
                pid = item.get("pid")
                cpu = item.get("cpu_percent")
                mem = item.get("mem_percent")
                cmd = item.get("command")
                pid_str = str(pid) if isinstance(pid, int) else "?"
                cpu_str = f"{float(cpu):.1f}" if isinstance(cpu, (int, float)) else "?"
                mem_str = f"{float(mem):.1f}" if isinstance(mem, (int, float)) else "?"
                cmd_str = str(cmd).strip() if isinstance(cmd, str) else "?"
                rows.append((kind, pid_str, cpu_str, mem_str, cmd_str))

        append_rows("CPU", top_cpu)
        append_rows("MEM", top_mem)

        headers = ("Type", "PID", "CPU%", "MEM%", "Command")
        if rows:
            host.set_field("processes", f"Top offenders (rows: {len(rows)})")
            host.render_table("processes", headers, rows)
            data["ok"] = True
            return data

        host.set_field("processes", "No process data")
        host.render_table("processes", headers, [])
        data["ok"] = False
        return data
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Processes section", exc)
        ) from exc
