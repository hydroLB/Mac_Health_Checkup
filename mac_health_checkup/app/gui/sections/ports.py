from __future__ import annotations

from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error, parse_usb_tree_items, safe_run
from mac_health_checkup.diagnostics.devices import PortsDiagnostics
from mac_health_checkup.diagnostics.display import DisplayDiagnostics

MODULE_PATH = "mac_health_checkup/app/gui/sections/ports.py"

_BILLBOARD_KEYWORDS = ("billboard",)


def _extract_external_display_names(raw: str) -> list[str]:
    """
    Summary
    Extract external display names from raw SPDisplaysDataType output.

    Inputs
    raw: system_profiler SPDisplaysDataType output string.

    Outputs
    List of external display names, in the order they appear.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by the Ports section to annotate USB-C ports that expose a display.

    Why this exists
    A USB billboard device is non-obvious; annotating it with the active external display makes the UI understandable.
    """
    try:
        if not raw:
            return []
        names: list[str] = []
        current_name: str | None = None
        current_connection: str | None = None
        current_is_builtin: bool | None = None

        def flush() -> None:
            """
            Summary
            Execute `flush` for its module-level responsibility.

            Inputs
            None.

            Outputs
            None.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `mac_health_checkup/app/gui/sections/ports.py:flush` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `mac_health_checkup/app/gui/sections/ports.py`.

            Why this exists
            Keeps `flush` explicit, testable, and maintainable.
            """
            nonlocal current_name, current_connection, current_is_builtin
            if not current_name:
                current_name = None
                current_connection = None
                current_is_builtin = None
                return
            if current_connection is None and current_is_builtin is None:
                current_name = None
                current_connection = None
                current_is_builtin = None
                return
            connection = (current_connection or "").lower()
            builtin = (
                bool(current_is_builtin) if current_is_builtin is not None else ("internal" in connection)
            )
            name = current_name.strip()
            if name and not builtin and name.lower() not in {"color lcd", "built-in retina lcd", "built-in"}:
                names.append(name)
            current_name = None
            current_connection = None
            current_is_builtin = None

        for line in raw.splitlines():
            if line.startswith("    ") and line.strip().endswith(":") and ":" not in line.strip()[:-1]:
                flush()
                current_name = line.strip()[:-1].strip()
                continue
            if current_name is None:
                continue
            stripped = line.strip()
            if stripped.lower().startswith("connection type:"):
                current_connection = stripped.split(":", 1)[1].strip()
                continue
            if stripped.lower().startswith("display type:"):
                value = stripped.split(":", 1)[1].strip().lower()
                if "built-in" in value or "internal" in value:
                    current_is_builtin = True
                continue
        flush()
        return names
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_extract_external_display_names", "Failed to parse display names", exc)
        ) from exc


def _compute_depths(items: list[dict[str, int | str]]) -> list[int]:
    """
    Summary
    Compute stable nesting depths from system_profiler indentation levels.

    Inputs
    items: Parsed USB tree items with an integer indent key.

    Outputs
    List of depths aligned to items.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when depth computation fails.

    Ties to other methods
    Used by `update_section` to convert raw USB tree indentation into a proper hierarchy.

    Why this exists
    system_profiler uses inconsistent indentation steps; relying on a fixed indent size flattens the tree.
    """
    try:
        stack: list[int] = []
        depths: list[int] = []
        for item in items:
            indent = int(item.get("indent", 0))
            while stack and indent < stack[-1]:
                stack.pop()
            if not stack or indent > stack[-1]:
                stack.append(indent)
            depths.append(max(0, len(stack) - 1))
        return depths
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_compute_depths", "Failed to compute USB depths", exc)
        ) from exc


def _annotate_usb_tree_labels(
    labels: list[str], depths: list[int], external_displays: list[str]
) -> list[str]:
    """
    Summary
    Annotate USB tree labels with user-meaningful hints (display alt-mode and port highlighting).

    Inputs
    labels: Raw USB tree labels.
    depths: Nesting depths aligned to labels.
    external_displays: Parsed display names.

    Outputs
    Updated labels aligned to inputs.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when annotation fails unexpectedly.

    Ties to other methods
    Used by `update_section` before rendering the tree.

    Why this exists
    Makes it clear which USB-C port is carrying an external display and avoids exposing confusing kernel device names.
    """
    try:
        if not labels:
            return labels
        updated = list(labels)
        display_suffix = f": {external_displays[0]}" if external_displays else ""

        root_indices = [idx for idx, depth in enumerate(depths) if depth == 0]
        root_indices.append(len(updated))
        for pos in range(len(root_indices) - 1):
            start = root_indices[pos]
            end = root_indices[pos + 1]
            segment = updated[start:end]
            has_billboard = any(
                any(keyword in value.lower() for keyword in _BILLBOARD_KEYWORDS) for value in segment
            )
            if has_billboard:
                root_label = updated[start].strip()
                if "display" not in root_label.lower():
                    updated[start] = f"{root_label} (Display{display_suffix})"

        for idx, label in enumerate(updated):
            if any(keyword in label.lower() for keyword in _BILLBOARD_KEYWORDS):
                updated[idx] = f"Display Alt Mode{display_suffix}"
        return updated
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_annotate_usb_tree_labels", "Failed to annotate USB labels", exc)
        ) from exc


def update_section(host: SectionHost) -> JsonDict:
    """
    Summary
    Update the Ports section from diagnostics.

    Inputs
    host: SectionHost implementation.

    Outputs
    Diagnostics dict for the section.

    Side effects
    Updates host fields and table output.

    Error handling
    Raises `RuntimeError` with module and method context when section rendering fails.

    Ties to other methods
    Used by the dashboard section handler.

    Why this exists
    Keeps ports rendering logic isolated.
    """
    try:
        data = PortsDiagnostics.fetch()
        display_payload = DisplayDiagnostics.fetch()
        raw_display = display_payload.get("raw") if isinstance(display_payload, dict) else ""
        external_displays = _extract_external_display_names(
            raw_display if isinstance(raw_display, str) else ""
        )
        out, _err = safe_run(
            ["system_profiler", "SPUSBDataType"], context="usb_tree_full", allow_sudo=False, timeout=8
        )
        items = parse_usb_tree_items(out or "") if out else []
        rows: list[tuple[str, ...]] = []
        depths = _compute_depths(items)
        labels = [str(item.get("label", "")).strip() for item in items]
        labels = _annotate_usb_tree_labels(labels, depths, external_displays)
        root_counts: dict[str, int] = {}
        for idx, item in enumerate(items):
            label = labels[idx] if idx < len(labels) else str(item.get("label", "")).strip()
            if not label:
                continue
            depth = depths[idx] if idx < len(depths) else 0
            if depth == 0:
                count = root_counts.get(label, 0) + 1
                root_counts[label] = count
                if count > 1:
                    label = f"{label} ({count})"
            prefix = " " * (depth * 2)
            rows.append((f"{prefix}{label}",))
        if rows:
            host.set_field("ports", f"{len(rows)} nodes")
            host.render_table("ports", ("USB Tree",), rows)
        else:
            devices = data.get("devices")
            text = ", ".join(devices) if isinstance(devices, list) else "None"
            host.set_field("ports", text)
            host.render_table("ports", ("USB Tree",), [])
        return {"ports": data, "usb_tree": items, "external_displays": external_displays}
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_section", "Failed to update Ports section", exc)
        ) from exc
