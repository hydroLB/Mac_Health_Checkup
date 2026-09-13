from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Protocol, Sequence, cast

from mac_health_checkup.app.gui.dashboard import render_support
from mac_health_checkup.app.gui.dashboard.ui_helpers import (
    _SectionWidgets,
    _segment_at_char,
    _UiPalette,
    _UiTokens,
)
from mac_health_checkup.app.gui.sections.types import Widget
from mac_health_checkup.app.gui.widgets.tooltip import TooltipManager
from mac_health_checkup.app.help_text import metric as metric_help_text
from mac_health_checkup.app.help_text import section as section_help_text
from mac_health_checkup.app.help_text import table_header as table_header_help_text
from mac_health_checkup.core.config import Config
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/render_mixin.py"


class _SectionFeedbackFn(Protocol):
    def __call__(self, key: str, message: str, *, level: str) -> None:
        """
        Summary
        Invoke section feedback updates on a dashboard host.

        Inputs
        key: Section key.
        message: Feedback text.
        level: Feedback severity level.

        Outputs
        None.

        Side effects
        Updates UI feedback state on the host.

        Error handling
        Implementations raise contextual host-specific runtime errors when updates fail.

        Ties to other methods
        Used by table and metrics rendering paths.

        Why this exists
        Provides a typed callable contract for cross-mixin feedback updates.
        """
        ...


class _CardStateHandlerFn(Protocol):
    def __call__(self, *, key: str, mode: str) -> Callable[[tk.Event[tk.Misc]], None]:
        """
        Summary
        Build a Tk event handler that updates card border state.

        Inputs
        key: Section key.
        mode: Border interaction mode.

        Outputs
        Callable accepting a Tk event.

        Side effects
        Returned callback updates card border visuals.

        Error handling
        Implementations suppress per-event failures to keep UI input resilient.

        Ties to other methods
        Used by text widgets and card affordance bindings.

        Why this exists
        Provides a typed cross-mixin contract for focus and hover border behavior.
        """
        ...


class _EffectiveTableHeightFn(Protocol):
    def __call__(self, *, key: str, base_height: int) -> int:
        """
        Summary
        Compute final table height from a section key and base row budget.

        Inputs
        key: Section key.
        base_height: Initial table row count before viewport adjustments.

        Outputs
        Final table row count.

        Side effects
        None.

        Error handling
        Implementations return safe fallbacks when host state is incomplete.

        Ties to other methods
        Used by `_create_text_widget` and layout sizing paths.

        Why this exists
        Captures the keyword-only signature needed for strict mypy checks.
        """
        ...


class _DashboardRenderMixin:
    _cfg: Config
    _sections: dict[str, _SectionWidgets]
    _tooltips: TooltipManager
    _table_headers: dict[int, tuple[str, ...]]
    _ui_tokens: _UiTokens
    _ui_palette: _UiPalette
    _machine_hint: str
    _table_base_heights: dict[str, int]
    _set_card_border: Callable[[str, str], None]
    _set_section_feedback: _SectionFeedbackFn
    _card_state_handler: _CardStateHandlerFn
    _color: Callable[[str], str]
    _effective_table_height: _EffectiveTableHeightFn

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
            default_fg = self._color("text.primary")
            section.field.configure(text=text, fg=fg or default_fg)
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
            widget = section.metrics or self._create_text_widget(key, section, kind="metrics")
            section.metrics = widget
            self._configure_text_tags(widget)
            if created:
                self._tooltips.set_dynamic(
                    widget,
                    lambda event: self._metrics_tooltip_for_event(key=key, widget=widget, event=event),
                )
            self._set_card_border(key, "normal")
            plan = render_support.plan_metrics_render(
                rows=tuple(rows),
                empty_metrics_message=self._ui_tokens.empty_metrics_message,
                status_to_tag_fn=self._status_to_tag,
            )
            self._apply_text_render_plan(key=key, widget=widget, plan=plan)
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
            widget = section.table or self._create_text_widget(key, section, kind="table")
            section.table = widget
            self._configure_text_tags(widget)
            self._table_headers[id(widget)] = headers
            if created:
                self._tooltips.set_dynamic(
                    widget,
                    lambda event: self._table_tooltip_for_event(key=key, widget=widget, event=event),
                )
            self._set_card_border(key, "normal")
            plan = render_support.plan_table_render(
                headers=headers,
                rows=tuple(rows),
                empty_table_message=self._ui_tokens.empty_table_message,
                separator_min_chars=self._ui_tokens.table_separator_min_chars,
                separator_max_chars=self._ui_tokens.table_separator_max_chars,
            )
            self._apply_text_render_plan(key=key, widget=widget, plan=plan)
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
        except (
            tk.TclError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ):
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
        except (
            tk.TclError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ):
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
            cast(tk.Misc, self).after(0, fn)
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

    def _create_text_widget(self, key: str, section: _SectionWidgets, *, kind: str) -> tk.Text:
        """
        Summary
        Create a read-only Text widget with vertical and horizontal scrollbars for a section.

        Inputs
        key: Section key, used to apply per-section height tuning.
        section: Section widget container that owns the widget.
        kind: View type, either table or metrics.

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
            table_base_heights = self.__dict__.setdefault("_table_base_heights", {})
            if not isinstance(table_base_heights, dict):
                table_base_heights = {}
                self.__dict__["_table_base_heights"] = table_base_heights
            return render_support.create_text_widget(
                key=key,
                section=section,
                kind=kind,
                cfg=self._cfg,
                ui_tokens=cast(Optional[_UiTokens], self.__dict__.get("_ui_tokens")),
                table_base_heights=table_base_heights,
                color_fn=self._color,
                effective_table_height_fn=self._effective_table_height,
                card_state_handler_fn=self._card_state_handler,
                style_scrollbar_fn=self._style_scrollbar,
                set_horizontal_scrollbar_visibility_fn=self._set_horizontal_scrollbar_visibility,
            )
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._create_text_widget", "Failed to create text widget", exc
                )
            ) from exc

    def _style_scrollbar(self, scrollbar: tk.Scrollbar) -> None:
        """
        Summary
        Apply centralized low-contrast scrollbar styling.

        Inputs
        scrollbar: Target Tk scrollbar.

        Outputs
        None.

        Side effects
        Updates scrollbar visual options.

        Error handling
        Never raises for unsupported platform-specific options.

        Ties to other methods
        Used by `_create_text_widget`.

        Why this exists
        Softer scrollbars reduce visual clutter while preserving affordance.
        """
        render_support.style_scrollbar(scrollbar, color_fn=self._color)

    def _set_horizontal_scrollbar_visibility(self, scrollbar: tk.Scrollbar, *, visible: bool) -> None:
        """
        Summary
        Toggle horizontal scrollbar packing based on overflow state.

        Inputs
        scrollbar: Horizontal scrollbar.
        visible: True when overflow exists.

        Outputs
        None.

        Side effects
        Packs or unpacks the scrollbar widget.

        Error handling
        Never raises for missing geometry manager methods on stubs.

        Ties to other methods
        Used by `_create_text_widget`.

        Why this exists
        Always-visible horizontal bars add noise when no horizontal scrolling is possible.
        """
        render_support.set_horizontal_scrollbar_visibility(scrollbar, visible=visible)

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
            render_support.configure_text_tags(widget, color_fn=self._color)
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
            return render_support.status_to_tag(status, default="unknown")
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._status_to_tag", "Failed to map status tag", exc)
            ) from exc

    def _apply_text_render_plan(self, *, key: str, widget: tk.Text, plan: render_support.RenderPlan) -> None:
        """
        Summary
        Apply one prepared text render plan to a section detail widget.

        Inputs
        key: Section key for feedback updates.
        widget: Target text widget.
        plan: Prepared render plan containing inserts and feedback metadata.

        Outputs
        None.

        Side effects
        Replaces widget text content and updates section feedback.

        Error handling
        Raises `RuntimeError` with module and method context when widget updates fail.

        Ties to other methods
        Used by `render_metrics_table` and `render_table`.

        Why this exists
        The two text renderers share the same mutation sequence; centralizing it keeps the mixin readable without moving coordinator logic out of the file.
        """
        try:
            widget.configure(state="normal")
            widget.delete("1.0", tk.END)
            for insert in plan.inserts:
                widget.insert(tk.END, insert.text, insert.tags)
            self._set_section_feedback(key, plan.feedback_message, level=plan.feedback_level)
            widget.configure(state="disabled")
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "DashboardApp._apply_text_render_plan",
                    "Failed to apply text render plan",
                    exc,
                )
            ) from exc

    def _clear_text_widget(self, widget: tk.Text, *, message: str, level: str = "info") -> None:
        """
        Summary
        Clear a read-only text widget and optionally render a fallback message.

        Inputs
        widget: Target text widget.
        message: Optional replacement line when no data should remain.
        level: Status level used to pick a text tag.

        Outputs
        None.

        Side effects
        Mutates widget text content.

        Error handling
        Raises `RuntimeError` with module and method context when clearing fails.

        Ties to other methods
        Used by `_clear_section_data_views` and refresh error handling.

        Why this exists
        Prevents stale rows from lingering after section failures.
        """
        try:
            render_support.clear_text_widget(widget, message=message, level=level)
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._clear_text_widget", "Failed to clear text widget", exc
                )
            ) from exc

    def _clear_section_data_views(self, key: str, *, message: str = "", level: str = "info") -> None:
        """
        Summary
        Clear table and metrics views for a section.

        Inputs
        key: Section key.
        message: Optional fallback message to show in cleared views.
        level: Status level used to style fallback text.

        Outputs
        None.

        Side effects
        Updates section text widgets.

        Error handling
        Raises `RuntimeError` with module and method context when clearing fails.

        Ties to other methods
        Used by refresh failure handling to avoid stale detail data.

        Why this exists
        A failed refresh should not keep displaying old details as if they are current.
        """
        try:
            section = self._sections.get(key)
            if section is None:
                return
            if section.table is not None:
                self._clear_text_widget(section.table, message=message, level=level)
            if section.metrics is not None:
                self._clear_text_widget(section.metrics, message=message, level=level)
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "DashboardApp._clear_section_data_views",
                    "Failed to clear section views",
                    exc,
                )
            ) from exc
