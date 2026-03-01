from __future__ import annotations

import sys
import time
import tkinter as tk
from datetime import datetime
from typing import Callable, Protocol, cast

from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.app.gui.dashboard.queueing import SectionQueue
from mac_health_checkup.app.gui.dashboard.sections import (
    SECTION_HANDLERS as DEFAULT_SECTION_HANDLERS,
)
from mac_health_checkup.app.gui.dashboard.sections import run_section as default_run_section
from mac_health_checkup.app.gui.dashboard.ui_helpers import _refresh_status_message
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import Config
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils.error_boundary import ErrorBoundary, map_boundary_exception

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/refresh_mixin.py"


class _SetNextRefreshHintFn(Protocol):
    def __call__(self, *, delay_ms: int) -> None:
        """
        Summary
        Update the next refresh hint in the dashboard header.

        Inputs
        delay_ms: Delay until next refresh in milliseconds.

        Outputs
        None.

        Side effects
        Updates UI hint text on the host.

        Error handling
        Implementations raise contextual host-specific runtime errors when updates fail.

        Ties to other methods
        Used by refresh scheduling paths.

        Why this exists
        Provides a typed callable contract for cross-mixin scheduling feedback.
        """
        ...


class _SetStatusFn(Protocol):
    def __call__(self, text: str, *, level: str = "info") -> None:
        """
        Summary
        Update global status text and severity level in the dashboard header.

        Inputs
        text: Status message text.
        level: Status severity level.

        Outputs
        None.

        Side effects
        Updates status variables and visual styling on the host.

        Error handling
        Implementations raise contextual host-specific runtime errors when updates fail.

        Ties to other methods
        Used throughout refresh start, success, and failure flows.

        Why this exists
        Provides a typed callable contract for global refresh feedback.
        """
        ...


class _SetSectionFeedbackFn(Protocol):
    def __call__(self, key: str, message: str, *, level: str) -> None:
        """
        Summary
        Update inline feedback text for a specific section card.

        Inputs
        key: Section key.
        message: Feedback text.
        level: Feedback severity level.

        Outputs
        None.

        Side effects
        Updates section feedback state on the host.

        Error handling
        Implementations raise contextual host-specific runtime errors when updates fail.

        Ties to other methods
        Used by refresh setup and per-section completion or failure flows.

        Why this exists
        Provides a typed callable contract for section-level refresh feedback.
        """
        ...


class _ClearSectionDataViewsFn(Protocol):
    def __call__(self, key: str, *, message: str = "", level: str = "info") -> None:
        """
        Summary
        Clear stale table and metric views for one section.

        Inputs
        key: Section key.
        message: Optional fallback message to render.
        level: Message severity level.

        Outputs
        None.

        Side effects
        Mutates section data views on the host.

        Error handling
        Implementations raise contextual host-specific runtime errors when clear operations fail.

        Ties to other methods
        Used by refresh error handling paths.

        Why this exists
        Provides a typed callable contract for stale data cleanup.
        """
        ...


class _SetFieldFn(Protocol):
    def __call__(self, key: str, text: str, fg: str | None = None, tooltip: str | None = None) -> None:
        """
        Summary
        Update a section summary field value and optional styling hints.

        Inputs
        key: Section key.
        text: Field text to display.
        fg: Optional foreground color override.
        tooltip: Optional tooltip text override.

        Outputs
        None.

        Side effects
        Updates section field display state on the host.

        Error handling
        Implementations raise contextual host-specific runtime errors when updates fail.

        Ties to other methods
        Used by section refresh fallback rendering.

        Why this exists
        Provides a typed callable contract for summary-field updates across mixins.
        """
        ...


class _DashboardRefreshMixin:
    _refresh_after_id: str | None
    _queue: SectionQueue
    _shutdown: ShutdownManager
    _cfg: Config
    _set_next_refresh_hint: _SetNextRefreshHintFn
    _set_refresh_controls_busy: Callable[[bool], None]
    _set_status: _SetStatusFn
    _set_section_feedback: _SetSectionFeedbackFn
    _clear_section_data_views: _ClearSectionDataViewsFn
    set_field: _SetFieldFn
    _color: Callable[[str], str]

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
        Reports stale or invalid timer cancellation failures with standardized UI boundary errors.

        Ties to other methods
        Used by `_schedule_next_refresh`, manual refresh shortcuts, and close handling.

        Why this exists
        Ensures only one refresh timer remains active at a time.
        """
        try:
            if self._refresh_after_id is None:
                return
            try:
                cast(tk.Misc, self).after_cancel(self._refresh_after_id)
            except tk.TclError as cancel_exc:
                mapped = map_boundary_exception(
                    cancel_exc,
                    boundary=ErrorBoundary.UI,
                    default_message="Scheduled refresh cancellation failed",
                )
                sys.stderr.write(
                    mapped.to_stderr_line(
                        module_path=MODULE_PATH,
                        method="DashboardApp._cancel_scheduled_refresh",
                    )
                    + "\n"
                )
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
            self._refresh_after_id = cast(tk.Misc, self).after(bounded_delay, self._run_scheduled_refresh)
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
        app_module = sys.modules.get("mac_health_checkup.app.gui.app")
        section_handlers = DEFAULT_SECTION_HANDLERS
        section_runner = default_run_section
        if app_module is not None:
            section_handlers = getattr(app_module, "SECTION_HANDLERS", section_handlers)
            section_runner = getattr(app_module, "run_section", section_runner)
        failures = 0
        total_sections = len(section_handlers)
        now = datetime.now().strftime("%H:%M:%S")
        started = time.perf_counter()
        tokens = self.__dict__.get("_ui_tokens")
        loading_feedback = tokens.section_feedback_loading if tokens is not None else "Refreshing section..."
        error_feedback = (
            tokens.section_feedback_error
            if tokens is not None
            else "Section refresh failed. Auto retry is enabled."
        )
        try:
            self._set_refresh_controls_busy(True)
            self._set_status(f"Refreshing {total_sections} sections...", level="loading")
            cast(tk.Misc, self).update_idletasks()
            for key in section_handlers:
                self._queue.enqueue(key)
                self._set_section_feedback(key, loading_feedback, level="loading")
            for key in self._queue.drain():
                try:
                    section_runner(cast(SectionHost, self), key)
                    self._set_section_feedback(key, f"Updated at {now}.", level="success")
                except (
                    tk.TclError,
                    RuntimeError,
                    ValueError,
                    TypeError,
                    AttributeError,
                    KeyError,
                    IndexError,
                    OSError,
                ) as exc:
                    failures += 1
                    render_exc: Exception | None = None
                    try:
                        self._clear_section_data_views(
                            key,
                            message="Data unavailable. The section will retry on the next refresh.",
                        )
                        error_color = self._color("status.error")
                        self.set_field(
                            key,
                            f"Unable to refresh ({type(exc).__name__}). Hover for details.",
                            fg=error_color,
                            tooltip=str(exc),
                        )
                        self._set_section_feedback(key, error_feedback, level="error")
                    except (
                        tk.TclError,
                        RuntimeError,
                        ValueError,
                        TypeError,
                        AttributeError,
                        KeyError,
                        IndexError,
                        OSError,
                    ) as field_exc:
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
            except (tk.TclError, RuntimeError, ValueError, TypeError) as finalize_exc:
                mapped = map_boundary_exception(
                    finalize_exc,
                    boundary=ErrorBoundary.UI,
                    default_message="Refresh finalize failed",
                )
                sys.stderr.write(
                    mapped.to_stderr_line(module_path=MODULE_PATH, method="DashboardApp._refresh") + "\n"
                )

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
            cast(tk.Misc, self).destroy()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._on_close", "Failed to close UI", exc)
            ) from exc
