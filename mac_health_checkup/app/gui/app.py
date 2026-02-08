from __future__ import annotations

import time
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Literal, Optional, Sequence

from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.app.gui.dashboard.queueing import SectionQueue
from mac_health_checkup.app.gui.dashboard.sections import SECTION_HANDLERS, run_section
from mac_health_checkup.app.gui.sections.types import SectionHost, Widget
from mac_health_checkup.app.gui.widgets.controls import (
    ButtonTheme,
    InlineStatusBadge,
    InteractiveButton,
    StatusTheme,
)
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


@dataclass(frozen=True)
class _UiPalette:
    """
    Summary
    Hold resolved color roles used by dashboard components and interaction states.

    Inputs
    Colors from config and derived shades for hover and disabled interactions.

    Outputs
    Immutable palette container.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `_build_ui_palette` and consumed by layout, card, status, and action-control helpers.

    Why this exists
    A single palette object keeps restyling predictable and avoids scattered color constants.
    """

    page_bg: str
    card_bg: str
    card_border: str
    card_border_hover: str
    card_border_focus: str
    text_primary: str
    text_secondary: str
    text_muted: str
    status_info: str
    status_loading: str
    status_success: str
    status_warn: str
    status_error: str
    button_bg: str
    button_hover_bg: str
    button_active_bg: str
    button_disabled_bg: str
    button_disabled_fg: str
    button_border: str
    button_focus_border: str


@dataclass(frozen=True)
class _UiTokens:
    """
    Summary
    Hold shared layout and styling tokens for the dashboard shell.

    Inputs
    Spacing, sizing, and behavior constants derived from config.

    Outputs
    Immutable token container.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `DashboardApp` layout and rendering helpers.

    Why this exists
    Keeps visual decisions centralized so spacing and component behavior stay consistent.
    """

    outer_pad_x: int
    header_pad_top: int
    header_pad_bottom: int
    card_inner_pad_x: int
    card_inner_pad_y: int
    field_wrap_min_px: int
    table_separator_min_chars: int
    table_separator_max_chars: int
    empty_table_message: str
    empty_metrics_message: str
    section_feedback_default: str = "Waiting for first refresh."
    section_feedback_loading: str = "Refreshing section..."
    section_feedback_empty: str = "No data returned for this section."
    section_feedback_error: str = "Section refresh failed. Auto retry is enabled."
    table_loading_message: str = "Loading table data..."
    metrics_loading_message: str = "Loading metrics..."
    action_button_pad_x: int = 14
    action_button_pad_y: int = 7
    status_pad_top: int = 4
    status_pad_bottom: int = 10
    section_feedback_pad_top: int = 1
    section_feedback_pad_bottom: int = 7
    table_container_pad_top: int = 8
    text_pad_x: int = 8
    text_pad_y: int = 6


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    """
    Summary
    Convert a six-digit hex color string into integer RGB channels.

    Inputs
    color: Color string such as `#58a6ff`.

    Outputs
    Tuple of (r, g, b) channel integers in [0, 255].

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when the input cannot be parsed.

    Ties to other methods
    Used by `_blend_hex`.

    Why this exists
    Derived interaction colors are easier to maintain when computed from base theme colors.
    """
    try:
        normalized = str(color).strip()
        if not normalized.startswith("#"):
            raise ValueError("Color must start with '#'")
        hex_part = normalized[1:]
        if len(hex_part) != 6:
            raise ValueError("Color must use six hex digits")
        return (int(hex_part[0:2], 16), int(hex_part[2:4], 16), int(hex_part[4:6], 16))
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_hex_to_rgb", "Failed to parse hex color", exc)) from exc


def _blend_hex(base: str, overlay: str, ratio: float) -> str:
    """
    Summary
    Blend two hex colors together with a normalized ratio.

    Inputs
    base: Base color hex string.
    overlay: Overlay color hex string.
    ratio: Blend ratio in [0.0, 1.0] where 1.0 fully selects the overlay color.

    Outputs
    Blended hex color string.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when blending fails.

    Ties to other methods
    Used by `_build_ui_palette` to derive hover and disabled shades.

    Why this exists
    Keeps interaction shades tied to theme colors without adding extra config keys.
    """
    try:
        r_base, g_base, b_base = _hex_to_rgb(base)
        r_overlay, g_overlay, b_overlay = _hex_to_rgb(overlay)
        alpha = max(0.0, min(1.0, float(ratio)))
        r_out = int(round((r_base * (1.0 - alpha)) + (r_overlay * alpha)))
        g_out = int(round((g_base * (1.0 - alpha)) + (g_overlay * alpha)))
        b_out = int(round((b_base * (1.0 - alpha)) + (b_overlay * alpha)))
        return f"#{r_out:02x}{g_out:02x}{b_out:02x}"
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_blend_hex", "Failed to blend colors", exc)) from exc


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


def _table_separator_length(
    headers: tuple[str, ...],
    rows: Sequence[tuple[str, ...]],
    *,
    minimum: int,
    maximum: int,
) -> int:
    """
    Summary
    Compute a separator width for text tables based on rendered content.

    Inputs
    headers: Table headers.
    rows: Table rows.
    minimum: Minimum separator width.
    maximum: Maximum separator width.

    Outputs
    Separator length in characters.

    Side effects
    None.

    Error handling
    Returns a bounded fallback width when values are invalid.

    Ties to other methods
    Used by `DashboardApp.render_table`.

    Why this exists
    A fixed separator width clips wide tables and wastes space on narrow tables.
    """
    try:
        header_width = len(" | ".join(headers))
        row_width = max((len(" | ".join(row)) for row in rows), default=0)
        width = max(header_width, row_width)
        if width <= 0:
            width = int(minimum)
        bounded_min = max(8, int(minimum))
        bounded_max = max(bounded_min, int(maximum))
        return max(bounded_min, min(width, bounded_max))
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_table_separator_length", "Failed to compute separator length", exc)
        ) from exc


def _refresh_status_message(*, refreshed_at: str, total_sections: int, failures: int, elapsed_ms: int) -> str:
    """
    Summary
    Build a user-facing refresh status line for the dashboard header.

    Inputs
    refreshed_at: Time label in HH:MM:SS.
    total_sections: Number of section refresh attempts.
    failures: Number of failed sections.
    elapsed_ms: Duration in milliseconds.

    Outputs
    Human-readable status line.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when formatting fails.

    Ties to other methods
    Used by `DashboardApp._refresh`.

    Why this exists
    Header messaging should be consistent, concise, and actionable.
    """
    try:
        total = max(0, int(total_sections))
        failed = max(0, int(failures))
        ok_count = max(0, total - failed)
        elapsed = max(0, int(elapsed_ms))
        if failed > 0:
            return (
                f"Last refreshed: {refreshed_at} | {ok_count}/{total} sections OK | "
                f"{failed} errors | {elapsed} ms"
            )
        return f"Last refreshed: {refreshed_at} | {ok_count}/{total} sections OK | {elapsed} ms"
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_refresh_status_message", "Failed to build status message", exc)
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
    feedback: Optional[InlineStatusBadge] = None
    card: Optional[tk.Frame] = None
    table_container: Optional[tk.Frame] = None
    metrics_container: Optional[tk.Frame] = None


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
            self._refresh_after_id: str | None = None
            self._status_var = tk.StringVar(value="")
            self._status_label: tk.Label | None = None
            self._next_refresh_var = tk.StringVar(value="")
            self._next_refresh_label: tk.Label | None = None
            self._refresh_button: InteractiveButton | None = None
            self._refresh_in_progress = False
            self._scroll: ScrollContainer | None = None
            self._ui_palette = self._build_ui_palette()
            self._ui_tokens = self._build_ui_tokens()
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
            self.configure(bg=self._ui_palette.page_bg)
            self.geometry(self._cfg.ui.window_size)
            self.maxsize(self._cfg.gui.window_max_width, self._cfg.gui.window_max_height)

            self._build_layout()
            self._bind_keyboard_shortcuts()
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

    def _build_ui_palette(self) -> _UiPalette:
        """
        Summary
        Build the resolved UI color palette from configuration.

        Inputs
        None.

        Outputs
        `_UiPalette` containing base and interaction colors.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when palette derivation fails.

        Ties to other methods
        Used by `_build_layout`, `_set_card_border`, `_status_color`, and section feedback helpers.

        Why this exists
        Centralized color roles make global restyling a single-change operation.
        """
        try:
            page_bg = self._cfg.colors.bg
            card_bg = self._cfg.gui.card_bg
            card_border = self._cfg.gui.card_border
            accent = self._cfg.colors.section
            return _UiPalette(
                page_bg=page_bg,
                card_bg=card_bg,
                card_border=card_border,
                card_border_hover=_blend_hex(card_border, accent, 0.35),
                card_border_focus=accent,
                text_primary=self._cfg.colors.field,
                text_secondary=self._cfg.colors.label,
                text_muted=_blend_hex(self._cfg.colors.label, page_bg, 0.12),
                status_info=self._cfg.colors.label,
                status_loading=self._cfg.colors.section,
                status_success=self._cfg.colors.ok,
                status_warn=self._cfg.colors.warn,
                status_error=self._cfg.colors.bad,
                button_bg=_blend_hex(card_bg, accent, 0.22),
                button_hover_bg=_blend_hex(card_bg, accent, 0.32),
                button_active_bg=_blend_hex(card_bg, accent, 0.40),
                button_disabled_bg=_blend_hex(card_bg, page_bg, 0.34),
                button_disabled_fg=_blend_hex(self._cfg.colors.label, page_bg, 0.22),
                button_border=card_border,
                button_focus_border=accent,
            )
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._build_ui_palette", "Failed to derive UI palette", exc)
            ) from exc

    def _build_ui_tokens(self) -> _UiTokens:
        """
        Summary
        Build centralized UI tokens from configuration.

        Inputs
        None.

        Outputs
        `_UiTokens` with shared layout and rendering values.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when token derivation fails.

        Ties to other methods
        Used by layout and render helpers such as `_build_layout`, `render_table`, and `render_metrics_table`.

        Why this exists
        Keeps UI spacing and placeholder behavior consistent without scattering literals.
        """
        try:
            return _UiTokens(
                outer_pad_x=max(10, self._cfg.gui.section_padx + 6),
                header_pad_top=12,
                header_pad_bottom=8,
                card_inner_pad_x=14,
                card_inner_pad_y=12,
                field_wrap_min_px=280,
                table_separator_min_chars=28,
                table_separator_max_chars=160,
                empty_table_message="No entries available.",
                empty_metrics_message="No metrics available.",
                section_feedback_default="Waiting for first refresh.",
                section_feedback_loading="Refreshing section...",
                section_feedback_empty="No data returned for this section.",
                section_feedback_error="Section refresh failed. Auto retry is enabled.",
                table_loading_message="Loading table data...",
                metrics_loading_message="Loading metrics...",
                action_button_pad_x=14,
                action_button_pad_y=7,
                status_pad_top=4,
                status_pad_bottom=10,
                section_feedback_pad_top=1,
                section_feedback_pad_bottom=7,
                table_container_pad_top=8,
                text_pad_x=8,
                text_pad_y=6,
            )
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._build_ui_tokens", "Failed to derive UI tokens", exc)
            ) from exc

    def _new_label(
        self,
        *,
        parent: tk.Misc,
        text: str | None = None,
        textvariable: tk.StringVar | None = None,
        bg: str,
        fg: str,
        font_size: int,
        font_weight: str,
        wraplength: int | None = None,
        justify: Literal["left", "center", "right"] = "left",
    ) -> tk.Label:
        """
        Summary
        Create a consistently styled label for dashboard UI surfaces.

        Inputs
        parent: Parent widget.
        text: Static label text.
        textvariable: Optional Tk variable for dynamic text.
        bg: Background color.
        fg: Foreground color.
        font_size: Font size.
        font_weight: Font weight.
        wraplength: Optional wrap length in pixels.
        justify: Text justification.

        Outputs
        Configured `tk.Label`.

        Side effects
        Creates a Tk widget.

        Error handling
        Raises `RuntimeError` with module and method context when label creation fails.

        Ties to other methods
        Used by `_build_layout` and `_build_section_card`.

        Why this exists
        Prevents style drift and reduces repetitive widget configuration code.
        """
        try:
            label = tk.Label(
                parent,
                bg=bg,
                fg=fg,
                font=(self._cfg.fonts.family_default, font_size, font_weight),
                justify=justify,
            )
            if text is not None:
                label.configure(text=text)
            if textvariable is not None:
                label.configure(textvariable=textvariable)
            if wraplength is not None:
                label.configure(wraplength=int(wraplength))
            return label
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._new_label", "Failed to create label", exc)
            ) from exc

    def _status_color(self, level: str) -> str:
        """
        Summary
        Map a status level to the configured color used in the header.

        Inputs
        level: Status level such as info, loading, warn, or error.

        Outputs
        Hex color string.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when mapping fails unexpectedly.

        Ties to other methods
        Used by `_set_status`.

        Why this exists
        Centralizes header status color decisions.
        """
        try:
            palette_obj = self.__dict__.get("_ui_palette")
            palette = palette_obj if isinstance(palette_obj, _UiPalette) else None
            status_loading = palette.status_loading if palette is not None else self._cfg.colors.section
            status_success = palette.status_success if palette is not None else self._cfg.colors.ok
            status_warn = palette.status_warn if palette is not None else self._cfg.colors.warn
            status_error = palette.status_error if palette is not None else self._cfg.colors.bad
            status_info = palette.status_info if palette is not None else self._cfg.colors.label
            normalized = (level or "").strip().lower()
            if normalized == "loading":
                return status_loading
            if normalized == "success":
                return status_success
            if normalized == "warn":
                return status_warn
            if normalized == "error":
                return status_error
            return status_info
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._status_color", "Failed to map status color", exc)
            ) from exc

    def _set_status(self, text: str, *, level: str = "info") -> None:
        """
        Summary
        Update the header status text and color.

        Inputs
        text: Status message to display.
        level: Status level such as info, loading, warn, or error.

        Outputs
        None.

        Side effects
        Updates Tk variables and label styling.

        Error handling
        Raises `RuntimeError` with module and method context when updates fail.

        Ties to other methods
        Called by refresh scheduling and error paths.

        Why this exists
        Keeps user feedback consistent during loading, success, and failure states.
        """
        try:
            self._status_var.set(str(text))
            if self._status_label is not None:
                self._status_label.configure(fg=self._status_color(level))
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._set_status", "Failed to set status", exc)
            ) from exc

    def _set_refresh_controls_busy(self, busy: bool) -> None:
        """
        Summary
        Toggle header action controls between idle and busy states.

        Inputs
        busy: True when refresh work is running.

        Outputs
        None.

        Side effects
        Updates refresh button state and loading visuals.

        Error handling
        Raises `RuntimeError` with module and method context when state updates fail.

        Ties to other methods
        Used by `_refresh` and `_schedule_next_refresh`.

        Why this exists
        Prevents duplicate refresh requests and communicates current work state.
        """
        try:
            self._refresh_in_progress = bool(busy)
            button = self.__dict__.get("_refresh_button")
            if button is not None:
                button.set_loading(bool(busy))
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._set_refresh_controls_busy", "Failed to update refresh controls", exc
                )
            ) from exc

    def _set_next_refresh_hint(self, *, delay_ms: int) -> None:
        """
        Summary
        Update the header hint that shows when the next automatic refresh is scheduled.

        Inputs
        delay_ms: Delay in milliseconds for the next scheduled refresh.

        Outputs
        None.

        Side effects
        Updates a Tk string variable used in the header.

        Error handling
        Raises `RuntimeError` with module and method context when updates fail.

        Ties to other methods
        Used by `_schedule_next_refresh` and `_refresh`.

        Why this exists
        Clear timing feedback helps users understand when stale data will be retried.
        """
        try:
            seconds = max(1, int(round(float(delay_ms) / 1000.0)))
            next_refresh_var = self.__dict__.get("_next_refresh_var")
            if next_refresh_var is None:
                return
            next_refresh_var.set(f"Next automatic refresh in ~{seconds}s")
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._set_next_refresh_hint", "Failed to set refresh hint", exc)
            ) from exc

    def _set_section_feedback(self, key: str, message: str, *, level: str) -> None:
        """
        Summary
        Update inline feedback text for one section card.

        Inputs
        key: Section key.
        message: User-facing feedback text.
        level: Status level such as info, loading, success, warn, or error.

        Outputs
        None.

        Side effects
        Updates section badge text and color.

        Error handling
        Raises `RuntimeError` with module and method context when feedback updates fail.

        Ties to other methods
        Used by refresh lifecycle and table/metric rendering helpers.

        Why this exists
        Inline, per-section messaging gives users local context without scanning only the global header.
        """
        try:
            sections = self.__dict__.get("_sections", {})
            section = sections.get(key) if isinstance(sections, dict) else None
            if section is None or section.feedback is None:
                return
            section.feedback.set_message(message, level=level)
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._set_section_feedback", "Failed to set section feedback", exc)
            ) from exc

    def _bind_keyboard_shortcuts(self) -> None:
        """
        Summary
        Bind keyboard shortcuts for refresh and scrolling.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Installs global key bindings on the Tk root.

        Error handling
        Raises `RuntimeError` with module and method context when binding fails.

        Ties to other methods
        Uses `_on_refresh_shortcut`, `_on_scroll_home`, `_on_scroll_end`, and page scrolling handlers.

        Why this exists
        Improves keyboard accessibility and discoverability for power users.
        """
        try:
            self.bind_all("<F5>", self._on_refresh_shortcut)
            self.bind_all("<KeyPress-r>", self._on_refresh_shortcut)
            self.bind_all("<Home>", self._on_scroll_home)
            self.bind_all("<End>", self._on_scroll_end)
            self.bind_all("<Prior>", self._on_scroll_page_up)
            self.bind_all("<Next>", self._on_scroll_page_down)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._bind_keyboard_shortcuts", "Failed to bind shortcuts", exc
                )
            ) from exc

    def _on_refresh_shortcut(self, _event: tk.Event[tk.Misc]) -> str:
        """
        Summary
        Trigger an immediate manual refresh from a keyboard shortcut.

        Inputs
        _event: Tk key event.

        Outputs
        "break" to stop event propagation.

        Side effects
        Cancels pending scheduled refresh and runs a new cycle.

        Error handling
        Never raises; falls back to status updates on failures.

        Ties to other methods
        Uses `_cancel_scheduled_refresh` and `_refresh`.

        Why this exists
        Users should be able to request a fresh snapshot without waiting for the timer.
        """
        try:
            if bool(self.__dict__.get("_refresh_in_progress", False)):
                return "break"
            self._cancel_scheduled_refresh()
            self.after(0, self._refresh)
        except (tk.TclError, RuntimeError, ValueError, TypeError):
            return "break"
        return "break"

    def _on_refresh_button(self) -> None:
        """
        Summary
        Trigger a manual refresh from the header action button.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Delegates to the same immediate refresh flow used by keyboard shortcuts.

        Error handling
        Raises `RuntimeError` with module and method context when dispatch fails.

        Ties to other methods
        Uses `_on_refresh_shortcut`.

        Why this exists
        A visible action button improves discoverability for users who do not rely on keyboard shortcuts.
        """
        try:
            if self._refresh_in_progress:
                return
            self._cancel_scheduled_refresh()
            self._set_status("Manual refresh requested...", level="info")
            self.after(0, self._refresh)
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._on_refresh_button", "Failed to trigger manual refresh", exc)
            ) from exc

    def _on_scroll_home(self, _event: tk.Event[tk.Misc]) -> str:
        """
        Summary
        Scroll to the top of the dashboard.

        Inputs
        _event: Tk key event.

        Outputs
        "break" to stop event propagation.

        Side effects
        Moves scroll position.

        Error handling
        Never raises; returns "break" on failure.

        Ties to other methods
        Uses `ScrollContainer.scroll_to_top`.

        Why this exists
        Supports quick keyboard navigation in long dashboards.
        """
        try:
            if self._scroll is not None:
                self._scroll.scroll_to_top()
        except (tk.TclError, RuntimeError, ValueError, TypeError):
            return "break"
        return "break"

    def _on_scroll_end(self, _event: tk.Event[tk.Misc]) -> str:
        """
        Summary
        Scroll to the bottom of the dashboard.

        Inputs
        _event: Tk key event.

        Outputs
        "break" to stop event propagation.

        Side effects
        Moves scroll position.

        Error handling
        Never raises; returns "break" on failure.

        Ties to other methods
        Uses `ScrollContainer.scroll_to_bottom`.

        Why this exists
        Supports quick keyboard navigation in long dashboards.
        """
        try:
            if self._scroll is not None:
                self._scroll.scroll_to_bottom()
        except (tk.TclError, RuntimeError, ValueError, TypeError):
            return "break"
        return "break"

    def _on_scroll_page_up(self, _event: tk.Event[tk.Misc]) -> str:
        """
        Summary
        Scroll one page upward.

        Inputs
        _event: Tk key event.

        Outputs
        "break" to stop event propagation.

        Side effects
        Moves scroll position.

        Error handling
        Never raises; returns "break" on failure.

        Ties to other methods
        Uses `ScrollContainer.scroll_pages`.

        Why this exists
        Supports keyboard page navigation for accessibility.
        """
        try:
            if self._scroll is not None:
                self._scroll.scroll_pages(-1)
        except (tk.TclError, RuntimeError, ValueError, TypeError):
            return "break"
        return "break"

    def _on_scroll_page_down(self, _event: tk.Event[tk.Misc]) -> str:
        """
        Summary
        Scroll one page downward.

        Inputs
        _event: Tk key event.

        Outputs
        "break" to stop event propagation.

        Side effects
        Moves scroll position.

        Error handling
        Never raises; returns "break" on failure.

        Ties to other methods
        Uses `ScrollContainer.scroll_pages`.

        Why this exists
        Supports keyboard page navigation for accessibility.
        """
        try:
            if self._scroll is not None:
                self._scroll.scroll_pages(1)
        except (tk.TclError, RuntimeError, ValueError, TypeError):
            return "break"
        return "break"

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
            palette = self.__dict__.get("_ui_palette")
            default_fg = palette.text_primary if palette is not None else self._cfg.colors.field
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
            widget.configure(state="normal")
            widget.delete("1.0", tk.END)
            if rows:
                for label, value, status in rows:
                    tag = self._status_to_tag(status)
                    widget.insert(tk.END, f"{label}: {value} ", ())
                    widget.insert(tk.END, f"[{status}]\n", (tag,))
                self._set_section_feedback(
                    key,
                    f"Showing {len(rows)} metrics.",
                    level="success",
                )
            else:
                widget.insert(tk.END, self._ui_tokens.empty_metrics_message + "\n", ("empty",))
                self._set_section_feedback(key, self._ui_tokens.section_feedback_empty, level="info")
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
            widget.configure(state="normal")
            widget.delete("1.0", tk.END)
            widget.insert(tk.END, " | ".join(headers) + "\n", ("header",))
            widget.insert(
                tk.END,
                "-"
                * _table_separator_length(
                    headers,
                    rows,
                    minimum=self._ui_tokens.table_separator_min_chars,
                    maximum=self._ui_tokens.table_separator_max_chars,
                )
                + "\n",
                ("separator",),
            )
            if rows:
                for row in rows:
                    widget.insert(tk.END, " | ".join(row) + "\n")
                self._set_section_feedback(
                    key,
                    f"Showing {len(rows)} rows.",
                    level="success",
                )
            else:
                widget.insert(tk.END, self._ui_tokens.empty_table_message + "\n", ("empty",))
                self._set_section_feedback(key, self._ui_tokens.section_feedback_empty, level="info")
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
            root = tk.Frame(self, bg=self._ui_palette.page_bg)
            root.pack(fill="both", expand=True)

            header = tk.Frame(root, bg=self._ui_palette.page_bg)
            header.pack(
                fill="x",
                padx=self._ui_tokens.outer_pad_x,
                pady=(self._ui_tokens.header_pad_top, self._ui_tokens.header_pad_bottom),
            )

            title_row = tk.Frame(header, bg=self._ui_palette.page_bg)
            title_row.pack(fill="x")

            title = self._new_label(
                parent=title_row,
                text=self._cfg.ui.window_title,
                bg=self._ui_palette.page_bg,
                fg=self._ui_palette.text_primary,
                font_size=self._cfg.fonts.size_banner,
                font_weight=self._cfg.fonts.weight_bold,
            )
            title.pack(side="left", anchor="w")
            self._tooltips.set_static(
                title,
                "Mac Health Checkup dashboard. Hover over section titles, fields, metrics, and tables for details.",
            )

            right_controls = tk.Frame(title_row, bg=self._ui_palette.page_bg)
            right_controls.pack(side="right", anchor="e")

            self._refresh_button = InteractiveButton(
                right_controls,
                text="Refresh now",
                command=self._on_refresh_button,
                theme=ButtonTheme(
                    bg=self._ui_palette.button_bg,
                    fg=self._ui_palette.text_primary,
                    border=self._ui_palette.button_border,
                    hover_bg=self._ui_palette.button_hover_bg,
                    active_bg=self._ui_palette.button_active_bg,
                    disabled_bg=self._ui_palette.button_disabled_bg,
                    disabled_fg=self._ui_palette.button_disabled_fg,
                    focus_border=self._ui_palette.button_focus_border,
                ),
                font_family=self._cfg.fonts.family_default,
                font_size=self._cfg.fonts.size_field,
                font_weight=self._cfg.fonts.weight_bold,
                pad_x=self._ui_tokens.action_button_pad_x,
                pad_y=self._ui_tokens.action_button_pad_y,
                loading_text="Refreshing...",
            )
            self._refresh_button.pack(anchor="e")
            self._tooltips.set_static(
                self._refresh_button,
                "Refresh all sections now. Keyboard shortcuts: F5 or R.",
            )

            next_refresh = self._new_label(
                parent=header,
                textvariable=self._next_refresh_var,
                bg=self._ui_palette.page_bg,
                fg=self._ui_palette.text_secondary,
                font_size=self._cfg.fonts.size_tooltip,
                font_weight=self._cfg.fonts.weight_normal,
            )
            next_refresh.pack(anchor="w", pady=(self._ui_tokens.status_pad_top, 0))
            self._next_refresh_label = next_refresh
            self._set_next_refresh_hint(delay_ms=self._cfg.gui.auto_refresh_ms)

            status = self._new_label(
                parent=header,
                textvariable=self._status_var,
                bg=self._ui_palette.page_bg,
                fg=self._ui_palette.status_info,
                font_size=self._cfg.fonts.size_tooltip,
                font_weight=self._cfg.fonts.weight_normal,
            )
            status.pack(anchor="w", pady=(self._ui_tokens.status_pad_top, self._ui_tokens.status_pad_bottom))
            self._status_label = status
            self._set_status("Waiting for first refresh...", level="info")
            self._tooltips.set_static(
                status,
                "Refresh status and diagnostic messages. Values update on a timer and may be cached briefly.",
            )

            separator = tk.Frame(root, bg=self._ui_palette.card_border, height=1)
            separator.pack(fill="x", padx=self._ui_tokens.outer_pad_x, pady=(0, 10))

            self._scroll = ScrollContainer(
                root, bg=self._ui_palette.page_bg, scroll_divisor=self._cfg.gui.drag_scroll_divisor
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
                self._build_section_card(parent=parent, key=key, title=title, subtitle=subtitle)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._build_sections", "Failed to build sections", exc)
            ) from exc

    def _build_section_card(self, *, parent: tk.Frame, key: str, title: str, subtitle: str) -> None:
        """
        Summary
        Create one section card with title, subtitle, and primary field widgets.

        Inputs
        parent: Parent frame receiving the card.
        key: Section key.
        title: Section title text.
        subtitle: Section subtitle text.

        Outputs
        None.

        Side effects
        Creates widgets, binds hover and focus affordances, and stores section references.

        Error handling
        Raises `RuntimeError` with module and method context when card creation fails.

        Ties to other methods
        Called by `_build_sections` and consumed by `set_field`, `render_table`, and `render_metrics_table`.

        Why this exists
        Encapsulates repeated card construction so visual consistency is automatic across sections.
        """
        try:
            card = tk.Frame(
                parent,
                bg=self._ui_palette.card_bg,
                highlightbackground=self._ui_palette.card_border,
                highlightthickness=1,
                takefocus=0,
            )
            card.pack(fill="x", padx=self._ui_tokens.outer_pad_x, pady=self._cfg.gui.section_pady)

            content = tk.Frame(card, bg=self._ui_palette.card_bg)
            content.pack(
                fill="x",
                padx=self._ui_tokens.card_inner_pad_x,
                pady=self._ui_tokens.card_inner_pad_y,
            )

            title_label = self._new_label(
                parent=content,
                text=title,
                bg=self._ui_palette.card_bg,
                fg=self._ui_palette.status_loading,
                font_size=self._cfg.fonts.size_section,
                font_weight=self._cfg.fonts.weight_bold,
            )
            title_label.pack(anchor="w")
            self._tooltips.set_static(title_label, section_help_text(key))

            subtitle_label = self._new_label(
                parent=content,
                text=subtitle,
                bg=self._ui_palette.card_bg,
                fg=self._ui_palette.text_secondary,
                font_size=self._cfg.fonts.size_field,
                font_weight=self._cfg.fonts.weight_normal,
            )
            subtitle_label.pack(anchor="w", pady=(2, self._ui_tokens.section_feedback_pad_bottom))
            self._tooltips.set_static(subtitle_label, section_help_text(key))

            feedback_label = InlineStatusBadge(
                content,
                bg=self._ui_palette.card_bg,
                theme=StatusTheme(
                    info_fg=self._ui_palette.status_info,
                    loading_fg=self._ui_palette.status_loading,
                    success_fg=self._ui_palette.status_success,
                    warn_fg=self._ui_palette.status_warn,
                    error_fg=self._ui_palette.status_error,
                ),
                font_family=self._cfg.fonts.family_default,
                font_size=self._cfg.fonts.size_tooltip,
                font_weight=self._cfg.fonts.weight_normal,
            )
            feedback_label.pack(anchor="w", pady=(self._ui_tokens.section_feedback_pad_top, 0))

            field_label = self._new_label(
                parent=content,
                text="Waiting for section data...",
                bg=self._ui_palette.card_bg,
                fg=self._ui_palette.text_muted,
                font_size=self._cfg.fonts.size_field,
                font_weight=self._cfg.fonts.weight_normal,
                wraplength=self._cfg.gui.content_wrap,
            )
            field_label.configure(anchor="w", takefocus=1)
            field_label.pack(anchor="w", fill="x", pady=(self._ui_tokens.section_feedback_pad_bottom, 0))
            self._tooltips.set_static(field_label, section_help_text(key))

            section_widgets = _SectionWidgets(
                frame=content,
                title=title_label,
                subtitle=subtitle_label,
                field=field_label,
                feedback=feedback_label,
                card=card,
            )
            self._sections[key] = section_widgets
            self._set_section_feedback(key, self._ui_tokens.section_feedback_default, level="info")
            self._bind_card_affordances(key=key, section=section_widgets)
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._build_section_card", "Failed to build section card", exc
                )
            ) from exc

    def _bind_card_affordances(self, *, key: str, section: _SectionWidgets) -> None:
        """
        Summary
        Attach hover and focus affordances for one section card.

        Inputs
        key: Section key.
        section: Section widget references.

        Outputs
        None.

        Side effects
        Binds widget events and updates card border styling as interaction states change.

        Error handling
        Raises `RuntimeError` with module and method context when event binding fails.

        Ties to other methods
        Called by `_build_section_card` and uses `_set_card_border`.

        Why this exists
        Subtle interaction cues improve discoverability and readability for dense dashboards.
        """
        try:
            card = section.card
            if card is None:
                return
            bind_targets: list[tk.Widget] = [
                card,
                section.frame,
                section.title,
                section.subtitle,
                section.field,
            ]
            if section.feedback is not None:
                bind_targets.append(section.feedback)
            for target in bind_targets:
                target.bind("<Enter>", self._card_state_handler(key=key, mode="hover"), add="+")
                target.bind("<Leave>", self._card_state_handler(key=key, mode="normal"), add="+")
                target.bind("<FocusIn>", self._card_state_handler(key=key, mode="focus"), add="+")
                target.bind("<FocusOut>", self._card_state_handler(key=key, mode="normal"), add="+")
            self._set_card_border(key, "normal")
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "DashboardApp._bind_card_affordances",
                    "Failed to bind card affordances",
                    exc,
                )
            ) from exc

    def _set_card_border(self, key: str, mode: str) -> None:
        """
        Summary
        Apply card border styling for normal, hover, and focus interaction states.

        Inputs
        key: Section key.
        mode: One of normal, hover, or focus.

        Outputs
        None.

        Side effects
        Updates card highlight style.

        Error handling
        Raises `RuntimeError` with module and method context when style updates fail.

        Ties to other methods
        Used by `_bind_card_affordances` and text focus handlers.

        Why this exists
        Consistent interactive borders improve visual affordance without changing core behavior.
        """
        try:
            section = self._sections.get(key)
            if section is None or section.card is None:
                return
            palette = self.__dict__.get("_ui_palette")
            cfg_obj = self.__dict__.get("_cfg")
            cfg_gui = getattr(cfg_obj, "gui", object())
            cfg_colors = getattr(cfg_obj, "colors", object())
            default_border = (
                palette.card_border
                if palette is not None
                else getattr(cfg_gui, "card_border", "#313d4b")
            )
            hover_border = (
                palette.card_border_hover
                if palette is not None
                else getattr(cfg_colors, "section", "#58a6ff")
            )
            focus_border = (
                palette.card_border_focus
                if palette is not None
                else getattr(cfg_colors, "section", "#58a6ff")
            )
            normalized = (mode or "").strip().lower()
            if normalized == "focus":
                border = focus_border
                thickness = 2
            elif normalized == "hover":
                border = hover_border
                thickness = 1
            else:
                border = default_border
                thickness = 1
            section.card.configure(
                highlightbackground=border,
                highlightcolor=border,
                highlightthickness=thickness,
            )
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._set_card_border", "Failed to set card border", exc)
            ) from exc

    def _card_state_handler(self, *, key: str, mode: str) -> Callable[[tk.Event[tk.Misc]], None]:
        """
        Summary
        Build a typed Tk event handler that updates card border state.

        Inputs
        key: Section key.
        mode: Card border mode to apply.

        Outputs
        Callable accepting a Tk event.

        Side effects
        Returned function updates card border styling when invoked.

        Error handling
        The returned handler never raises.

        Ties to other methods
        Used by `_bind_card_affordances` and `_create_text_widget`.

        Why this exists
        Tk binding callbacks should stay type-safe under strict mypy settings.
        """

        def _handler(_event: tk.Event[tk.Misc]) -> None:
            try:
                self._set_card_border(key, mode)
            except (tk.TclError, RuntimeError, ValueError, TypeError):
                return

        return _handler

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
            height = int(self._cfg.gui.scrollable_rows.get(key, self._cfg.gui.table_max_visible_rows))
            if height <= 0:
                height = int(self._cfg.gui.table_max_visible_rows)
            palette = self.__dict__.get("_ui_palette")
            tokens = self.__dict__.get("_ui_tokens")
            card_bg = palette.card_bg if palette is not None else self._cfg.gui.card_bg
            text_primary = palette.text_primary if palette is not None else self._cfg.colors.field
            select_bg = (
                palette.button_hover_bg if palette is not None else getattr(self._cfg.colors, "section", "#4c8df5")
            )
            inactive_select_bg = (
                palette.button_bg if palette is not None else getattr(self._cfg.gui, "card_border", "#313d4b")
            )
            table_pad_top = tokens.table_container_pad_top if tokens is not None else 8
            text_pad_x = tokens.text_pad_x if tokens is not None else 8
            text_pad_y = tokens.text_pad_y if tokens is not None else 6

            container = tk.Frame(section.frame, bg=card_bg)
            container.pack(fill="x", pady=(table_pad_top, 0))
            if kind == "table":
                section.table_container = container
            else:
                section.metrics_container = container

            scrollbar_y = tk.Scrollbar(container, orient="vertical")
            scrollbar_y.pack(side="right", fill="y")

            scrollbar_x = tk.Scrollbar(container, orient="horizontal")
            scrollbar_x.pack(side="bottom", fill="x")

            text_widget = tk.Text(
                container,
                height=height,
                bg=card_bg,
                fg=text_primary,
                font=(self._cfg.fonts.family_mono, self._cfg.fonts.size_field),
                wrap="none",
                relief="flat",
                highlightthickness=0,
                borderwidth=0,
                padx=text_pad_x,
                pady=text_pad_y,
                yscrollcommand=scrollbar_y.set,
                xscrollcommand=scrollbar_x.set,
                takefocus=1,
                insertbackground=text_primary,
                selectbackground=select_bg,
                selectforeground=text_primary,
                inactiveselectbackground=inactive_select_bg,
            )
            scrollbar_y.configure(command=text_widget.yview)
            scrollbar_x.configure(command=text_widget.xview)
            text_widget.bind("<FocusIn>", self._card_state_handler(key=key, mode="focus"), add="+")
            text_widget.bind("<FocusOut>", self._card_state_handler(key=key, mode="normal"), add="+")
            text_widget.configure(state="disabled")
            text_widget.pack(side="left", fill="both", expand=True)
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
            palette = self.__dict__.get("_ui_palette")
            header = palette.text_secondary if palette is not None else self._cfg.colors.label
            separator = palette.card_border if palette is not None else self._cfg.gui.card_border
            ok = palette.status_success if palette is not None else self._cfg.colors.ok
            warn = palette.status_warn if palette is not None else self._cfg.colors.warn
            bad = palette.status_error if palette is not None else self._cfg.colors.bad
            info = palette.status_info if palette is not None else self._cfg.colors.label
            empty = palette.text_secondary if palette is not None else self._cfg.colors.label
            loading = palette.status_loading if palette is not None else self._cfg.colors.section
            unknown = palette.text_primary if palette is not None else self._cfg.colors.field
            widget.tag_configure("header", foreground=header)
            widget.tag_configure("separator", foreground=separator)
            widget.tag_configure("ok", foreground=ok)
            widget.tag_configure("warn", foreground=warn)
            widget.tag_configure("bad", foreground=bad)
            widget.tag_configure("info", foreground=info)
            widget.tag_configure("empty", foreground=empty)
            widget.tag_configure("loading", foreground=loading)
            widget.tag_configure("unknown", foreground=unknown)
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
            if normalized in {"info", "note"}:
                return "info"
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
            outer_pad = self._ui_tokens.outer_pad_x
            wrap = max(
                self._ui_tokens.field_wrap_min_px,
                min(self._cfg.gui.content_wrap, width - (outer_pad * 2) - 72),
            )
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
            widget.configure(state="normal")
            widget.delete("1.0", tk.END)
            if message.strip():
                normalized = (level or "").strip().lower()
                tag = "bad" if normalized == "error" else "loading" if normalized == "loading" else "empty"
                widget.insert(tk.END, message.strip() + "\n", (tag,))
            widget.configure(state="disabled")
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

    def _cancel_scheduled_refresh(self) -> None:
        """
        Summary
        Cancel any pending scheduled refresh callback.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Cancels Tk `after` callback when present.

        Error handling
        Silently ignores stale timer ids that have already fired.

        Ties to other methods
        Used by `_schedule_next_refresh`, manual refresh shortcuts, and close handling.

        Why this exists
        Ensures only one refresh timer remains active at a time.
        """
        try:
            if self._refresh_after_id is None:
                return
            try:
                self.after_cancel(self._refresh_after_id)
            except tk.TclError:
                pass
            finally:
                self._refresh_after_id = None
        except (RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "DashboardApp._cancel_scheduled_refresh",
                    "Failed to cancel scheduled refresh",
                    exc,
                )
            ) from exc

    def _schedule_next_refresh(self, delay_ms: int) -> None:
        """
        Summary
        Schedule the next refresh callback with a single active timer.

        Inputs
        delay_ms: Delay in milliseconds.

        Outputs
        None.

        Side effects
        Cancels prior refresh timer and schedules a new one.

        Error handling
        Raises `RuntimeError` with module and method context when scheduling fails.

        Ties to other methods
        Used by `_refresh`.

        Why this exists
        Prevents overlapping timers after manual refresh requests.
        """
        try:
            self._cancel_scheduled_refresh()
            bounded_delay = max(1, int(delay_ms))
            self._refresh_after_id = self.after(bounded_delay, self._run_scheduled_refresh)
            self._set_next_refresh_hint(delay_ms=bounded_delay)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._schedule_next_refresh", "Failed to schedule next refresh", exc
                )
            ) from exc

    def _run_scheduled_refresh(self) -> None:
        """
        Summary
        Execute a scheduled refresh callback.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Clears tracked timer id and runs `_refresh`.

        Error handling
        Never raises to the Tk event loop.

        Ties to other methods
        Scheduled by `_schedule_next_refresh`.

        Why this exists
        Keeps refresh scheduling robust even when callbacks race with manual refresh triggers.
        """
        self._refresh_after_id = None
        self._refresh()

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
            self._cancel_scheduled_refresh()
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
        total_sections = len(SECTION_HANDLERS)
        now = datetime.now().strftime("%H:%M:%S")
        started = time.perf_counter()
        tokens = self.__dict__.get("_ui_tokens")
        loading_feedback = (
            tokens.section_feedback_loading if tokens is not None else "Refreshing section..."
        )
        error_feedback = (
            tokens.section_feedback_error
            if tokens is not None
            else "Section refresh failed. Auto retry is enabled."
        )
        try:
            self._set_refresh_controls_busy(True)
            self._set_status(f"Refreshing {total_sections} sections...", level="loading")
            self.update_idletasks()
            for key in SECTION_HANDLERS:
                self._queue.enqueue(key)
                self._set_section_feedback(key, loading_feedback, level="loading")
            for key in self._queue.drain():
                try:
                    run_section(self, key)
                    self._set_section_feedback(key, f"Updated at {now}.", level="success")
                except Exception as exc:
                    failures += 1
                    render_exc: Exception | None = None
                    try:
                        self._clear_section_data_views(
                            key,
                            message="Data unavailable. The section will retry on the next refresh.",
                        )
                        palette = self.__dict__.get("_ui_palette")
                        error_color = palette.status_error if palette is not None else self._cfg.colors.bad
                        self.set_field(
                            key,
                            f"Unable to refresh ({type(exc).__name__}). Hover for details.",
                            fg=error_color,
                            tooltip=str(exc),
                        )
                        self._set_section_feedback(key, error_feedback, level="error")
                    except Exception as field_exc:
                        render_exc = field_exc
                    if render_exc is not None:
                        continue
            elapsed_ms = int((time.perf_counter() - started) * 1000.0)
            if failures > 0:
                self._set_status(
                    _refresh_status_message(
                        refreshed_at=now,
                        total_sections=total_sections,
                        failures=failures,
                        elapsed_ms=elapsed_ms,
                    ),
                    level="warn",
                )
            else:
                self._set_status(
                    _refresh_status_message(
                        refreshed_at=now,
                        total_sections=total_sections,
                        failures=0,
                        elapsed_ms=elapsed_ms,
                    ),
                    level="info",
                )
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            self._set_status(f"Refresh error at {now}: {type(exc).__name__}", level="error")
        finally:
            try:
                self._set_refresh_controls_busy(False)
                if not self._shutdown.shutdown_requested():
                    self._schedule_next_refresh(self._cfg.gui.auto_refresh_ms)
            except (tk.TclError, RuntimeError, ValueError, TypeError):
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
            self._cancel_scheduled_refresh()
            self._shutdown.trigger_shutdown()
            self.destroy()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._on_close", "Failed to close UI", exc)
            ) from exc
