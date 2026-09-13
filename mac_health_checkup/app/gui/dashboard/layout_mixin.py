from __future__ import annotations

import platform
import subprocess  # nosec B404
import tkinter as tk
from typing import Callable, Literal, cast

from mac_health_checkup.app.gui.dashboard.layout_support import (
    bind_card_affordances,
    build_section_widgets,
    compute_field_wraplength,
    effective_table_height_for_width,
    resolve_card_border_style,
)
from mac_health_checkup.app.gui.dashboard.ui_helpers import (
    _blend_hex,
    _SectionWidgets,
    _UiPalette,
    _UiTokens,
)
from mac_health_checkup.app.gui.widgets.controls import ButtonTheme, InteractiveButton
from mac_health_checkup.app.gui.widgets.scroll_container import ScrollContainer
from mac_health_checkup.app.gui.widgets.tooltip import TooltipManager
from mac_health_checkup.core.config import Config
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/layout_mixin.py"


class _DashboardLayoutMixin:
    _cfg: Config
    _sections: dict[str, _SectionWidgets]
    _tooltips: TooltipManager
    _ui_palette: _UiPalette
    _ui_tokens: _UiTokens
    _status_var: tk.StringVar
    _status_label: tk.Label | None
    _next_refresh_var: tk.StringVar
    _next_refresh_label: tk.Label | None
    _refresh_button: InteractiveButton | None
    _refresh_in_progress: bool
    _scroll: ScrollContainer | None
    _wraplength_px: int | None
    _table_base_heights: dict[str, int]
    _cancel_scheduled_refresh: Callable[[], None]
    _refresh: Callable[[], None]

    def _detect_system_dark_mode(self) -> bool | None:
        """
        Summary
        Detect macOS appearance mode for `auto` theme selection.

        Inputs
        None.

        Outputs
        `True` when dark mode is active, `False` when light mode is active, and `None` when detection is
        unavailable.

        Side effects
        Executes one short-lived subprocess on macOS.

        Error handling
        Never raises. Returns `None` for detection errors.

        Ties to other methods
        Used by `_resolve_color_mode`.

        Why this exists
        `auto` mode should follow the operating system appearance when possible.
        """
        try:
            if platform.system() != "Darwin":
                return None
            completed = subprocess.run(  # nosec B603
                ["/usr/bin/defaults", "read", "-g", "AppleInterfaceStyle"],
                check=False,
                capture_output=True,
                text=True,
                timeout=1.0,
            )
            if completed.returncode != 0:
                return False
            return "dark" in str(completed.stdout).strip().lower()
        except (
            RuntimeError,
            ValueError,
            TypeError,
            OSError,
            subprocess.SubprocessError,
            TimeoutError,
        ):
            return None

    def _resolve_color_mode(self) -> str:
        """
        Summary
        Resolve the active color mode (`light` or `dark`) from config and OS settings.

        Inputs
        None.

        Outputs
        Resolved mode string.

        Side effects
        May query operating system appearance when config mode is `auto`.

        Error handling
        Raises `RuntimeError` with module and method context when mode resolution fails unexpectedly.

        Ties to other methods
        Used by `_build_ui_palette`.

        Why this exists
        Centralized mode resolution keeps behavior deterministic across the entire GUI.
        """
        try:
            ui_cfg = getattr(self._cfg, "ui", object())
            configured = str(getattr(ui_cfg, "color_mode", "auto")).strip().lower()
            if configured == "light":
                return "light"
            if configured == "dark":
                return "dark"
            detected = self._detect_system_dark_mode()
            if detected is True:
                return "dark"
            if detected is False:
                return "light"
            return "dark"
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._resolve_color_mode", "Failed to resolve color mode", exc
                )
            ) from exc

    def _color(self, role: str) -> str:
        """
        Summary
        Resolve a semantic color role through the central palette registry.

        Inputs
        role: Semantic color token such as `surface.app` or `status.error`.

        Outputs
        Hex color string.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when role lookup fails unexpectedly.

        Ties to other methods
        Used by layout, render, and interaction-state methods.

        Why this exists
        Widgets should rely on one color resolver instead of scattered defaults.
        """
        try:
            palette_obj = self.__dict__.get("_ui_palette")
            if isinstance(palette_obj, _UiPalette):
                resolved = palette_obj.colors.get(str(role))
                if resolved:
                    return str(resolved)
            colors_cfg = getattr(self._cfg, "colors", object())
            gui_cfg = getattr(self._cfg, "gui", object())
            fallback: dict[str, str] = {
                "surface.app": str(getattr(colors_cfg, "bg", "#12181f")),
                "surface.card": str(getattr(gui_cfg, "card_bg", "#1a212a")),
                "border.card": str(getattr(gui_cfg, "card_border", "#313d4b")),
                "border.card.hover": str(getattr(colors_cfg, "section", "#58a6ff")),
                "border.card.focus": str(getattr(colors_cfg, "section", "#58a6ff")),
                "text.primary": str(getattr(colors_cfg, "field", "#e3eaf4")),
                "text.secondary": str(getattr(colors_cfg, "label", "#a8b3c4")),
                "text.hint": str(getattr(colors_cfg, "label", "#a8b3c4")),
                "text.empty": str(getattr(colors_cfg, "label", "#a8b3c4")),
                "status.ready": str(getattr(colors_cfg, "label", "#a8b3c4")),
                "status.working": str(getattr(colors_cfg, "section", "#58a6ff")),
                "status.success": str(getattr(colors_cfg, "ok", "#2fbf71")),
                "status.warn": str(getattr(colors_cfg, "warn", "#d8a13a")),
                "status.error": str(getattr(colors_cfg, "bad", "#e05d5d")),
            }
            return fallback.get(str(role), str(getattr(colors_cfg, "field", "#e3eaf4")))
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._color", "Failed to resolve color role", exc)
            ) from exc

    def _button_theme(self, variant: str) -> ButtonTheme:
        """
        Summary
        Build a semantic button theme (`default`, `primary`, `toolbar`, or `segmented`) from color tokens.

        Inputs
        variant: Semantic button variant name.

        Outputs
        `ButtonTheme` for the requested variant.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when theme construction fails.

        Ties to other methods
        Used by `_build_layout`.

        Why this exists
        Button state maps should remain centralized and consistent across control types.
        """
        try:
            normalized = (variant or "").strip().lower()
            if normalized not in {"default", "primary", "toolbar", "segmented"}:
                normalized = "primary"
            prefix = f"button.{normalized}"
            return ButtonTheme(
                bg=self._color(f"{prefix}.bg"),
                fg=self._color(f"{prefix}.fg"),
                border=self._color(f"{prefix}.border"),
                hover_bg=self._color(f"{prefix}.hover"),
                active_bg=self._color(f"{prefix}.active"),
                disabled_bg=self._color(f"{prefix}.disabled.bg"),
                disabled_fg=self._color(f"{prefix}.disabled.fg"),
                disabled_border=self._color(f"{prefix}.disabled.border"),
                focus_border=self._color(f"{prefix}.focus"),
                selected_bg=self._color(f"{prefix}.selected"),
            )
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._button_theme", "Failed to build button theme", exc)
            ) from exc

    def _status_level_from_text(self, text: str) -> str:
        """
        Summary
        Infer semantic status level from user-facing status text.

        Inputs
        text: Status message text.

        Outputs
        Normalized status level.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when normalization fails unexpectedly.

        Ties to other methods
        Used by `_set_status` to map Ready/Working/Success/Error text automatically.

        Why this exists
        Status colors should stay aligned with displayed status wording.
        """
        try:
            normalized = str(text).strip().lower()
            if any(token in normalized for token in ("error", "failed", "failure")):
                return "error"
            if "warn" in normalized:
                return "warn"
            if any(token in normalized for token in ("working", "refreshing", "loading")):
                return "working"
            if any(token in normalized for token in ("success", "complete", "showing")):
                return "success"
            if any(token in normalized for token in ("ready", "waiting", "idle")):
                return "ready"
            return "ready"
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._status_level_from_text", "Failed to infer status level", exc
                )
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
            mode = self._resolve_color_mode()
            accent = self._cfg.colors.section
            success = self._cfg.colors.ok
            warn = self._cfg.colors.warn
            error = self._cfg.colors.bad
            if mode == "light":
                page_bg = "#eef2f7"
                card_bg = "#ffffff"
                card_border = "#d4dde8"
                text_primary = "#122033"
                text_secondary = "#43556c"
                text_muted = "#5d6f86"
                status_ready = "#586b84"
                status_working = _blend_hex(accent, "#2f6fb8", 0.24)
                button_primary_bg = _blend_hex(accent, page_bg, 0.16)
                button_primary_hover = _blend_hex(accent, page_bg, 0.24)
                button_primary_active = _blend_hex(accent, page_bg, 0.34)
                button_disabled_bg = _blend_hex(card_bg, page_bg, 0.54)
                button_disabled_fg = _blend_hex(text_secondary, page_bg, 0.40)
                button_disabled_border = _blend_hex(card_border, page_bg, 0.45)
            else:
                page_bg = self._cfg.colors.bg
                card_bg = self._cfg.gui.card_bg
                card_border = self._cfg.gui.card_border
                text_primary = self._cfg.colors.field
                text_secondary = self._cfg.colors.label
                text_muted = _blend_hex(self._cfg.colors.label, page_bg, 0.12)
                status_ready = self._cfg.colors.label
                status_working = accent
                button_primary_bg = _blend_hex(card_bg, accent, 0.18)
                button_primary_hover = _blend_hex(card_bg, accent, 0.28)
                button_primary_active = _blend_hex(card_bg, accent, 0.36)
                button_disabled_bg = _blend_hex(card_bg, page_bg, 0.34)
                button_disabled_fg = _blend_hex(self._cfg.colors.label, page_bg, 0.22)
                button_disabled_border = _blend_hex(card_border, page_bg, 0.26)
            card_border_hover = _blend_hex(card_border, accent, 0.35)
            card_border_focus = accent
            inset_bg = _blend_hex(card_bg, page_bg, 0.14)
            border_subtle = _blend_hex(card_border, page_bg, 0.18)
            table_select_active = _blend_hex(card_bg, accent, 0.30)
            table_select_inactive = _blend_hex(card_bg, card_border, 0.45)
            button_default_bg = _blend_hex(card_bg, accent, 0.12)
            button_default_hover = _blend_hex(card_bg, accent, 0.20)
            button_default_active = _blend_hex(card_bg, accent, 0.30)
            button_toolbar_bg = _blend_hex(card_bg, page_bg, 0.20)
            button_toolbar_hover = _blend_hex(button_toolbar_bg, accent, 0.12)
            button_toolbar_active = _blend_hex(button_toolbar_bg, accent, 0.20)
            button_segmented_bg = _blend_hex(card_bg, page_bg, 0.12)
            button_segmented_hover = _blend_hex(button_segmented_bg, accent, 0.14)
            button_segmented_active = _blend_hex(button_segmented_bg, accent, 0.22)
            scrollbar_track = _blend_hex(card_border, page_bg, 0.45)
            scrollbar_thumb = _blend_hex(card_border, accent, 0.22)
            colors: dict[str, str] = {
                "surface.app": page_bg,
                "surface.header": page_bg,
                "surface.card": card_bg,
                "surface.inset": inset_bg,
                "border.card": card_border,
                "border.card.hover": card_border_hover,
                "border.card.focus": card_border_focus,
                "border.subtle": border_subtle,
                "text.primary": text_primary,
                "text.secondary": text_secondary,
                "text.muted": text_muted,
                "text.section_header": text_primary,
                "text.form_label": text_secondary,
                "text.hint": text_secondary,
                "text.empty": text_muted,
                "text.status": status_ready,
                "status.ready": status_ready,
                "status.working": status_working,
                "status.success": success,
                "status.warn": warn,
                "status.error": error,
                "button.default.bg": button_default_bg,
                "button.default.fg": text_primary,
                "button.default.hover": button_default_hover,
                "button.default.active": button_default_active,
                "button.default.border": card_border,
                "button.default.focus": accent,
                "button.default.disabled.bg": button_disabled_bg,
                "button.default.disabled.fg": button_disabled_fg,
                "button.default.disabled.border": button_disabled_border,
                "button.default.selected": button_default_active,
                "button.primary.bg": button_primary_bg,
                "button.primary.fg": text_primary,
                "button.primary.hover": button_primary_hover,
                "button.primary.active": button_primary_active,
                "button.primary.border": card_border,
                "button.primary.focus": accent,
                "button.primary.disabled.bg": button_disabled_bg,
                "button.primary.disabled.fg": button_disabled_fg,
                "button.primary.disabled.border": button_disabled_border,
                "button.primary.selected": button_primary_active,
                "button.toolbar.bg": button_toolbar_bg,
                "button.toolbar.fg": text_secondary,
                "button.toolbar.hover": button_toolbar_hover,
                "button.toolbar.active": button_toolbar_active,
                "button.toolbar.border": border_subtle,
                "button.toolbar.focus": accent,
                "button.toolbar.disabled.bg": button_disabled_bg,
                "button.toolbar.disabled.fg": button_disabled_fg,
                "button.toolbar.disabled.border": button_disabled_border,
                "button.toolbar.selected": button_toolbar_active,
                "button.segmented.bg": button_segmented_bg,
                "button.segmented.fg": text_secondary,
                "button.segmented.hover": button_segmented_hover,
                "button.segmented.active": button_segmented_active,
                "button.segmented.border": border_subtle,
                "button.segmented.focus": accent,
                "button.segmented.disabled.bg": button_disabled_bg,
                "button.segmented.disabled.fg": button_disabled_fg,
                "button.segmented.disabled.border": button_disabled_border,
                "button.segmented.selected": button_segmented_active,
                "table.header": text_secondary,
                "table.separator": card_border,
                "table.selection.active": table_select_active,
                "table.selection.inactive": table_select_inactive,
                "scrollbar.track": scrollbar_track,
                "scrollbar.thumb": scrollbar_thumb,
                "scrollbar.arrow": _blend_hex(text_secondary, page_bg, 0.18),
            }
            return _UiPalette(
                mode=mode,
                colors=colors,
                page_bg=page_bg,
                card_bg=card_bg,
                card_border=card_border,
                card_border_hover=card_border_hover,
                card_border_focus=card_border_focus,
                text_primary=text_primary,
                text_secondary=text_secondary,
                text_muted=text_muted,
                status_info=status_ready,
                status_loading=status_working,
                status_success=success,
                status_warn=warn,
                status_error=error,
                button_bg=button_primary_bg,
                button_hover_bg=button_primary_hover,
                button_active_bg=button_primary_active,
                button_disabled_bg=button_disabled_bg,
                button_disabled_fg=button_disabled_fg,
                button_border=card_border,
                button_focus_border=accent,
            )
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._build_ui_palette", "Failed to derive UI palette", exc
                )
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
                action_button_pad_x=16,
                action_button_pad_y=8,
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
            normalized = (level or "").strip().lower()
            if normalized in {"working", "loading"}:
                return self._color("status.working")
            if normalized in {"success", "ok"}:
                return self._color("status.success")
            if normalized in {"warn", "warning"}:
                return self._color("status.warn")
            if normalized in {"error", "bad", "failed", "fail"}:
                return self._color("status.error")
            return self._color("status.ready")
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
            resolved_level = (level or "").strip().lower()
            if resolved_level in {"", "info", "default"}:
                resolved_level = self._status_level_from_text(text)
            self._status_var.set(str(text))
            if self._status_label is not None:
                self._status_label.configure(fg=self._status_color(resolved_level))
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
                    MODULE_PATH,
                    "DashboardApp._set_refresh_controls_busy",
                    "Failed to update refresh controls",
                    exc,
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
                format_error(
                    MODULE_PATH, "DashboardApp._set_next_refresh_hint", "Failed to set refresh hint", exc
                )
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
                format_error(
                    MODULE_PATH, "DashboardApp._set_section_feedback", "Failed to set section feedback", exc
                )
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
            bind_target = cast(tk.Misc, self)
            bind_target.bind_all("<F5>", self._on_refresh_shortcut)
            bind_target.bind_all("<KeyPress-r>", self._on_refresh_shortcut)
            bind_target.bind_all("<Home>", self._on_scroll_home)
            bind_target.bind_all("<End>", self._on_scroll_end)
            bind_target.bind_all("<Prior>", self._on_scroll_page_up)
            bind_target.bind_all("<Next>", self._on_scroll_page_down)
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
            cast(tk.Misc, self).after(0, self._refresh)
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
            self._set_status("Manual refresh requested...", level="working")
            cast(tk.Misc, self).after(0, self._refresh)
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._on_refresh_button", "Failed to trigger manual refresh", exc
                )
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
            root = tk.Frame(cast(tk.Misc, self), bg=self._color("surface.app"))
            root.pack(fill="both", expand=True)

            header = tk.Frame(root, bg=self._color("surface.header"))
            header.pack(
                fill="x",
                padx=self._ui_tokens.outer_pad_x,
                pady=(self._ui_tokens.header_pad_top, self._ui_tokens.header_pad_bottom),
            )

            title_row = tk.Frame(header, bg=self._color("surface.header"))
            title_row.pack(fill="x")

            title = self._new_label(
                parent=title_row,
                text=self._cfg.ui.window_title,
                bg=self._color("surface.header"),
                fg=self._color("text.section_header"),
                font_size=self._cfg.fonts.size_banner,
                font_weight=self._cfg.fonts.weight_bold,
            )
            title.pack(side="left", anchor="w")
            self._tooltips.set_static(
                title,
                "Mac Health Checkup dashboard. Hover over section titles, fields, metrics, and tables for details.",
            )

            right_controls = tk.Frame(title_row, bg=self._color("surface.header"))
            right_controls.pack(side="right", anchor="e")

            self._refresh_button = InteractiveButton(
                right_controls,
                text="Refresh now",
                command=self._on_refresh_button,
                theme=self._button_theme("primary"),
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
                bg=self._color("surface.header"),
                fg=self._color("text.hint"),
                font_size=self._cfg.fonts.size_tooltip,
                font_weight=self._cfg.fonts.weight_normal,
            )
            next_refresh.pack(anchor="w", pady=(self._ui_tokens.status_pad_top, 0))
            self._next_refresh_label = next_refresh
            self._set_next_refresh_hint(delay_ms=self._cfg.gui.auto_refresh_ms)

            status = self._new_label(
                parent=header,
                textvariable=self._status_var,
                bg=self._color("surface.header"),
                fg=self._color("text.status"),
                font_size=self._cfg.fonts.size_tooltip,
                font_weight=self._cfg.fonts.weight_normal,
            )
            status.pack(anchor="w", pady=(self._ui_tokens.status_pad_top, self._ui_tokens.status_pad_bottom))
            self._status_label = status
            self._set_status("Ready. Waiting for first refresh...", level="ready")
            self._tooltips.set_static(
                status,
                "Refresh status and diagnostic messages. Values update on a timer and may be cached briefly.",
            )

            separator = tk.Frame(root, bg=self._color("border.subtle"), height=1)
            separator.pack(fill="x", padx=self._ui_tokens.outer_pad_x, pady=(0, 10))

            self._scroll = ScrollContainer(
                root, bg=self._color("surface.app"), scroll_divisor=self._cfg.gui.drag_scroll_divisor
            )
            self._scroll.pack(fill="both", expand=True)

            cast(tk.Misc, self).bind("<Configure>", self._on_window_configure)
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
            section_widgets = build_section_widgets(
                parent=parent,
                key=key,
                title=title,
                subtitle=subtitle,
                cfg=self._cfg,
                ui_tokens=self._ui_tokens,
                color_fn=self._color,
                new_label_fn=self._new_label,
                set_tooltip_fn=self._tooltips.set_static,
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
            bind_card_affordances(
                key=key,
                section=section,
                card_state_handler_fn=lambda section_key, mode: self._card_state_handler(
                    key=section_key, mode=mode
                ),
                set_card_border_fn=self._set_card_border,
            )
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
            border, thickness = resolve_card_border_style(
                mode=mode,
                default_border=self._color("border.card"),
                hover_border=self._color("border.card.hover"),
                focus_border=self._color("border.card.focus"),
            )
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
            """
            Summary
            Execute `_handler` for its module-level responsibility.

            Inputs
            _event: `tk.Event[tk.Misc]` parameter from the function signature.

            Outputs
            None.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `mac_health_checkup/app/gui/app.py:_handler` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `mac_health_checkup/app/gui/app.py`.

            Why this exists
            Keeps `_handler` explicit, testable, and maintainable.
            """
            try:
                self._set_card_border(key, mode)
            except (tk.TclError, RuntimeError, ValueError, TypeError):
                return

        return _handler

    def _effective_table_height(self, *, key: str, base_height: int) -> int:
        """
        Summary
        Compute effective table row count for the current window size.

        Inputs
        key: Section key.
        base_height: Configured table height before responsive scaling.

        Outputs
        Effective table height in rows.

        Side effects
        None.

        Error handling
        Never raises. Returns `base_height` when window metrics are unavailable.

        Ties to other methods
        Used by `_create_text_widget` and `_on_window_configure`.

        Why this exists
        Smaller windows need denser table defaults to avoid clipping and excessive vertical scrolling.
        """
        try:
            _ = key
            window_obj = cast(tk.Misc, self)
            width_getter = getattr(window_obj, "winfo_width", None)
            if not callable(width_getter):
                return max(1, int(base_height))
            return effective_table_height_for_width(
                base_height=base_height,
                width=int(width_getter()),
                breakpoint=int(getattr(self._cfg.gui, "layout_breakpoint_width", 760)),
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
            return max(1, int(base_height))

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
            width = int(cast(tk.Misc, self).winfo_width())
            wrap = compute_field_wraplength(
                width=width,
                outer_pad=self._ui_tokens.outer_pad_x,
                min_wrap=self._ui_tokens.field_wrap_min_px,
                max_wrap=self._cfg.gui.content_wrap,
            )
            if self._wraplength_px == wrap:
                wrap_changed = False
            else:
                self._wraplength_px = wrap
                wrap_changed = True
            base_heights = self.__dict__.get("_table_base_heights", {})
            default_table_height = int(getattr(self._cfg.gui, "table_max_visible_rows", 3))
            for section in self._sections.values():
                if wrap_changed:
                    section.field.configure(wraplength=wrap)
            for key, section in self._sections.items():
                base_height = int(base_heights.get(key, default_table_height))
                effective_height = self._effective_table_height(key=key, base_height=base_height)
                if section.table is not None:
                    section.table.configure(height=effective_height)
                if section.metrics is not None:
                    section.metrics.configure(height=effective_height)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "DashboardApp._on_window_configure", "Failed to update wrap length", exc
                )
            ) from exc
