from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from typing import Literal, Protocol

from mac_health_checkup.app.gui.dashboard.ui_helpers import _SectionWidgets, _UiTokens
from mac_health_checkup.app.gui.widgets.controls import InlineStatusBadge, StatusTheme
from mac_health_checkup.app.help_text import section as section_help_text
from mac_health_checkup.core.config import Config

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/layout_support.py"


class _NewLabelFn(Protocol):
    """
    Summary
    Describe the host label-factory signature used by section-card assembly.

    Inputs
    None.

    Outputs
    Structural callable protocol.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `build_section_widgets`.

    Why this exists
    Strict mypy rejects `Callable[..., tk.Label]`, and the layout helper depends on keyword-only label arguments.
    """

    def __call__(
        self,
        *,
        parent: tk.Misc,
        text: str | None = ...,
        textvariable: tk.StringVar | None = ...,
        bg: str,
        fg: str,
        font_size: int,
        font_weight: str,
        wraplength: int | None = ...,
        justify: Literal["left", "center", "right"] = ...,
    ) -> tk.Label:
        """
        Summary
        Create a styled dashboard label.

        Inputs
        Matches `_DashboardLayoutMixin._new_label`.

        Outputs
        Configured `tk.Label`.

        Side effects
        Creates a Tk widget on the host.

        Error handling
        Implementations may raise Tk or config errors.

        Ties to other methods
        Used by `build_section_widgets`.

        Why this exists
        The helper needs the precise host callback shape without introducing `Any`.
        """


def build_section_widgets(
    *,
    parent: tk.Frame,
    key: str,
    title: str,
    subtitle: str,
    cfg: Config,
    ui_tokens: _UiTokens,
    color_fn: Callable[[str], str],
    new_label_fn: _NewLabelFn,
    set_tooltip_fn: Callable[[tk.Widget, str], None],
) -> _SectionWidgets:
    """
    Summary
    Create the widget bundle for one dashboard section card.

    Inputs
    parent: Parent frame receiving the section card.
    key: Section key used for tooltip help text.
    title: Section title text.
    subtitle: Section subtitle text.
    cfg: Loaded dashboard config.
    ui_tokens: Shared layout spacing and feedback tokens.
    color_fn: Host semantic color resolver.
    new_label_fn: Host label factory.
    set_tooltip_fn: Host tooltip registration callback.

    Outputs
    `_SectionWidgets` bundle for the new section card.

    Side effects
    Creates and packs Tk widgets.

    Error handling
    Propagates Tk and config errors to the caller.

    Ties to other methods
    Used by `_DashboardLayoutMixin._build_section_card`.

    Why this exists
    Section-card assembly is a cohesive unit and does not need to stay buried inside the larger layout coordinator.
    """
    card = tk.Frame(
        parent,
        bg=color_fn("surface.card"),
        highlightbackground=color_fn("border.card"),
        highlightthickness=1,
        takefocus=0,
    )
    card.pack(fill="x", padx=ui_tokens.outer_pad_x, pady=cfg.gui.section_pady)

    help_text = section_help_text(key)

    title_label = new_label_fn(
        parent=card,
        text=title,
        bg=color_fn("surface.card"),
        fg=color_fn("text.section_header"),
        font_size=cfg.fonts.size_section,
        font_weight=cfg.fonts.weight_bold,
    )
    title_label.pack(anchor="w", padx=ui_tokens.card_inner_pad_x, pady=(ui_tokens.card_inner_pad_y, 0))
    set_tooltip_fn(title_label, help_text)

    subtitle_label = new_label_fn(
        parent=card,
        text=subtitle,
        bg=color_fn("surface.card"),
        fg=color_fn("text.form_label"),
        font_size=cfg.fonts.size_field,
        font_weight=cfg.fonts.weight_normal,
    )
    subtitle_label.pack(
        anchor="w",
        padx=ui_tokens.card_inner_pad_x,
        pady=(2, ui_tokens.section_feedback_pad_bottom),
    )
    set_tooltip_fn(subtitle_label, help_text)

    feedback_label = InlineStatusBadge(
        card,
        bg=color_fn("surface.card"),
        theme=StatusTheme(
            info_fg=color_fn("status.ready"),
            loading_fg=color_fn("status.working"),
            success_fg=color_fn("status.success"),
            warn_fg=color_fn("status.warn"),
            error_fg=color_fn("status.error"),
        ),
        font_family=cfg.fonts.family_default,
        font_size=cfg.fonts.size_tooltip,
        font_weight=cfg.fonts.weight_normal,
    )
    feedback_label.pack(
        anchor="w",
        padx=ui_tokens.card_inner_pad_x,
        pady=(ui_tokens.section_feedback_pad_top, 0),
    )

    field_label = new_label_fn(
        parent=card,
        text="Waiting for section data...",
        bg=color_fn("surface.card"),
        fg=color_fn("text.empty"),
        font_size=cfg.fonts.size_field,
        font_weight=cfg.fonts.weight_normal,
        wraplength=cfg.gui.content_wrap,
    )
    field_label.configure(anchor="w", takefocus=1)
    field_label.pack(
        anchor="w",
        fill="x",
        padx=ui_tokens.card_inner_pad_x,
        pady=(ui_tokens.section_feedback_pad_bottom, ui_tokens.card_inner_pad_y),
    )
    set_tooltip_fn(field_label, help_text)

    return _SectionWidgets(
        frame=card,
        title=title_label,
        subtitle=subtitle_label,
        field=field_label,
        feedback=feedback_label,
        card=card,
    )


def bind_card_affordances(
    *,
    key: str,
    section: _SectionWidgets,
    card_state_handler_fn: Callable[[str, str], Callable[[tk.Event[tk.Misc]], None]],
    set_card_border_fn: Callable[[str, str], None],
) -> None:
    """
    Summary
    Bind hover and focus affordances across the widgets that make up one dashboard card.

    Inputs
    key: Section key.
    section: Section widget bundle.
    card_state_handler_fn: Host callback factory for Tk event handlers.
    set_card_border_fn: Host border-style applier.

    Outputs
    None.

    Side effects
    Registers Tk event bindings on the section widgets and resets the card border to the normal state.

    Error handling
    Propagates widget binding errors to the caller.

    Ties to other methods
    Used by `_DashboardLayoutMixin._bind_card_affordances`.

    Why this exists
    Affordance binding is deterministic layout wiring and should be directly testable outside the mixin host.
    """
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
    deduped_targets: list[tk.Widget] = list(dict.fromkeys(bind_targets))
    for target in deduped_targets:
        target.bind("<Enter>", card_state_handler_fn(key, "hover"), add="+")
        target.bind("<Leave>", card_state_handler_fn(key, "normal"), add="+")
        target.bind("<FocusIn>", card_state_handler_fn(key, "focus"), add="+")
        target.bind("<FocusOut>", card_state_handler_fn(key, "normal"), add="+")
    set_card_border_fn(key, "normal")


def resolve_card_border_style(
    *,
    mode: str,
    default_border: str,
    hover_border: str,
    focus_border: str,
) -> tuple[str, int]:
    """
    Summary
    Resolve the border color and thickness for one card interaction state.

    Inputs
    mode: Requested interaction state.
    default_border: Border color for the resting state.
    hover_border: Border color for the hover state.
    focus_border: Border color for the focus state.

    Outputs
    `(border_color, highlight_thickness)` tuple.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `_DashboardLayoutMixin._set_card_border`.

    Why this exists
    Border-state selection is pure logic and should not stay mixed with widget mutation.
    """
    normalized = (mode or "").strip().lower()
    if normalized == "focus":
        return (focus_border, 2)
    if normalized == "hover":
        return (hover_border, 1)
    return (default_border, 1)


def effective_table_height_for_width(*, width: int, base_height: int, breakpoint: int) -> int:
    """
    Summary
    Compute the effective table height for a given window width.

    Inputs
    width: Current window width in pixels.
    base_height: Configured base row count.
    breakpoint: Compact-layout breakpoint in pixels.

    Outputs
    Effective row count.

    Side effects
    None.

    Error handling
    Never raises; invalid numeric inputs are normalized defensively.

    Ties to other methods
    Used by `_DashboardLayoutMixin._effective_table_height`.

    Why this exists
    Responsive table-height math is deterministic and easier to validate as a standalone helper.
    """
    resolved_base = max(1, int(base_height))
    resolved_width = int(width)
    resolved_breakpoint = int(breakpoint)
    if resolved_width <= 0:
        return resolved_base
    if resolved_width <= resolved_breakpoint - 120:
        return max(2, resolved_base - 2)
    if resolved_width <= resolved_breakpoint:
        return max(2, resolved_base - 1)
    return resolved_base


def compute_field_wraplength(*, width: int, outer_pad: int, min_wrap: int, max_wrap: int) -> int:
    """
    Summary
    Compute the effective field wrap length for a given window width.

    Inputs
    width: Current window width in pixels.
    outer_pad: Horizontal outer padding in pixels.
    min_wrap: Minimum readable wrap length in pixels.
    max_wrap: Maximum configured wrap length in pixels.

    Outputs
    Effective wrap length in pixels.

    Side effects
    None.

    Error handling
    Never raises; invalid numeric inputs are normalized defensively.

    Ties to other methods
    Used by `_DashboardLayoutMixin._on_window_configure`.

    Why this exists
    Responsive wrap-length math should be easy to test without instantiating a Tk root.
    """
    resolved_width = int(width)
    resolved_outer_pad = max(0, int(outer_pad))
    resolved_min_wrap = max(1, int(min_wrap))
    resolved_max_wrap = max(1, int(max_wrap))
    return max(
        resolved_min_wrap,
        min(resolved_max_wrap, resolved_width - (resolved_outer_pad * 2) - 72),
    )
