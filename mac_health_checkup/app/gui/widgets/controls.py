from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Literal

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/gui/widgets/controls.py"


@dataclass(frozen=True)
class ButtonTheme:
    """
    Summary
    Hold styling tokens for an interactive button.

    Inputs
    Base and interaction colors for normal, hover, active, focus, and disabled states.

    Outputs
    Immutable theme container.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Consumed by `InteractiveButton`.

    Why this exists
    Keeps button styling centralized and easy to restyle.
    """

    bg: str
    fg: str
    border: str
    hover_bg: str
    active_bg: str
    disabled_bg: str
    disabled_fg: str
    focus_border: str


@dataclass(frozen=True)
class StatusTheme:
    """
    Summary
    Hold color tokens for inline status messaging.

    Inputs
    Foreground colors for info, loading, success, warn, and error states.

    Outputs
    Immutable theme container.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Consumed by `InlineStatusBadge`.

    Why this exists
    Centralized state colors keep status messaging consistent across the UI.
    """

    info_fg: str
    loading_fg: str
    success_fg: str
    warn_fg: str
    error_fg: str


class InteractiveButton(tk.Button):
    """
    Summary
    Provide a reusable Tk button with consistent hover, focus, active, disabled, and loading states.

    Inputs
    Parent widget, display text, callback, theme tokens, typography, and paddings.

    Outputs
    Configured button widget.

    Side effects
    Binds pointer and focus events to maintain visual interaction states.

    Error handling
    Raises `RuntimeError` with module and method context when initialization or state updates fail.

    Ties to other methods
    Used by `DashboardApp` for primary header actions.

    Why this exists
    Button state behavior should be reusable and not duplicated across screens.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        text: str,
        command: Callable[[], None],
        theme: ButtonTheme,
        font_family: str,
        font_size: int,
        font_weight: str,
        pad_x: int,
        pad_y: int,
        loading_text: str = "Loading...",
    ) -> None:
        """
        Summary
        Initialize the interactive button and bind state events.

        Inputs
        parent: Parent widget.
        text: Default button label.
        command: Callback invoked when activated.
        theme: Interaction color tokens.
        font_family: Font family for label text.
        font_size: Font size for label text.
        font_weight: Font weight for label text.
        pad_x: Horizontal padding.
        pad_y: Vertical padding.
        loading_text: Label shown while loading.

        Outputs
        None.

        Side effects
        Creates a Tk button and installs hover, press, and focus event handlers.

        Error handling
        Raises `RuntimeError` with module and method context when setup fails.

        Ties to other methods
        Uses `_sync_style` and event handlers to apply interaction visuals.

        Why this exists
        Encapsulates interaction state behavior in one place.
        """
        try:
            self._theme = theme
            self._default_text = str(text)
            self._loading_text = str(loading_text)
            self._is_hovered = False
            self._is_pressed = False
            self._is_focused = False
            self._is_loading = False
            self._is_enabled = True
            super().__init__(
                parent,
                text=self._default_text,
                command=command,
                bg=theme.bg,
                fg=theme.fg,
                activebackground=theme.active_bg,
                activeforeground=theme.fg,
                disabledforeground=theme.disabled_fg,
                relief="flat",
                borderwidth=0,
                highlightthickness=1,
                highlightbackground=theme.border,
                highlightcolor=theme.focus_border,
                cursor="hand2",
                takefocus=1,
                font=(font_family, int(font_size), font_weight),
                padx=int(pad_x),
                pady=int(pad_y),
            )
            self.bind("<Enter>", self._on_enter, add="+")
            self.bind("<Leave>", self._on_leave, add="+")
            self.bind("<ButtonPress-1>", self._on_press, add="+")
            self.bind("<ButtonRelease-1>", self._on_release, add="+")
            self.bind("<FocusIn>", self._on_focus_in, add="+")
            self.bind("<FocusOut>", self._on_focus_out, add="+")
            self._sync_style()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "InteractiveButton.__init__", "Failed to initialize interactive button", exc
                )
            ) from exc

    def set_enabled(self, enabled: bool) -> None:
        """
        Summary
        Enable or disable the button interaction state.

        Inputs
        enabled: True to enable interactions; False to disable.

        Outputs
        None.

        Side effects
        Updates button state and visual styling.

        Error handling
        Raises `RuntimeError` with module and method context when updates fail.

        Ties to other methods
        Works with `set_loading` and `_sync_style`.

        Why this exists
        Callers need explicit control over when actions are available.
        """
        try:
            self._is_enabled = bool(enabled)
            self._sync_style()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "InteractiveButton.set_enabled", "Failed to set enabled state", exc)
            ) from exc

    def set_loading(self, loading: bool) -> None:
        """
        Summary
        Toggle loading mode and update label text.

        Inputs
        loading: True to show loading mode; False to restore normal mode.

        Outputs
        None.

        Side effects
        Updates button text, cursor, and disables interaction while loading.

        Error handling
        Raises `RuntimeError` with module and method context when updates fail.

        Ties to other methods
        Uses `_sync_style`.

        Why this exists
        Prevents duplicate action triggers and gives immediate feedback during work.
        """
        try:
            self._is_loading = bool(loading)
            self._sync_style()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "InteractiveButton.set_loading", "Failed to set loading state", exc)
            ) from exc

    def _on_enter(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Mark button as hovered.

        Inputs
        _event: Tk pointer event.

        Outputs
        None.

        Side effects
        Updates visual style.

        Error handling
        Swallows transient Tk errors to avoid disrupting UI events.

        Ties to other methods
        Calls `_sync_style`.

        Why this exists
        Hover feedback improves click discoverability.
        """
        try:
            self._is_hovered = True
            self._sync_style()
        except Exception:
            return

    def _on_leave(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Clear hover and pressed state when pointer leaves the button.

        Inputs
        _event: Tk pointer event.

        Outputs
        None.

        Side effects
        Updates visual style.

        Error handling
        Swallows transient Tk errors to avoid disrupting UI events.

        Ties to other methods
        Calls `_sync_style`.

        Why this exists
        Prevents stale visual states after pointer exits.
        """
        try:
            self._is_hovered = False
            self._is_pressed = False
            self._sync_style()
        except Exception:
            return

    def _on_press(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Mark button as pressed.

        Inputs
        _event: Tk pointer event.

        Outputs
        None.

        Side effects
        Updates visual style.

        Error handling
        Swallows transient Tk errors to avoid disrupting UI events.

        Ties to other methods
        Calls `_sync_style`.

        Why this exists
        Active state feedback confirms pointer interaction.
        """
        try:
            self._is_pressed = True
            self._sync_style()
        except Exception:
            return

    def _on_release(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Clear pressed state when pointer is released.

        Inputs
        _event: Tk pointer event.

        Outputs
        None.

        Side effects
        Updates visual style.

        Error handling
        Swallows transient Tk errors to avoid disrupting UI events.

        Ties to other methods
        Calls `_sync_style`.

        Why this exists
        Keeps active styling in sync with click lifecycle.
        """
        try:
            self._is_pressed = False
            self._sync_style()
        except Exception:
            return

    def _on_focus_in(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Apply focused visual styling.

        Inputs
        _event: Tk focus event.

        Outputs
        None.

        Side effects
        Updates visual style.

        Error handling
        Swallows transient Tk errors to avoid disrupting UI events.

        Ties to other methods
        Calls `_sync_style`.

        Why this exists
        Keyboard users need visible focus indication.
        """
        try:
            self._is_focused = True
            self._sync_style()
        except Exception:
            return

    def _on_focus_out(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Clear focused visual styling.

        Inputs
        _event: Tk focus event.

        Outputs
        None.

        Side effects
        Updates visual style.

        Error handling
        Swallows transient Tk errors to avoid disrupting UI events.

        Ties to other methods
        Calls `_sync_style`.

        Why this exists
        Focus styling should reflect current keyboard target.
        """
        try:
            self._is_focused = False
            self._sync_style()
        except Exception:
            return

    def _sync_style(self) -> None:
        """
        Summary
        Apply visual styling for the current interaction state.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Updates Tk button colors, border, text, and state.

        Error handling
        Raises `RuntimeError` with module and method context when styling fails.

        Ties to other methods
        Used by all interaction state handlers and explicit state setters.

        Why this exists
        A single render path keeps state transitions predictable and easy to maintain.
        """
        try:
            interactive = self._is_enabled and not self._is_loading
            state: Literal["normal", "disabled"]
            if not interactive:
                bg = self._theme.disabled_bg
                fg = self._theme.disabled_fg
                cursor = "watch" if self._is_loading else "arrow"
                state = "disabled"
            elif self._is_pressed:
                bg = self._theme.active_bg
                fg = self._theme.fg
                cursor = "hand2"
                state = "normal"
            elif self._is_hovered:
                bg = self._theme.hover_bg
                fg = self._theme.fg
                cursor = "hand2"
                state = "normal"
            else:
                bg = self._theme.bg
                fg = self._theme.fg
                cursor = "hand2"
                state = "normal"

            border = self._theme.focus_border if self._is_focused else self._theme.border
            thickness = 2 if self._is_focused else 1
            label = self._loading_text if self._is_loading else self._default_text
            self.configure(
                state=state,
                text=label,
                bg=bg,
                fg=fg,
                activebackground=self._theme.active_bg,
                activeforeground=self._theme.fg,
                disabledforeground=self._theme.disabled_fg,
                cursor=cursor,
                highlightbackground=border,
                highlightcolor=border,
                highlightthickness=thickness,
            )
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "InteractiveButton._sync_style", "Failed to sync button style", exc)
            ) from exc


class InlineStatusBadge(tk.Label):
    """
    Summary
    Provide a reusable inline status label with consistent state colors.

    Inputs
    Parent widget, static background color, theme, and typography settings.

    Outputs
    Configured label widget.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when setup or updates fail.

    Ties to other methods
    Used by `DashboardApp` header and section cards for state feedback.

    Why this exists
    Inline status messaging should use one shared style system instead of ad hoc label configuration.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        bg: str,
        theme: StatusTheme,
        font_family: str,
        font_size: int,
        font_weight: str,
    ) -> None:
        """
        Summary
        Initialize the inline status badge.

        Inputs
        parent: Parent widget.
        bg: Background color.
        theme: Status color theme.
        font_family: Font family.
        font_size: Font size.
        font_weight: Font weight.

        Outputs
        None.

        Side effects
        Creates a Tk label widget.

        Error handling
        Raises `RuntimeError` with module and method context when setup fails.

        Ties to other methods
        Used by `set_message`.

        Why this exists
        Keeps status rendering simple and reusable.
        """
        try:
            self._theme = theme
            super().__init__(
                parent,
                bg=bg,
                fg=theme.info_fg,
                text="",
                anchor="w",
                justify="left",
                font=(font_family, int(font_size), font_weight),
            )
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "InlineStatusBadge.__init__", "Failed to initialize status badge", exc
                )
            ) from exc

    def set_message(self, text: str, *, level: str = "info") -> None:
        """
        Summary
        Set badge text and state color.

        Inputs
        text: Message text.
        level: Status level such as info, loading, success, warn, or error.

        Outputs
        None.

        Side effects
        Updates label text and foreground color.

        Error handling
        Raises `RuntimeError` with module and method context when updates fail.

        Ties to other methods
        Called by the dashboard refresh and rendering flows.

        Why this exists
        Keeps state communication consistent and readable.
        """
        try:
            normalized = (level or "").strip().lower()
            if normalized == "loading":
                fg = self._theme.loading_fg
            elif normalized == "success":
                fg = self._theme.success_fg
            elif normalized == "warn":
                fg = self._theme.warn_fg
            elif normalized == "error":
                fg = self._theme.error_fg
            else:
                fg = self._theme.info_fg
            self.configure(text=str(text).strip(), fg=fg)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "InlineStatusBadge.set_message", "Failed to set status message", exc)
            ) from exc
