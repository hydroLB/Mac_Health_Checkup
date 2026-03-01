from __future__ import annotations

import tkinter as tk

from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/gui/widgets/scroll_container.py"


class ScrollContainer(tk.Frame):
    """
    Summary
    Provide a vertically scrollable container for Tk widgets.

    Inputs
    parent: Tk widget that owns this container.
    bg: Background color for the canvas and inner frame.
    scroll_divisor: Divisor applied to mouse wheel delta for smooth scrolling.

    Outputs
    A `tk.Frame` with `content` as the scrollable child frame.

    Side effects
    Binds mouse wheel events while the cursor is inside the container.

    Error handling
    Raises `RuntimeError` with module and method context when Tk bindings fail.

    Ties to other methods
    Used by `DashboardApp` to host section cards in a single scroll view.

    Why this exists
    Tkinter does not provide a native scrollable frame; this encapsulates the standard canvas pattern.
    """

    def __init__(self, parent: tk.Misc, *, bg: str, scroll_divisor: int) -> None:
        """
        Summary
        Initialize the scroll container and its internal canvas.

        Inputs
        parent: Parent widget.
        bg: Background color.
        scroll_divisor: Mouse wheel divisor for scrolling.

        Outputs
        None.

        Side effects
        Creates a Canvas, Scrollbar, and an inner `content` frame; installs bindings.

        Error handling
        Raises `RuntimeError` if widget creation or event binding fails.

        Ties to other methods
        Creates the internal bindings used by `_on_mousewheel`, `_on_content_configure`, and `_on_canvas_configure`.

        Why this exists
        Centralizes scroll behavior so the main app can focus on layout and rendering.
        """
        try:
            super().__init__(parent, bg=bg)
            self._bg = bg
            self._scroll_divisor = max(1, int(scroll_divisor))

            self._canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
            self._scrollbar = tk.Scrollbar(self, orient="vertical", command=self._canvas.yview)
            self._canvas.configure(yscrollcommand=self._scrollbar.set)

            self._scrollbar.pack(side="right", fill="y")
            self._canvas.pack(side="left", fill="both", expand=True)

            self.content = tk.Frame(self._canvas, bg=bg)
            self._content_window = self._canvas.create_window((0, 0), window=self.content, anchor="nw")

            self.content.bind("<Configure>", self._on_content_configure)
            self._canvas.bind("<Configure>", self._on_canvas_configure)
            self._canvas.bind("<Enter>", self._bind_mousewheel)
            self._canvas.bind("<Leave>", self._unbind_mousewheel)
            self.content.bind("<Enter>", self._bind_mousewheel)
            self.content.bind("<Leave>", self._unbind_mousewheel)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "ScrollContainer.__init__", "Failed to initialize scroll container", exc
                )
            ) from exc

    def scroll_to_top(self) -> None:
        """
        Summary
        Scroll the container to the top.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Moves the canvas viewport.

        Error handling
        Raises `RuntimeError` if the canvas cannot scroll.

        Ties to other methods
        Useful for future navigation controls (sidebar or search) to reset the view.

        Why this exists
        Provides a single safe entrypoint to reset scroll position.
        """
        try:
            self._canvas.yview_moveto(0.0)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ScrollContainer.scroll_to_top", "Failed to scroll to top", exc)
            ) from exc

    def scroll_to_bottom(self) -> None:
        """
        Summary
        Scroll the container to the bottom.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Moves the canvas viewport.

        Error handling
        Raises `RuntimeError` if the canvas cannot scroll.

        Ties to other methods
        Used by keyboard navigation shortcuts in the dashboard.

        Why this exists
        Supports efficient navigation for long dashboards without requiring drag gestures.
        """
        try:
            self._canvas.yview_moveto(1.0)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "ScrollContainer.scroll_to_bottom", "Failed to scroll to bottom", exc
                )
            ) from exc

    def scroll_pages(self, pages: int) -> None:
        """
        Summary
        Scroll by a whole number of pages.

        Inputs
        pages: Positive values scroll down, negative values scroll up.

        Outputs
        None.

        Side effects
        Moves the canvas viewport in page increments.

        Error handling
        Raises `RuntimeError` when the input is invalid or scrolling fails.

        Ties to other methods
        Used by keyboard page navigation handlers in the dashboard.

        Why this exists
        Page stepping gives predictable navigation compared with small unit scrolling.
        """
        try:
            steps = int(pages)
            if steps == 0:
                return
            self._canvas.yview_scroll(steps, "pages")
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ScrollContainer.scroll_pages", "Failed to scroll pages", exc)
            ) from exc

    def _on_content_configure(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Update the canvas scroll region when content size changes.

        Inputs
        _event: Tk event (unused).

        Outputs
        None.

        Side effects
        Updates the canvas scroll region.

        Error handling
        Raises `RuntimeError` if the scroll region cannot be updated.

        Ties to other methods
        Triggered by the `content` frame `<Configure>` binding.

        Why this exists
        Keeps the scroll region accurate as cards are added or resized.
        """
        try:
            self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "ScrollContainer._on_content_configure",
                    "Failed to update scroll region",
                    exc,
                )
            ) from exc

    def _on_canvas_configure(self, event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Resize the embedded content frame to match the canvas width.

        Inputs
        event: Tk event containing the new canvas width.

        Outputs
        None.

        Side effects
        Updates the canvas window item width.

        Error handling
        Raises `RuntimeError` if the embedded window cannot be resized.

        Ties to other methods
        Triggered by the canvas `<Configure>` binding and impacts text wrapping and card layouts.

        Why this exists
        Ensures section cards expand to full width so the UI reads like a native scroll view.
        """
        try:
            width = int(getattr(event, "width", 0))
            if width > 0:
                self._canvas.itemconfigure(self._content_window, width=width)
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "ScrollContainer._on_canvas_configure",
                    "Failed to resize content window",
                    exc,
                )
            ) from exc

    def _bind_mousewheel(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Bind global mouse wheel events for scrolling while hovered.

        Inputs
        _event: Tk event (unused).

        Outputs
        None.

        Side effects
        Installs `bind_all` handlers for mouse wheel events.

        Error handling
        Raises `RuntimeError` if bindings cannot be installed.

        Ties to other methods
        Routes events to `_on_mousewheel` and `_on_mousewheel_linux`.

        Why this exists
        Tk sends mouse wheel events to the widget under the cursor; binding globally while hovered is reliable.
        """
        try:
            self._canvas.bind_all("<MouseWheel>", self._on_mousewheel)
            self._canvas.bind_all("<Button-4>", self._on_mousewheel_linux)
            self._canvas.bind_all("<Button-5>", self._on_mousewheel_linux)
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "ScrollContainer._bind_mousewheel", "Failed to bind mouse wheel", exc
                )
            ) from exc

    def _unbind_mousewheel(self, _event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Remove global mouse wheel bindings when the cursor leaves the container.

        Inputs
        _event: Tk event (unused).

        Outputs
        None.

        Side effects
        Removes `bind_all` mouse wheel handlers.

        Error handling
        Raises `RuntimeError` if bindings cannot be removed.

        Ties to other methods
        Installed by `_bind_mousewheel`.

        Why this exists
        Prevents scroll events from affecting the container when the cursor is elsewhere.
        """
        try:
            self._canvas.unbind_all("<MouseWheel>")
            self._canvas.unbind_all("<Button-4>")
            self._canvas.unbind_all("<Button-5>")
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "ScrollContainer._unbind_mousewheel", "Failed to unbind mouse wheel", exc
                )
            ) from exc

    def _on_mousewheel(self, event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Scroll the canvas in response to a mouse wheel event.

        Inputs
        event: Tk event with `delta` values.

        Outputs
        None.

        Side effects
        Adjusts the canvas vertical view.

        Error handling
        Raises `RuntimeError` if scrolling fails or event data is invalid.

        Ties to other methods
        Called via bindings installed by `_bind_mousewheel`.

        Why this exists
        Provides consistent trackpad and wheel scrolling across macOS and Windows.
        """
        try:
            delta = int(getattr(event, "delta", 0))
            if delta == 0:
                return
            steps = int(-delta / self._scroll_divisor)
            if steps == 0:
                steps = -1 if delta > 0 else 1
            self._canvas.yview_scroll(steps, "units")
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ScrollContainer._on_mousewheel", "Failed to scroll", exc)
            ) from exc

    def _on_mousewheel_linux(self, event: tk.Event[tk.Misc]) -> None:
        """
        Summary
        Scroll the canvas for Linux button-based wheel events.

        Inputs
        event: Tk event with `num` indicating direction.

        Outputs
        None.

        Side effects
        Adjusts the canvas vertical view.

        Error handling
        Raises `RuntimeError` if scrolling fails.

        Ties to other methods
        Called via bindings installed by `_bind_mousewheel`.

        Why this exists
        Some Tk builds report wheel scrolling as Button-4 and Button-5 events.
        """
        try:
            num = int(getattr(event, "num", 0))
            if num == 4:
                self._canvas.yview_scroll(-1, "units")
            elif num == 5:
                self._canvas.yview_scroll(1, "units")
        except (tk.TclError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ScrollContainer._on_mousewheel_linux", "Failed to scroll", exc)
            ) from exc
