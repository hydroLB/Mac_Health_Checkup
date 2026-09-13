from __future__ import annotations

import concurrent.futures
import sys
import threading
import tkinter as tk
from typing import Callable, Protocol, cast

from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.app.gui.dashboard.queueing import SectionQueue
from mac_health_checkup.app.gui.dashboard.refresh_support import (
    RECOVERABLE_SECTION_EXCEPTIONS,
    BufferedRefreshResult,
    RefreshCycle,
    RenderMetricsOperation,
    RenderOperation,
    RenderTableOperation,
    RunOnUiOperation,
    SetFieldOperation,
    SetMachineHintOperation,
    build_refresh_messages,
    build_refresh_status_update,
    resolve_refresh_runtime,
    run_buffered_refresh,
    start_refresh_cycle,
)
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import Config
from mac_health_checkup.core.utils import format_error
from mac_health_checkup.core.utils.error_boundary import ErrorBoundary, map_boundary_exception

MODULE_PATH = "mac_health_checkup/app/gui/dashboard/refresh_mixin.py"
_REFRESH_POLL_MS = 25
_SHUTDOWN_POLL_MS = 100


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
    _refresh_executor: concurrent.futures.ThreadPoolExecutor
    _refresh_future: concurrent.futures.Future[BufferedRefreshResult] | None
    _refresh_cancel_event: threading.Event
    _refresh_poll_after_id: str | None
    _shutdown_after_id: str | None
    _refresh_cycle: RefreshCycle | None

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
        Centralizes non-blocking collection and deterministic main-thread replay.
        """
        try:
            active_future = self.__dict__.get("_refresh_future")
            if active_future is not None:
                return
            self._cancel_scheduled_refresh()
            app_module = sys.modules.get("mac_health_checkup.app.gui.app")
            runtime = resolve_refresh_runtime(app_module)
            section_keys = tuple(runtime.section_handlers)
            cycle = start_refresh_cycle(total_sections=len(section_keys))
            messages = build_refresh_messages(self.__dict__.get("_ui_tokens"))
            self._set_refresh_controls_busy(True)
            self._set_status(f"Refreshing {cycle.total_sections} sections...", level="loading")
            for key in section_keys:
                self._set_section_feedback(key, messages.loading_feedback, level="loading")
            cancel_event = threading.Event()
            executor = self.__dict__.get("_refresh_executor")
            if executor is None:
                executor = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="diagnostics"
                )
                self._refresh_executor = executor
            self._refresh_cancel_event = cancel_event
            self._refresh_cycle = cycle
            machine_hint = cast(SectionHost, self).machine_hint()
            self._refresh_future = executor.submit(
                run_buffered_refresh,
                section_keys,
                section_runner=runtime.section_runner,
                machine_hint=machine_hint,
                should_cancel=lambda: cancel_event.is_set() or self._shutdown.shutdown_requested(),
            )
            self._schedule_refresh_poll()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            pending_cancel_event = self.__dict__.get("_refresh_cancel_event")
            if pending_cancel_event is not None:
                pending_cancel_event.set()
            future = self.__dict__.get("_refresh_future")
            if future is not None:
                future.cancel()
            self._refresh_future = None
            self._refresh_cycle = None
            self._set_refresh_controls_busy(False)
            self._set_status(f"Refresh error: {type(exc).__name__}", level="error")

    def _schedule_refresh_poll(self) -> None:
        """
        Summary
        Schedule a short Tk-thread poll for background refresh completion.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Registers one Tk after callback.

        Error handling
        Propagates Tk scheduling failures to the refresh boundary.

        Ties to other methods
        Calls `_poll_refresh_result`.

        Why this exists
        Future completion must be observed without blocking Tk.
        """
        if self.__dict__.get("_refresh_poll_after_id") is not None:
            return
        poll_ms = max(
            10,
            int(getattr(self._cfg.gui, "ui_queue_poll_ms", _REFRESH_POLL_MS)),
        )
        self._refresh_poll_after_id = cast(tk.Misc, self).after(poll_ms, self._poll_refresh_result)

    def _poll_refresh_result(self) -> None:
        """
        Summary
        Replay completed buffered section results on the Tk thread.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Polls a future, updates UI state, and schedules the next refresh.

        Error handling
        Maps recoverable worker or replay failures to UI status.

        Ties to other methods
        Scheduled by `_schedule_refresh_poll`.

        Why this exists
        Only the Tk thread may apply buffered render operations.
        """
        self._refresh_poll_after_id = None
        future = self.__dict__.get("_refresh_future")
        if future is None:
            return
        if not future.done():
            if self._shutdown.shutdown_requested():
                self._refresh_cancel_event.set()
            self._schedule_refresh_poll()
            return

        self._refresh_future = None
        cycle = self._refresh_cycle
        self._refresh_cycle = None
        messages = build_refresh_messages(self.__dict__.get("_ui_tokens"))
        try:
            result = future.result()
            if self._shutdown.shutdown_requested():
                return
            replay_failures = 0
            for section in result.sections:
                if section.error is not None:
                    self._handle_section_refresh_failure(
                        section.key,
                        section.error,
                        error_feedback=messages.error_feedback,
                    )
                    continue
                try:
                    self._replay_render_operations(section.operations)
                    refreshed_at = cycle.refreshed_at if cycle is not None else "now"
                    self._set_section_feedback(
                        section.key,
                        f"Updated at {refreshed_at}.",
                        level="success",
                    )
                except RECOVERABLE_SECTION_EXCEPTIONS as replay_exc:
                    replay_failures += 1
                    self._handle_section_refresh_failure(
                        section.key,
                        replay_exc,
                        error_feedback=messages.error_feedback,
                    )
            if cycle is not None:
                status_update = build_refresh_status_update(
                    cycle,
                    failures=result.failures + replay_failures,
                )
                self._set_status(status_update.text, level=status_update.level)
        except (concurrent.futures.CancelledError, tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            self._set_status(f"Refresh error: {type(exc).__name__}", level="error")
        finally:
            self._set_refresh_controls_busy(False)
            if not self._shutdown.shutdown_requested():
                self._schedule_next_refresh(self._cfg.gui.auto_refresh_ms)

    def _replay_render_operations(self, operations: tuple[RenderOperation, ...]) -> None:
        """
        Summary
        Apply recorded SectionHost operations to the live UI host in order.

        Inputs
        operations: Ordered buffered render operations.

        Outputs
        None.

        Side effects
        Mutates live dashboard UI state.

        Error handling
        Propagates render failures for per-section fallback handling.

        Ties to other methods
        Used by `_poll_refresh_result`.

        Why this exists
        Separates worker collection from main-thread Tk mutation.
        """
        host = cast(SectionHost, self)
        for operation in operations:
            if isinstance(operation, SetFieldOperation):
                host.set_field(operation.key, operation.text, operation.fg, operation.tooltip)
            elif isinstance(operation, RenderMetricsOperation):
                host.render_metrics_table(operation.key, operation.rows, columns=operation.columns)
            elif isinstance(operation, RenderTableOperation):
                host.render_table(
                    operation.key,
                    operation.headers,
                    operation.rows,
                    operation.max_col_chars,
                )
            elif isinstance(operation, RunOnUiOperation):
                host.run_on_ui(operation.callback)
            elif isinstance(operation, SetMachineHintOperation):
                host.set_machine_hint(operation.descriptor)

    def _schedule_shutdown_poll(self) -> None:
        """
        Summary
        Poll shutdown state so signal-triggered shutdown closes the Tk mainloop.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Closes the app or registers one Tk after callback.

        Error handling
        Propagates Tk scheduling and close failures to the app boundary.

        Ties to other methods
        Called by app startup and `_poll_shutdown`.

        Why this exists
        Signals set lifecycle state but Tk still needs a main-thread close action.
        """
        if self._shutdown.shutdown_requested():
            self._on_close()
            return
        self._shutdown_after_id = cast(tk.Misc, self).after(_SHUTDOWN_POLL_MS, self._poll_shutdown)

    def _poll_shutdown(self) -> None:
        """
        Summary
        Close the window after SIGINT or SIGTERM requests shutdown.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Clears the poll id and advances shutdown polling.

        Error handling
        Propagates close or rescheduling failures to the Tk boundary.

        Ties to other methods
        Scheduled by `_schedule_shutdown_poll`.

        Why this exists
        Gives signal-triggered lifecycle state a prompt Tk-mainloop exit path.
        """
        self._shutdown_after_id = None
        self._schedule_shutdown_poll()

    def _handle_section_refresh_failure(self, key: str, exc: Exception, *, error_feedback: str) -> None:
        """
        Summary
        Render fallback state for a failed section refresh.

        Inputs
        key: Section key.
        exc: Section refresh failure.
        error_feedback: Inline section feedback message for the failed state.

        Outputs
        None.

        Side effects
        Clears stale section data, updates the summary field, and sets inline feedback.

        Error handling
        Swallows secondary render failures so one broken section does not abort the refresh loop.

        Ties to other methods
        Used by `_refresh` after a section runner failure.

        Why this exists
        Keeps the UI fallback path explicit while the support module owns the section-loop bookkeeping.
        """
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
        except RECOVERABLE_SECTION_EXCEPTIONS:
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
            refresh_poll_id = self.__dict__.get("_refresh_poll_after_id")
            if refresh_poll_id is not None:
                try:
                    cast(tk.Misc, self).after_cancel(refresh_poll_id)
                except tk.TclError:
                    pass
                self._refresh_poll_after_id = None
            shutdown_poll_id = self.__dict__.get("_shutdown_after_id")
            if shutdown_poll_id is not None:
                try:
                    cast(tk.Misc, self).after_cancel(shutdown_poll_id)
                except tk.TclError:
                    pass
                self._shutdown_after_id = None
            cancel_event = self.__dict__.get("_refresh_cancel_event")
            if cancel_event is not None:
                cancel_event.set()
            future = self.__dict__.get("_refresh_future")
            if future is not None:
                try:
                    future.cancel()
                except (RuntimeError, ValueError, TypeError):
                    pass
                self._refresh_future = None
            executor = self.__dict__.get("_refresh_executor")
            if executor is not None:
                try:
                    executor.shutdown(wait=False, cancel_futures=True)
                except (RuntimeError, ValueError, TypeError):
                    pass
            self._shutdown.trigger_shutdown()
            cast(tk.Misc, self).destroy()
        except (tk.TclError, RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DashboardApp._on_close", "Failed to close UI", exc)
            ) from exc
