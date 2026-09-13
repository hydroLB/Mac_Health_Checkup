from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional, Protocol

from mac_health_checkup.app.gui.dashboard.ui_helpers import (
    _SectionWidgets,
    _table_separator_length,
    _UiTokens,
)
from mac_health_checkup.core.config import Config


class _EffectiveTableHeightFn(Protocol):
    def __call__(self, *, key: str, base_height: int) -> int:
        """
        Summary
        Resolve the effective detail-widget height for one section.

        Inputs
        key: Section key.
        base_height: Configured baseline row count.

        Outputs
        Effective row count.

        Side effects
        None.

        Error handling
        Implementations may propagate host calculation failures.

        Ties to other methods
        Used by `create_text_widget`.

        Why this exists
        The render helper needs the host sizing callback without depending on the full mixin type.
        """
        ...


class _CardStateHandlerFn(Protocol):
    def __call__(self, *, key: str, mode: str) -> Callable[[tk.Event[tk.Misc]], None]:
        """
        Summary
        Build one card-state handler for a focus or hover transition.

        Inputs
        key: Section key.
        mode: Interaction mode to apply.

        Outputs
        Tk event handler callable.

        Side effects
        None.

        Error handling
        Implementations may propagate host binding errors.

        Ties to other methods
        Used by `create_text_widget`.

        Why this exists
        The support helper needs the host event-factory contract without reaching back into the mixin class.
        """
        ...


class _HorizontalScrollbarVisibilityFn(Protocol):
    def __call__(self, scrollbar: tk.Scrollbar, *, visible: bool) -> None:
        """
        Summary
        Show or hide the horizontal scrollbar for a text widget container.

        Inputs
        scrollbar: Target Tk scrollbar.
        visible: Whether the scrollbar should be visible.

        Outputs
        None.

        Side effects
        Mutates scrollbar geometry management.

        Error handling
        Implementations may propagate Tk geometry errors.

        Ties to other methods
        Used by `create_text_widget`.

        Why this exists
        The render helper needs the host scrollbar-visibility policy without embedding layout ownership.
        """
        ...


@dataclass(frozen=True)
class TextInsert:
    """
    Summary
    Describe one text insertion operation for a Tk text widget.

    Inputs
    text: Text content to insert.
    tags: Text tags to apply.

    Outputs
    Immutable insertion record.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Returned by render-planning helpers and consumed by `render_mixin.py`.

    Why this exists
    Render planning should be testable without mutating a Tk widget directly.
    """

    text: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenderPlan:
    """
    Summary
    Hold the deterministic text and feedback plan for rendering one section detail view.

    Inputs
    inserts: Ordered text insertion operations.
    feedback_message: Section feedback text.
    feedback_level: Section feedback severity.

    Outputs
    Immutable render plan.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Returned by `plan_metrics_render` and `plan_table_render`.

    Why this exists
    The Tk mixin should coordinate widget updates, but the text plan itself is pure data.
    """

    inserts: tuple[TextInsert, ...]
    feedback_message: str
    feedback_level: str


def status_to_tag(level: str, *, default: str = "unknown") -> str:
    """
    Summary
    Normalize a status or feedback level into a shared Tk text tag.

    Inputs
    level: Status or feedback string such as "ok", "warn", or "error".
    default: Tag to return when the level is not recognized.

    Outputs
    Text tag name.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `plan_metrics_render` and `clear_text_widget`.

    Why this exists
    Tk renderers and fallback messaging should share one normalization policy instead of drifting apart.
    """
    normalized = (level or "").strip().lower()
    if normalized in {"ok", "good", "pass", "success"}:
        return "ok"
    if normalized in {"warn", "warning"}:
        return "warn"
    if normalized in {"bad", "fail", "error"}:
        return "bad"
    if normalized in {"working", "loading"}:
        return "loading"
    if normalized in {"ready", "info", "note"}:
        return "info"
    return default


def style_scrollbar(scrollbar: tk.Scrollbar, *, color_fn: Callable[[str], str]) -> None:
    """
    Summary
    Apply centralized low-contrast scrollbar styling.

    Inputs
    scrollbar: Target Tk scrollbar.
    color_fn: Host color resolver.

    Outputs
    None.

    Side effects
    Updates scrollbar visual options.

    Error handling
    Never raises for unsupported platform-specific options.

    Ties to other methods
    Used by `create_text_widget`.

    Why this exists
    Keeps widget-creation details out of the render coordinator.
    """
    try:
        scrollbar.configure(
            bg=color_fn("scrollbar.thumb"),
            troughcolor=color_fn("scrollbar.track"),
            activebackground=color_fn("scrollbar.arrow"),
            relief="flat",
            bd=0,
            highlightthickness=0,
            width=10,
        )
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
        return


def plan_metrics_render(
    *,
    rows: list[tuple[str, str, str]] | tuple[tuple[str, str, str], ...],
    empty_metrics_message: str,
    status_to_tag_fn: Callable[[str], str],
) -> RenderPlan:
    """
    Summary
    Build the deterministic text and feedback plan for a metrics widget.

    Inputs
    rows: Metrics rows as `(label, value, status)` tuples.
    empty_metrics_message: Empty-state message when no metrics exist.
    status_to_tag_fn: Status-to-tag mapper.

    Outputs
    `RenderPlan`.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `render_mixin.render_metrics_table`.

    Why this exists
    Metrics row formatting is pure logic and should not be buried inside Tk widget mutation.
    """
    if not rows:
        return RenderPlan(
            inserts=(TextInsert(empty_metrics_message + "\n", ("empty",)),),
            feedback_message="No data returned for this section.",
            feedback_level="info",
        )
    inserts: list[TextInsert] = []
    for label, value, status in rows:
        inserts.append(TextInsert(f"{label}: {value} "))
        inserts.append(TextInsert(f"[{status}]\n", (status_to_tag_fn(status),)))
    return RenderPlan(
        inserts=tuple(inserts),
        feedback_message=f"Showing {len(rows)} metrics.",
        feedback_level="success",
    )


def plan_table_render(
    *,
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]] | tuple[tuple[str, ...], ...],
    empty_table_message: str,
    separator_min_chars: int,
    separator_max_chars: int,
) -> RenderPlan:
    """
    Summary
    Build the deterministic text and feedback plan for a table widget.

    Inputs
    headers: Column headers.
    rows: Table rows.
    empty_table_message: Empty-state message when no rows exist.
    separator_min_chars: Minimum separator length.
    separator_max_chars: Maximum separator length.

    Outputs
    `RenderPlan`.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `render_mixin.render_table`.

    Why this exists
    Header/separator/row planning is pure formatting logic and should stay testable outside Tk.
    """
    inserts: list[TextInsert] = [
        TextInsert(" | ".join(headers) + "\n", ("header",)),
        TextInsert(
            "-"
            * _table_separator_length(
                headers,
                rows,
                minimum=separator_min_chars,
                maximum=separator_max_chars,
            )
            + "\n",
            ("separator",),
        ),
    ]
    if rows:
        inserts.extend(TextInsert(" | ".join(row) + "\n") for row in rows)
        return RenderPlan(
            inserts=tuple(inserts),
            feedback_message=f"Showing {len(rows)} rows.",
            feedback_level="success",
        )
    inserts.append(TextInsert(empty_table_message + "\n", ("empty",)))
    return RenderPlan(
        inserts=tuple(inserts),
        feedback_message="No data returned for this section.",
        feedback_level="info",
    )


def set_horizontal_scrollbar_visibility(scrollbar: tk.Scrollbar, *, visible: bool) -> None:
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
    Used by `create_text_widget`.

    Why this exists
    Keeps scrollbar visibility logic testable outside the Tk host.
    """
    try:
        if visible:
            scrollbar.pack(side="bottom", fill="x")
            return
        pack_forget = getattr(scrollbar, "pack_forget", None)
        if callable(pack_forget):
            pack_forget()
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
        return


def create_text_widget(
    *,
    key: str,
    section: _SectionWidgets,
    kind: str,
    cfg: Config,
    ui_tokens: Optional[_UiTokens],
    table_base_heights: dict[str, int],
    color_fn: Callable[[str], str],
    effective_table_height_fn: _EffectiveTableHeightFn,
    card_state_handler_fn: _CardStateHandlerFn,
    style_scrollbar_fn: Callable[[tk.Scrollbar], None],
    set_horizontal_scrollbar_visibility_fn: _HorizontalScrollbarVisibilityFn,
) -> tk.Text:
    """
    Summary
    Create a read-only Text widget with vertical and horizontal scrollbars for a section.

    Inputs
    key: Section key used for per-section sizing.
    section: Section widget container that owns the widget.
    kind: View type, either table or metrics.
    cfg: Host configuration.
    ui_tokens: Optional UI spacing tokens.
    table_base_heights: Mutable map of baseline row budgets.
    color_fn: Host color resolver.
    effective_table_height_fn: Host final-height calculator.
    card_state_handler_fn: Host focus handler factory.
    style_scrollbar_fn: Scrollbar styling callback.
    set_horizontal_scrollbar_visibility_fn: Horizontal visibility callback.

    Outputs
    A `tk.Text` widget configured for read-only rendering.

    Side effects
    Adds new Tk widgets to the section frame.

    Error handling
    Propagates Tk/configuration failures to the caller.

    Ties to other methods
    Called by `DashboardApp._create_text_widget`.

    Why this exists
    Keeps the render mixin focused on coordination rather than widget construction details.
    """
    base_height = int(cfg.gui.scrollable_rows.get(key, cfg.gui.table_max_visible_rows))
    if base_height <= 0:
        base_height = int(cfg.gui.table_max_visible_rows)
    table_base_heights[key] = base_height
    height = effective_table_height_fn(key=key, base_height=base_height)
    card_bg = color_fn("surface.card")
    inset_bg = color_fn("surface.inset")
    text_primary = color_fn("text.primary")
    select_bg = color_fn("table.selection.active")
    inactive_select_bg = color_fn("table.selection.inactive")
    table_pad_top = ui_tokens.table_container_pad_top if ui_tokens is not None else 8
    text_pad_x = ui_tokens.text_pad_x if ui_tokens is not None else 8
    configured_pad_y = ui_tokens.text_pad_y if ui_tokens is not None else 6
    inner_pad_x = ui_tokens.card_inner_pad_x if ui_tokens is not None else 12
    inner_pad_y = ui_tokens.card_inner_pad_y if ui_tokens is not None else 10
    table_row_height = int(getattr(cfg.gui, "table_row_height", 22))
    text_font_size = max(
        9,
        min(int(cfg.fonts.size_field), max(9, int(round(float(table_row_height) * 0.56)))),
    )
    text_pad_y = max(2, configured_pad_y, int(round((table_row_height - text_font_size) / 2)))

    container = tk.Frame(section.frame, bg=card_bg)
    container.pack(fill="x", padx=inner_pad_x, pady=(table_pad_top, inner_pad_y))
    if kind == "table":
        section.table_container = container
    else:
        section.metrics_container = container

    scrollbar_y = tk.Scrollbar(container, orient="vertical")
    style_scrollbar_fn(scrollbar_y)
    scrollbar_y.pack(side="right", fill="y")

    scrollbar_x = tk.Scrollbar(container, orient="horizontal")
    style_scrollbar_fn(scrollbar_x)

    horizontal_visible = {"value": False}

    def _on_xscroll(first: float, last: float) -> object:
        """
        Summary
        Mirror horizontal overflow state into the optional bottom scrollbar.

        Inputs
        first: Leading normalized x-scroll fraction.
        last: Trailing normalized x-scroll fraction.

        Outputs
        `None`.

        Side effects
        Updates scrollbar position and toggles horizontal scrollbar visibility.

        Error handling
        Returns `None` on Tk and conversion failures to keep widget wiring resilient.

        Ties to other methods
        Used as the `xscrollcommand` callback inside `create_text_widget`.

        Why this exists
        Overflow visibility is runtime state, but it is still local to text-widget creation and should stay explicit.
        """
        try:
            scrollbar_x.set(str(first), str(last))
            first_f = float(first)
            last_f = float(last)
            has_overflow = first_f > 0.0 or last_f < 1.0
            if has_overflow != horizontal_visible["value"]:
                horizontal_visible["value"] = has_overflow
                set_horizontal_scrollbar_visibility_fn(scrollbar_x, visible=has_overflow)
            return None
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

    text_widget = tk.Text(
        container,
        height=height,
        bg=inset_bg,
        fg=text_primary,
        font=(cfg.fonts.family_mono, text_font_size),
        wrap="none",
        relief="flat",
        highlightthickness=0,
        borderwidth=0,
        padx=text_pad_x,
        pady=text_pad_y,
        yscrollcommand=scrollbar_y.set,
        xscrollcommand=_on_xscroll,
        takefocus=1,
        insertbackground=text_primary,
        selectbackground=select_bg,
        selectforeground=text_primary,
        inactiveselectbackground=inactive_select_bg,
    )
    scrollbar_y.configure(command=text_widget.yview)
    scrollbar_x.configure(command=text_widget.xview)
    set_horizontal_scrollbar_visibility_fn(scrollbar_x, visible=False)
    text_widget.bind("<FocusIn>", card_state_handler_fn(key=key, mode="focus"), add="+")
    text_widget.bind("<FocusOut>", card_state_handler_fn(key=key, mode="normal"), add="+")
    text_widget.configure(state="disabled")
    text_widget.pack(side="left", fill="both", expand=True)
    return text_widget


def configure_text_tags(widget: tk.Text, *, color_fn: Callable[[str], str]) -> None:
    """
    Summary
    Configure shared Text widget tags for table and metrics rendering.

    Inputs
    widget: Text widget to configure.
    color_fn: Host color resolver.

    Outputs
    None.

    Side effects
    Updates tag configuration on the widget.

    Error handling
    Propagates widget failures to the caller.

    Ties to other methods
    Used by `render_table` and `render_metrics_table`.

    Why this exists
    Centralizes widget tag styling outside the render coordinator.
    """
    header = color_fn("table.header")
    separator = color_fn("table.separator")
    ok = color_fn("status.success")
    warn = color_fn("status.warn")
    bad = color_fn("status.error")
    info = color_fn("status.ready")
    empty = color_fn("text.empty")
    loading = color_fn("status.working")
    unknown = color_fn("text.primary")
    table_bg = color_fn("surface.inset")
    widget.tag_configure("header", foreground=header)
    widget.tag_configure("separator", foreground=separator)
    widget.tag_configure("ok", foreground=ok)
    widget.tag_configure("warn", foreground=warn)
    widget.tag_configure("bad", foreground=bad)
    widget.tag_configure("info", foreground=info)
    widget.tag_configure("empty", foreground=empty, background=table_bg)
    widget.tag_configure("loading", foreground=loading)
    widget.tag_configure("unknown", foreground=unknown)


def clear_text_widget(widget: tk.Text, *, message: str, level: str = "info") -> None:
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
    Propagates widget failures to the caller.

    Ties to other methods
    Used by `DashboardApp._clear_text_widget`.

    Why this exists
    Keeps fallback-message logic small and directly testable.
    """
    widget.configure(state="normal")
    widget.delete("1.0", tk.END)
    if message.strip():
        tag = status_to_tag(level, default="empty")
        if tag == "info":
            tag = "empty"
        widget.insert(tk.END, message.strip() + "\n", (tag,))
    widget.configure(state="disabled")
