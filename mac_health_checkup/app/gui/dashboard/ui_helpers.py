from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from mac_health_checkup.app.gui.widgets.controls import InlineStatusBadge
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/ui_helpers.py"


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

    mode: str
    colors: Mapping[str, str]
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
        raise RuntimeError(
            format_error(MODULE_PATH, "_hex_to_rgb", "Failed to parse hex color", exc)
        ) from exc


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
                cursor += 3
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
            format_error(
                MODULE_PATH,
                "_table_separator_length",
                "Failed to compute separator length",
                exc,
            )
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
