from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Sequence

from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.app.gui.dashboard.queueing import SectionQueue
from mac_health_checkup.app.gui.dashboard.sections import SECTION_HANDLERS, run_section
from mac_health_checkup.app.gui.sections.types import SectionHost, Widget
from mac_health_checkup.app.gui.widgets.scroll_container import ScrollContainer
from mac_health_checkup.app.gui.widgets.tooltip import TooltipManager, TooltipTheme
from mac_health_checkup.app.help_text import (
    metric as metric_help_text,
)
from mac_health_checkup.app.help_text import (
    section as section_help_text,
)
from mac_health_checkup.app.help_text import (
    table_header as table_header_help_text,
)
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/gui/app.py"


def _segment_at_char(line: str, char_index: int) -> str:
    """
    Summary
    Return the pipe-delimited segment under a character index.

    Inputs
    line: Full line of text, typically formatted as `A | B | C`.
    char_index: Zero-based character index within the line.

    Outputs
    Segment text under the index, or an empty string when no segment matches.

    Side effects
    None.

    Error handling
    Returns an empty string on invalid inputs.

    Ties to other methods
    Used by tooltip providers to map cursor position to a header or cell value.

    Why this exists
    Tk Text widgets provide a character offset; tooltips need a deterministic way to map that to a column.
    """
    try:
        text = line or ""
        idx = int(char_index)
        if idx < 0:
            idx = 0
        parts = text.split(" | ")
        cursor = 0
        for i, part in enumerate(parts):
            start = cursor
            end = start + len(part)
            if start <= idx <= end:
                return part
            cursor = end
            if i < len(parts) - 1:
                cursor += 3  # len(" | ")
        return ""
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_segment_at_char", "Failed to map column segment", exc)
        ) from exc


@dataclass
class _SectionWidgets:
    """
    Summary
    Hold widget references for a single dashboard section.

    Inputs
    frame: Content container for the section.
    title: Section title label.
    subtitle: Section subtitle label.
    field: Primary field label for summary text.
    table: Optional Text widget used for table output.
    metrics: Optional Text widget used for metric output.

    Outputs
    Structured container for section widgets.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `DashboardApp` render methods to update specific section UI elements.

    Why this exists
    Keeps section widget access consistent and typed, minimizing UI coupling in section renderers.
    """

    frame: tk.Frame
    title: tk.Label
    subtitle: tk.Label
    field: tk.Label
    table: Optional[tk.Text] = None
    metrics: Optional[tk.Text] = None


class DashboardApp(tk.Tk, SectionHost):
    """
    Summary
    Render a macOS diagnostics dashboard using Tkinter.

    Inputs
    None. Reads configuration from `get_config()` for layout, styling, and refresh timing.

    Outputs
    None. This class owns the window lifecycle.

    Side effects
    Creates a Tk root window, installs shutdown handlers, and schedules periodic refresh work.

    Error handling
    Raises `RuntimeError` with module and method context when Tk initialization or UI construction fails.

    Ties to other methods
    Implements `SectionHost` so section renderers can update the UI via `set_field`, `render_table`,
    and `render_metrics_table`.

    Why this exists
    Keeps diagnostics rendering approachable while providing enough structure for deterministic refresh behavior.
    """

    def __init__(self) -> None:
        """
        Summary
        Initialize the Tk window, layout containers, and section widgets.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates the root window, installs shutdown handlers, builds the header and scroll view, and registers
        the close handler.

        Error handling
        Raises `RuntimeError` with actionable context when initialization fails.

        Ties to other methods
        Calls `_build_layout` and `_build_sections` to construct the UI and stores section widget references.

        Why this exists
        Establishes a consistent UI structure that section renderers can update without direct Tk knowledge.
        """
        try:
            super().__init__()
            self._cfg = get_config()
            self._shutdown = ShutdownManager()
            self._shutdown.install_handlers()
            self._sections: dict[str, _SectionWidgets] = {}
            self._machine_hint: str = "mac"
            self._queue = SectionQueue()
            self._wraplength_px: int | None = None
            self._status_var = tk.StringVar(value="")
            self._scroll: ScrollContainer | None = None
            self._tooltips = TooltipManager(
                root=self,
                theme=TooltipTheme(
                    bg=self._cfg.fonts.tooltip_bg,
                    fg=self._cfg.fonts.tooltip_fg,
                    font_family=self._cfg.fonts.family_default,
                    font_size=self._cfg.fonts.size_tooltip,
                ),
                delay_ms=350,
            )
            self._table_headers: dict[int, tuple[str, ...]] = {}

            self.title(self._cfg.ui.window_title)
            self.configure(bg=self._cfg.colors.bg)
            self.geometry(self._cfg.ui.window_size)
            self.maxsize(self._cfg.gui.window_max_width, self._cfg.gui.window_max_height)

            self._build_layout()
            self.protocol("WM_DELETE_WINDOW", self._on_close)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp.__init__", "Failed to initialize UI", exc)
            ) from exc

    def start(self) -> None:
        """
        Summary
        Start the refresh loop and enter the Tk main loop.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Schedules periodic refresh work and blocks in the Tk event loop until the window closes.

        Error handling
        Raises `RuntimeError` with module and method context if the main loop fails to start.

        Ties to other methods
        Calls `_schedule_refresh` which calls `_refresh` for periodic section updates.

        Why this exists
        Provides a single explicit entrypoint for the GUI lifecycle used by the application entrypoint.
        """
        try:
            self._schedule_refresh()
            self.mainloop()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp.start", "Failed to start UI", exc)
            ) from exc

    def get_widget(self, key: str) -> Optional[Widget]:
        """
        Summary
        Return a widget for a section if one is available.

        Inputs
        key: Section key.

        Outputs
        The primary field widget for the section or `None` when the section is not present.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context if internal state access fails.

        Ties to other methods
        Used by section renderers that optionally render richer layouts.

        Why this exists
        Allows section code to stay decoupled from the concrete UI while still supporting optional widgets.
        """
        try:
            section = self._sections.get(key)
            return section.field if section else None
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp.get_widget", "Failed to get widget", exc)
            ) from exc

    def set_field(self, key: str, text: str, fg: Optional[str] = None, tooltip: Optional[str] = None) -> None:
        """
        Summary
        Update the primary field label for a section.

        Inputs
        key: Section key.
        text: Field text to display.
        fg: Optional foreground color override.
        tooltip: Optional tooltip text (currently unused by Tk widgets).

        Outputs
        None.

        Side effects
        Updates a Tk label in the UI.

        Error handling
        Raises `RuntimeError` with module and method context if label updates fail.

        Ties to other methods
        Called by section renderers during `_refresh` updates.

        Why this exists
        Provides a consistent, minimal API for section renderers to publish a summary without UI coupling.
        """
        try:
            section = self._sections.get(key)
            if not section:
                return
            section.field.configure(text=text, fg=fg or self._cfg.colors.field)
            self._tooltips.set_static(section.field, (tooltip or section_help_text(key)))
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp.set_field", "Failed to set field", exc)
            ) from exc

    def render_metrics_table(
        self, key: str, rows: Sequence[tuple[str, str, str]], *, columns: int = 2
    ) -> None:
        """
        Summary
        Render a compact metrics list into a section.

        Inputs
        key: Section key.
        rows: List of (label, value, status) tuples.
        columns: Layout hint from section renderers (currently informational only).

        Outputs
        None.

        Side effects
        Creates or updates a read-only Tk Text widget.

        Error handling
        Raises `RuntimeError` with module and method context if widget updates fail.

        Ties to other methods
        Uses `_create_text_widget` and `_configure_text_tags` to keep styling consistent.

        Why this exists
        Provides a simple, readable visualization for metrics without requiring per-section custom widgets.
        """
        try:
            _ = columns
            section = self._sections.get(key)
            if not section:
                return
            created = section.metrics is None
            widget = section.metrics or self._create_text_widget(key, section)
            section.metrics = widget
            self._configure_text_tags(widget)
            if created:
                self._tooltips.set_dynamic(
                    widget,
                    lambda event: self._metrics_tooltip_for_event(key=key, widget=widget, event=event),
                )
            widget.configure(state="normal")
            widget.delete("1.0", tk.END)
            for label, value, status in rows:
                tag = self._status_to_tag(status)
                widget.insert(tk.END, f"{label}: {value} ", ())
                widget.insert(tk.END, f"[{status}]\n", (tag,))
            widget.configure(state="disabled")
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp.render_metrics_table", "Failed to render metrics", exc
                )
            ) from exc

    def render_table(
        self,
        key: str,
        headers: tuple[str, ...],
        rows: Sequence[tuple[str, ...]],
        max_col_chars: tuple[int | None, ...] | None = None,
    ) -> None:
        """
        Summary
        Render a table into a section.

        Inputs
        key: Section key.
        headers: Column headers.
        rows: Table rows as tuples matching the header shape.
        max_col_chars: Optional column sizing hint (currently unused by the Tk Text renderer).

        Outputs
        None.

        Side effects
        Creates or updates a read-only Tk Text widget.

        Error handling
        Raises `RuntimeError` with module and method context if widget updates fail.

        Ties to other methods
        Uses `_create_text_widget` and `_configure_text_tags` to keep styling consistent.

        Why this exists
        Provides a deterministic, dependency-free table view for sections without requiring external widgets.
        """
        try:
            _ = max_col_chars
            section = self._sections.get(key)
            if not section:
                return
            created = section.table is None
            widget = section.table or self._create_text_widget(key, section)
            section.table = widget
            self._configure_text_tags(widget)
            self._table_headers[id(widget)] = headers
            if created:
                self._tooltips.set_dynamic(
                    widget,
                    lambda event: self._table_tooltip_for_event(key=key, widget=widget, event=event),
                )
            widget.configure(state="normal")
            widget.delete("1.0", tk.END)
            widget.insert(tk.END, " | ".join(headers) + "\n", ("header",))
            widget.insert(tk.END, "-" * 60 + "\n", ("separator",))
            for row in rows:
                widget.insert(tk.END, " | ".join(row) + "\n")
            widget.configure(state="disabled")
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp.render_table", "Failed to render table", exc)
            ) from exc

    def _metrics_tooltip_for_event(
        self, *, key: str, widget: tk.Text, event: tk.Event[tk.Misc]
    ) -> str | None:
        """
        Summary
        Compute tooltip text for a metrics Text widget based on cursor location.

        Inputs
        key: Section key for help text mapping.
        widget: Text widget containing metrics.
        event: Tk event containing cursor coordinates.

        Outputs
        Tooltip string, or None to hide the tooltip.

        Side effects
        None.

        Error handling
        Returns None on parsing failures to keep the UI resilient.

        Ties to other methods
        Used by `TooltipManager` dynamic providers for metrics tables.

        Why this exists
        Metrics tables contain multiple rows; tooltips should explain the specific row being hovered.
        """
        try:
            idx = widget.index(f"@{event.x},{event.y}")
            line_str, col_str = idx.split(".", 1)
            _ = col_str
            line_text = widget.get(f"{line_str}.0", f"{line_str}.end").strip()
            if not line_text or ":" not in line_text:
                return section_help_text(key)
            label = line_text.split(":", 1)[0].strip()
            if not label:
                return section_help_text(key)
            base = metric_help_text(key, label)
            value_part = line_text.split(":", 1)[1].strip()
            if value_part:
                return f"{base}\n\nCurrent value: {value_part}"
            return base
        except Exception:
            return None

    def _table_tooltip_for_event(self, *, key: str, widget: tk.Text, event: tk.Event[tk.Misc]) -> str | None:
        """
        Summary
        Compute tooltip text for a table Text widget based on cursor location.

        Inputs
        key: Section key for help text mapping.
        widget: Text widget containing a table.
        event: Tk event containing cursor coordinates.

        Outputs
        Tooltip string, or None to hide the tooltip.

        Side effects
        None.

        Error handling
        Returns None on parsing failures to keep the UI resilient.

        Ties to other methods
        Used by `TooltipManager` dynamic providers for section tables.

        Why this exists
        Table widgets contain header, separators, and many cells; tooltips should explain the hovered column.
        """
        try:
            idx = widget.index(f"@{event.x},{event.y}")
            line_str, col_str = idx.split(".", 1)
            line = int(line_str)
            col = int(col_str)
            if line <= 0:
                return None
            if line == 2:
                return section_help_text(key)

            header_line = widget.get("1.0", "1.end")
            header = _segment_at_char(header_line, col)
            if not header:
                return section_help_text(key)
            base = table_header_help_text(key, header)
            if line == 1:
                return base

            line_text = widget.get(f"{line_str}.0", f"{line_str}.end")
            value = _segment_at_char(line_text, col)
            if value:
                return f"{base}\n\nCurrent value: {value.strip()}"
            return base
        except Exception:
            return None

    def section_container(self, key: str) -> Optional[Widget]:
        """
        Summary
        Return the section container frame used for custom layouts.

        Inputs
        key: Section key.

        Outputs
        The section content frame or `None` when the section is not present.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context if internal state access fails.

        Ties to other methods
        Sections can use this to render custom widgets instead of `set_field` or `render_table`.

        Why this exists
        Keeps the default UI simple while leaving a safe extension point for richer section-specific UI.
        """
        try:
            section = self._sections.get(key)
            return section.frame if section else None
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp.section_container", "Failed to get container", exc)
            ) from exc

    def run_on_ui(self, fn: Callable[[], None]) -> None:
        """
        Summary
        Schedule a callback to run on the Tk event loop.

        Inputs
        fn: Callback to execute.

        Outputs
        None.

        Side effects
        Schedules a Tk `after(0, ...)` callback.

        Error handling
        Raises `RuntimeError` with module and method context if scheduling fails.

        Ties to other methods
        Used by sections that require UI-thread execution for Tk safety.

        Why this exists
        Ensures UI updates remain thread safe even if sections fetch data asynchronously in the future.
        """
        try:
            self.after(0, fn)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp.run_on_ui", "Failed to schedule callback", exc)
            ) from exc

    def set_machine_hint(self, descriptor: str) -> None:
        """
        Summary
        Store a machine hint derived from the model description.

        Inputs
        descriptor: Model description string.

        Outputs
        None.

        Side effects
        Updates internal state used by sections.

        Error handling
        Raises `RuntimeError` with module and method context if normalization fails.

        Ties to other methods
        Read by `machine_hint` and used by section renderers for small presentation tweaks.

        Why this exists
        Allows sections to tailor messaging for common Mac families without hard-coding per-section logic.
        """
        try:
            desc = (descriptor or "").lower()
            if "pro" in desc:
                self._machine_hint = "pro"
            elif "air" in desc:
                self._machine_hint = "air"
            else:
                self._machine_hint = "mac"
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp.set_machine_hint", "Failed to set machine hint", exc)
            ) from exc

    def machine_hint(self) -> str:
        """
        Summary
        Return the current machine hint.

        Inputs
        None.

        Outputs
        A normalized machine hint string.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context if state access fails.

        Ties to other methods
        Read by section renderers for small presentation adjustments.

        Why this exists
        Provides a single shared hint so sections can remain consistent.
        """
        try:
            return self._machine_hint
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp.machine_hint", "Failed to get machine hint", exc)
            ) from exc

    def _build_layout(self) -> None:
        """
        Summary
        Build the top-level layout including header and scroll view.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates header widgets and a scroll container and binds resize handling.

        Error handling
        Raises `RuntimeError` with module and method context when layout construction fails.

        Ties to other methods
        Calls `_build_sections` to create section cards inside the scroll container.

        Why this exists
        Keeps the UI structure closer to a native app by using a single scroll view and a stable header.
        """
        try:
            root = tk.Frame(self, bg=self._cfg.colors.bg)
            root.pack(fill="both", expand=True)

            header = tk.Frame(root, bg=self._cfg.colors.bg)
            header.pack(fill="x", padx=max(8, self._cfg.gui.section_padx), pady=(10, 6))

            title = tk.Label(
                header,
                text=self._cfg.ui.window_title,
                bg=self._cfg.colors.bg,
                fg=self._cfg.colors.fg,
                font=(
                    self._cfg.fonts.family_default,
                    self._cfg.fonts.size_banner,
                    self._cfg.fonts.weight_bold,
                ),
            )
            title.pack(anchor="w")
            self._tooltips.set_static(
                title,
                "Mac Health Checkup dashboard. Hover over section titles, fields, metrics, and tables for details.",
            )

            status = tk.Label(
                header,
                textvariable=self._status_var,
                bg=self._cfg.colors.bg,
                fg=self._cfg.colors.label,
                font=(
                    self._cfg.fonts.family_default,
                    self._cfg.fonts.size_tooltip,
                    self._cfg.fonts.weight_normal,
                ),
            )
            status.pack(anchor="w")
            self._tooltips.set_static(
                status,
                "Refresh status and diagnostic messages. Values update on a timer and may be cached briefly.",
            )

            separator = tk.Frame(root, bg=self._cfg.gui.card_border, height=1)
            separator.pack(fill="x", padx=max(8, self._cfg.gui.section_padx), pady=(0, 8))

            self._scroll = ScrollContainer(
                root, bg=self._cfg.colors.bg, scroll_divisor=self._cfg.gui.drag_scroll_divisor
            )
            self._scroll.pack(fill="both", expand=True)

            self.bind("<Configure>", self._on_window_configure)
            self._build_sections(self._scroll.content)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._build_layout", "Failed to build layout", exc)
            ) from exc

    def _build_sections(self, parent: tk.Frame) -> None:
        """
        Summary
        Build section cards based on config-defined rows.

        Inputs
        parent: Parent frame that will receive section card frames.

        Outputs
        None.

        Side effects
        Creates widgets and stores them in `self._sections`.

        Error handling
        Raises `RuntimeError` with module and method context when widget construction fails.

        Ties to other methods
        Section widgets created here are updated by `set_field`, `render_table`, and `render_metrics_table`.

        Why this exists
        Keeps section layout driven by configuration while maintaining a consistent, native-feeling card structure.
        """
        try:
            for title, subtitle, key in self._cfg.gui.section_rows:
                card = tk.Frame(
                    parent,
                    bg=self._cfg.gui.card_bg,
                    highlightbackground=self._cfg.gui.card_border,
                    highlightthickness=1,
                )
                card.pack(fill="x", padx=max(8, self._cfg.gui.section_padx), pady=self._cfg.gui.section_pady)

                content = tk.Frame(card, bg=self._cfg.gui.card_bg)
                content.pack(fill="x", padx=12, pady=10)

                title_label = tk.Label(
                    content,
                    text=title,
                    bg=self._cfg.gui.card_bg,
                    fg=self._cfg.colors.section,
                    font=(
                        self._cfg.fonts.family_default,
                        self._cfg.fonts.size_section,
                        self._cfg.fonts.weight_bold,
                    ),
                )
                title_label.pack(anchor="w")
                self._tooltips.set_static(title_label, section_help_text(key))

                subtitle_label = tk.Label(
                    content,
                    text=subtitle,
                    bg=self._cfg.gui.card_bg,
                    fg=self._cfg.colors.label,
                    font=(
                        self._cfg.fonts.family_default,
                        self._cfg.fonts.size_field,
                        self._cfg.fonts.weight_normal,
                    ),
                )
                subtitle_label.pack(anchor="w", pady=(2, 6))
                self._tooltips.set_static(subtitle_label, section_help_text(key))

                field_label = tk.Label(
                    content,
                    text="",
                    bg=self._cfg.gui.card_bg,
                    fg=self._cfg.colors.field,
                    wraplength=self._cfg.gui.content_wrap,
                    font=(
                        self._cfg.fonts.family_default,
                        self._cfg.fonts.size_field,
                        self._cfg.fonts.weight_normal,
                    ),
                    justify="left",
                )
                field_label.pack(anchor="w", fill="x")
                self._tooltips.set_static(field_label, section_help_text(key))

                self._sections[key] = _SectionWidgets(
                    frame=content,
                    title=title_label,
                    subtitle=subtitle_label,
                    field=field_label,
                )
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._build_sections", "Failed to build sections", exc)
            ) from exc

    def _create_text_widget(self, key: str, section: _SectionWidgets) -> tk.Text:
        """
        Summary
        Create a read-only Text widget with a vertical scrollbar for a section.

        Inputs
        key: Section key, used to apply per-section height tuning.
        section: Section widget container that owns the widget.

        Outputs
        A `tk.Text` widget configured for read-only rendering.

        Side effects
        Adds new Tk widgets to the UI.

        Error handling
        Raises `RuntimeError` with module and method context when widget creation fails.

        Ties to other methods
        Called by `render_table` and `render_metrics_table` when a section needs a scrollable text area.

        Why this exists
        Keeps table and metric rendering consistent while supporting longer outputs with a native-feeling scrollbar.
        """
        try:
            height = int(self._cfg.gui.scrollable_rows.get(key, self._cfg.gui.table_max_visible_rows))
            if height <= 0:
                height = int(self._cfg.gui.table_max_visible_rows)

            container = tk.Frame(section.frame, bg=self._cfg.gui.card_bg)
            container.pack(fill="x", pady=(8, 0))

            scrollbar = tk.Scrollbar(container, orient="vertical")
            scrollbar.pack(side="right", fill="y")

            text_widget = tk.Text(
                container,
                height=height,
                bg=self._cfg.gui.card_bg,
                fg=self._cfg.colors.field,
                font=(self._cfg.fonts.family_mono, self._cfg.fonts.size_field),
                wrap="none",
                relief="flat",
                highlightthickness=0,
                borderwidth=0,
                padx=8,
                pady=6,
                yscrollcommand=scrollbar.set,
            )
            scrollbar.configure(command=text_widget.yview)
            text_widget.configure(state="disabled")
            text_widget.pack(side="left", fill="x", expand=True)
            return text_widget
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._create_text_widget", "Failed to create text widget", exc
                )
            ) from exc

    def _configure_text_tags(self, widget: tk.Text) -> None:
        """
        Summary
        Configure shared Text widget tags for table and metrics rendering.

        Inputs
        widget: Text widget to configure.

        Outputs
        None.

        Side effects
        Updates tag configuration on the widget.

        Error handling
        Raises `RuntimeError` with module and method context if tag configuration fails.

        Ties to other methods
        Used by `render_table` and `render_metrics_table` to style headers and statuses.

        Why this exists
        Centralizes styling so all sections read consistently and can be tuned via config colors.
        """
        try:
            widget.tag_configure("header", foreground=self._cfg.colors.label)
            widget.tag_configure("separator", foreground=self._cfg.gui.card_border)
            widget.tag_configure("ok", foreground=self._cfg.colors.ok)
            widget.tag_configure("warn", foreground=self._cfg.colors.warn)
            widget.tag_configure("bad", foreground=self._cfg.colors.bad)
            widget.tag_configure("unknown", foreground=self._cfg.colors.field)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._configure_text_tags", "Failed to configure text tags", exc
                )
            ) from exc

    def _status_to_tag(self, status: str) -> str:
        """
        Summary
        Map a status string to a Text tag name.

        Inputs
        status: Status label such as "ok", "warn", or "bad".

        Outputs
        A tag name that can be used with `tk.Text.insert`.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context if normalization fails.

        Ties to other methods
        Used by `render_metrics_table` to apply consistent status coloring.

        Why this exists
        Keeps status mapping centralized so sections can emit simple status strings without UI concerns.
        """
        try:
            normalized = (status or "").strip().lower()
            if normalized in {"ok", "good", "pass"}:
                return "ok"
            if normalized in {"warn", "warning"}:
                return "warn"
            if normalized in {"bad", "fail", "error"}:
                return "bad"
            return "unknown"
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._status_to_tag", "Failed to map status tag", exc)
            ) from exc

    def _on_window_configure(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Update wrap lengths when the window is resized.

        Inputs
        _event: Tk event (unused).

        Outputs
        None.

        Side effects
        Updates `wraplength` on section field labels.

        Error handling
        Raises `RuntimeError` with module and method context if widget updates fail.

        Ties to other methods
        Bound by `_build_layout` to keep text readable across different window sizes.

        Why this exists
        Mimics native adaptive layouts by preventing fixed wrap lengths from wasting space or truncating text.
        """
        try:
            width = int(self.winfo_width())
            outer_pad = max(8, self._cfg.gui.section_padx)
            wrap = max(260, min(self._cfg.gui.content_wrap, width - (outer_pad * 2) - 64))
            if self._wraplength_px == wrap:
                return
            self._wraplength_px = wrap
            for section in self._sections.values():
                section.field.configure(wraplength=wrap)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._on_window_configure", "Failed to update wrap length", exc
                )
            ) from exc

    def _schedule_refresh(self) -> None:
        """
        Summary
        Schedule the next refresh cycle and run an initial refresh.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Schedules `_refresh` via Tk `after` and triggers an immediate refresh.

        Error handling
        Never raises for section handler failures; updates the status line instead. Raises `RuntimeError` only
        when Tk scheduling primitives fail unexpectedly.

        Ties to other methods
        Calls `_refresh` which runs section handlers and updates the status line.

        Why this exists
        Keeps the dashboard up to date without user interaction while remaining bounded by config.
        """
        try:
            self._refresh()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._schedule_refresh", "Failed to schedule refresh", exc)
            ) from exc

    def _refresh(self) -> None:
        """
        Summary
        Refresh all sections using the current diagnostics.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Runs section handlers, updates UI widgets, and updates the header status timestamp.

        Error handling
        Captures per-section handler failures, renders a per-section error fallback, and keeps the refresh loop
        running. Does not raise for recoverable section failures.

        Ties to other methods
        Calls `run_section` for each key in `SECTION_HANDLERS`.

        Why this exists
        Centralizes refresh so UI updates remain predictable and bounded by the queueing logic.
        """
        failures = 0
        now = datetime.now().strftime("%H:%M:%S")
        try:
            for key in SECTION_HANDLERS:
                self._queue.enqueue(key)
            for key in self._queue.drain():
                try:
                    run_section(self, key)
                except Exception as exc:
                    failures += 1
                    try:
                        self.set_field(
                            key,
                            f"Error: {type(exc).__name__}",
                            fg=self._cfg.colors.bad,
                            tooltip=str(exc),
                        )
                    except Exception:
                        continue
            if failures:
                self._status_var.set(f"Last refreshed: {now} ({failures} section errors)")
            else:
                self._status_var.set(f"Last refreshed: {now}")
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            self._status_var.set(f"Refresh error at {now}: {type(exc).__name__}")
        finally:
            try:
                if not self._shutdown.shutdown_requested():
                    self.after(self._cfg.gui.auto_refresh_ms, self._refresh)
            except tk.TclError:
                return

    def _on_close(self) -> None:
        """
        Summary
        Handle window close events with cleanup.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Triggers shutdown and destroys the root window.

        Error handling
        Raises `RuntimeError` with module and method context if shutdown or destroy fails.

        Ties to other methods
        Registered by `__init__` via `WM_DELETE_WINDOW`.

        Why this exists
        Ensures shutdown paths run deterministically so background work and handlers do not leak.
        """
        try:
            self._shutdown.trigger_shutdown()
            self.destroy()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._on_close", "Failed to close UI", exc)
            ) from exc
