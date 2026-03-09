from __future__ import annotations

import tkinter as tk

from mac_health_checkup.app.gui.dashboard.layout_mixin import _DashboardLayoutMixin
from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.app.gui.dashboard.queueing import SectionQueue
from mac_health_checkup.app.gui.dashboard.refresh_mixin import _DashboardRefreshMixin
from mac_health_checkup.app.gui.dashboard.render_mixin import _DashboardRenderMixin
from mac_health_checkup.app.gui.dashboard.sections import SECTION_HANDLERS, run_section
from mac_health_checkup.app.gui.dashboard.ui_helpers import (
    _blend_hex,
    _hex_to_rgb,
    _refresh_status_message,
    _SectionWidgets,
    _segment_at_char,
    _table_separator_length,
    _UiPalette,
    _UiTokens,
)
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.app.gui.widgets.controls import InteractiveButton
from mac_health_checkup.app.gui.widgets.scroll_container import ScrollContainer
from mac_health_checkup.app.gui.widgets.tooltip import TooltipManager, TooltipTheme
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/gui/app.py"

__all__ = [
    "DashboardApp",
    "_SectionWidgets",
    "_UiPalette",
    "_UiTokens",
    "_blend_hex",
    "_hex_to_rgb",
    "_refresh_status_message",
    "_segment_at_char",
    "_table_separator_length",
    "SECTION_HANDLERS",
    "run_section",
]


class DashboardApp(
    _DashboardRefreshMixin,
    _DashboardRenderMixin,
    _DashboardLayoutMixin,
    tk.Tk,
    SectionHost,
):
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
            self._table_base_heights: dict[str, int] = {}
            self._ui_palette = self._build_ui_palette()
            self._ui_tokens = self._build_ui_tokens()
            self._tooltips = TooltipManager(
                root=self,
                theme=TooltipTheme(
                    bg=self._color("surface.inset"),
                    fg=self._color("text.primary"),
                    font_family=self._cfg.fonts.family_default,
                    font_size=self._cfg.fonts.size_tooltip,
                ),
                delay_ms=350,
            )
            self._table_headers: dict[int, tuple[str, ...]] = {}

            self.title(self._cfg.ui.window_title)
            self.configure(bg=self._color("surface.app"))
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
