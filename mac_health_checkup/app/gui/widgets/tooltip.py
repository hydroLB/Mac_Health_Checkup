from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Callable, Optional

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/gui/widgets/tooltip.py"


@dataclass(frozen=True)
class TooltipTheme:
    """
    Summary
    Hold styling options for tooltips.

    Inputs
    bg: Background color.
    fg: Foreground color.
    font_family: Font family name.
    font_size: Font size.

    Outputs
    Immutable theme container.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `TooltipManager` to construct tooltip widgets consistently.

    Why this exists
    Keeps tooltip visuals configurable without hard-coding UI constants.
    """

    bg: str
    fg: str
    font_family: str
    font_size: int


class TooltipManager:
    """
    Summary
    Attach hover tooltips to Tk widgets.

    Inputs
    root: Tk root used to create tooltip windows.
    theme: TooltipTheme used for rendering.
    delay_ms: Hover delay before showing a tooltip.

    Outputs
    None. This class manages tooltip window lifecycle.

    Side effects
    Binds Tk events and creates/destroys a small Toplevel window.

    Error handling
    Raises RuntimeError with module and method context for unexpected Tk errors.

    Ties to other methods
    Used by `DashboardApp` to add hover help to labels and text widgets.

    Why this exists
    Tkinter has no built-in tooltip primitive; a small centralized implementation keeps behavior consistent.
    """

    def __init__(self, *, root: tk.Tk, theme: TooltipTheme, delay_ms: int = 400) -> None:
        """
        Summary
        Initialize the tooltip manager.

        Inputs
        root: Tk root.
        theme: TooltipTheme configuration.
        delay_ms: Delay before showing tooltips.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises RuntimeError when initialization receives invalid inputs.

        Ties to other methods
        Constructed by `DashboardApp`.

        Why this exists
        Centralizes tooltip configuration and event wiring.
        """
        try:
            if delay_ms < 0:
                raise ValueError("delay_ms must be non-negative")
            self._root = root
            self._theme = theme
            self._delay_ms = int(delay_ms)
            self._providers: dict[int, Callable[[tk.Event[tk.Misc]], Optional[str]]] = {}
            self._bound_widget_ids: set[int] = set()
            self._after_id: str | None = None
            self._tip: tk.Toplevel | None = None
            self._label: tk.Label | None = None
            self._active_widget_id: int | None = None
            self._last_text: str | None = None
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "TooltipManager.__init__", "Failed to init tooltips", exc)
            ) from exc

    def set_static(self, widget: tk.Widget, text: str) -> None:
        """
        Summary
        Attach or update a static tooltip for a widget.

        Inputs
        widget: Tk widget.
        text: Tooltip text.

        Outputs
        None.

        Side effects
        Binds hover events to the widget on first use.

        Error handling
        Raises RuntimeError for Tk failures.

        Ties to other methods
        Used by `DashboardApp` for labels and buttons.

        Why this exists
        Most UI elements have stable help text that does not depend on cursor position.
        """
        try:
            wid = id(widget)

            def _provider(_event: tk.Event[tk.Misc]) -> Optional[str]:
                value = (text or "").strip()
                return value if value else None

            self._providers[wid] = _provider
            self._bind_once(widget)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "TooltipManager.set_static", "Failed to set tooltip", exc)
            ) from exc

    def set_dynamic(self, widget: tk.Widget, provider: Callable[[tk.Event[tk.Misc]], Optional[str]]) -> None:
        """
        Summary
        Attach or update a dynamic tooltip provider for a widget.

        Inputs
        widget: Tk widget.
        provider: Callable that returns tooltip text for the current event, or None to hide.

        Outputs
        None.

        Side effects
        Binds hover/motion events to the widget on first use.

        Error handling
        Raises RuntimeError for Tk failures.

        Ties to other methods
        Used by `DashboardApp` for metrics and table text widgets.

        Why this exists
        Text widgets contain multiple logical items; tooltips should vary with cursor position.
        """
        try:
            self._providers[id(widget)] = provider
            self._bind_once(widget)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "TooltipManager.set_dynamic", "Failed to set tooltip", exc)
            ) from exc

    def hide(self) -> None:
        """
        Summary
        Hide the tooltip if visible.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Cancels scheduled show and destroys the tooltip window.

        Error handling
        None.

        Ties to other methods
        Called on leave events and when providers return None.

        Why this exists
        Ensures tooltips do not linger when the cursor leaves the widget.
        """
        self._cancel_scheduled()
        self._destroy_tip()

    def _bind_once(self, widget: tk.Widget) -> None:
        """
        Summary
        Bind tooltip events to a widget if not already bound.

        Inputs
        widget: Tk widget to bind.

        Outputs
        None.

        Side effects
        Registers Tk event handlers.

        Error handling
        Raises RuntimeError for Tk failures.

        Ties to other methods
        Called by `set_static` and `set_dynamic`.

        Why this exists
        Avoids stacking duplicate event bindings when tooltips are updated repeatedly.
        """
        try:
            wid = id(widget)
            if wid in self._bound_widget_ids:
                return
            self._bound_widget_ids.add(wid)
            widget.bind("<Enter>", self._on_enter, add="+")
            widget.bind("<Leave>", self._on_leave, add="+")
            widget.bind("<Motion>", self._on_motion, add="+")
            widget.bind("<ButtonPress>", self._on_leave, add="+")
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "TooltipManager._bind_once", "Failed to bind tooltip events", exc)
            ) from exc

    def _on_enter(self, event: tk.Event[tk.Misc]) -> None:
        try:
            self._active_widget_id = id(event.widget)
            self._schedule_show(event)
        except Exception:
            # Tooltips should never take down the UI; any unexpected errors are swallowed at this boundary.
            self.hide()

    def _on_motion(self, event: tk.Event[tk.Misc]) -> None:
        try:
            wid = id(event.widget)
            if self._active_widget_id != wid:
                self._active_widget_id = wid
            if self._tip is None:
                self._schedule_show(event)
                return
            text = self._tooltip_text(event)
            if not text:
                self.hide()
                return
            if text != self._last_text and self._label is not None:
                self._label.configure(text=text)
                self._last_text = text
            self._position_tip(event)
        except Exception:
            self.hide()

    def _on_leave(self, _event: tk.Event[tk.Misc]) -> None:
        self.hide()

    def _schedule_show(self, event: tk.Event[tk.Misc]) -> None:
        try:
            self._cancel_scheduled()
            if self._delay_ms == 0:
                self._show(event)
                return
            self._after_id = self._root.after(self._delay_ms, lambda: self._show(event))
        except Exception:
            self.hide()

    def _cancel_scheduled(self) -> None:
        if self._after_id is None:
            return
        try:
            self._root.after_cancel(self._after_id)
        except Exception:
            pass
        finally:
            self._after_id = None

    def _tooltip_text(self, event: tk.Event[tk.Misc]) -> Optional[str]:
        provider = self._providers.get(id(event.widget))
        if provider is None:
            return None
        try:
            return provider(event)
        except Exception:
            return None

    def _show(self, event: tk.Event[tk.Misc]) -> None:
        try:
            text = self._tooltip_text(event)
            if not text:
                return
            self._ensure_tip()
            if self._label is not None:
                self._label.configure(text=text)
            self._last_text = text
            self._position_tip(event)
            if self._tip is not None:
                self._tip.deiconify()
        except Exception:
            self.hide()

    def _ensure_tip(self) -> None:
        if self._tip is not None:
            return
        try:
            tip = tk.Toplevel(self._root)
            tip.withdraw()
            tip.overrideredirect(True)
            tip.attributes("-topmost", True)
            tip.configure(bg=self._theme.bg)
            label = tk.Label(
                tip,
                text="",
                bg=self._theme.bg,
                fg=self._theme.fg,
                justify="left",
                font=(self._theme.font_family, self._theme.font_size),
                padx=10,
                pady=6,
                wraplength=420,
            )
            label.pack()
            self._tip = tip
            self._label = label
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "TooltipManager._ensure_tip", "Failed to create tooltip window", exc
                )
            ) from exc

    def _position_tip(self, event: tk.Event[tk.Misc]) -> None:
        if self._tip is None:
            return
        try:
            x = int(event.x_root) + 14
            y = int(event.y_root) + 18
            self._tip.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _destroy_tip(self) -> None:
        if self._tip is None:
            self._label = None
            self._last_text = None
            return
        try:
            self._tip.destroy()
        except Exception:
            pass
        finally:
            self._tip = None
            self._label = None
            self._last_text = None
