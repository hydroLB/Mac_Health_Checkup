from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol, Sequence

from mac_health_checkup.app.gui.dashboard.queueing import SectionQueue
from mac_health_checkup.app.gui.dashboard.ui_helpers import _refresh_status_message
from mac_health_checkup.app.gui.sections.types import SectionHost

SectionRunner = Callable[[SectionHost, str], object]
_SectionRunner = SectionRunner


@dataclass(frozen=True)
class SetFieldOperation:
    key: str
    text: str
    fg: str | None
    tooltip: str | None


@dataclass(frozen=True)
class RenderMetricsOperation:
    key: str
    rows: tuple[tuple[str, str, str], ...]
    columns: int


@dataclass(frozen=True)
class RenderTableOperation:
    key: str
    headers: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    max_col_chars: tuple[int | None, ...] | None


@dataclass(frozen=True)
class RunOnUiOperation:
    callback: Callable[[], None]


@dataclass(frozen=True)
class SetMachineHintOperation:
    descriptor: str


RenderOperation = (
    SetFieldOperation
    | RenderMetricsOperation
    | RenderTableOperation
    | RunOnUiOperation
    | SetMachineHintOperation
)


@dataclass(frozen=True)
class BufferedSectionResult:
    key: str
    operations: tuple[RenderOperation, ...]
    error: Exception | None


@dataclass(frozen=True)
class BufferedRefreshResult:
    total_sections: int
    sections: tuple[BufferedSectionResult, ...]
    elapsed_ms: int
    cancelled: bool

    @property
    def failures(self) -> int:
        """
        Summary
        Count failed section results.

        Inputs
        None.

        Outputs
        Number of section errors.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used by refresh completion status rendering.

        Why this exists
        Keeps failure accounting derived from immutable worker results.
        """
        return sum(1 for section in self.sections if section.error is not None)


class RecordingSectionHost:
    """Record SectionHost render requests without accessing Tk objects."""

    def __init__(self, *, machine_hint: str) -> None:
        """
        Summary
        Initialize a non-Tk render recorder.

        Inputs
        machine_hint: Initial machine descriptor.

        Outputs
        None.

        Side effects
        Initializes in-memory operation storage.

        Error handling
        None.

        Ties to other methods
        Used by `run_buffered_refresh`.

        Why this exists
        Worker threads must not receive the live Tk host.
        """
        self._machine_hint = machine_hint
        self._operations: list[RenderOperation] = []

    def get_widget(self, key: str) -> None:
        """
        Summary
        Report that widgets are unavailable on the recording host.

        Inputs
        key: Widget key.

        Outputs
        None.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Implements `SectionHost.get_widget`.

        Why this exists
        Tk widgets cannot cross the worker-thread boundary.
        """
        _ = key
        return None

    def set_field(self, key: str, text: str, fg: str | None = None, tooltip: str | None = None) -> None:
        """
        Summary
        Record a field update.

        Inputs
        key: Field key. text: Display text. fg: Optional color. tooltip: Optional tooltip.

        Outputs
        None.

        Side effects
        Appends an operation.

        Error handling
        None.

        Ties to other methods
        Replayed by the dashboard refresh mixin.

        Why this exists
        Defers Tk updates to the main thread.
        """
        self._operations.append(SetFieldOperation(key=key, text=text, fg=fg, tooltip=tooltip))

    def render_metrics_table(
        self, key: str, rows: Sequence[tuple[str, str, str]], *, columns: int = 2
    ) -> None:
        """
        Summary
        Record a metrics-table update.

        Inputs
        key: Section key. rows: Metric rows. columns: Column count.

        Outputs
        None.

        Side effects
        Appends an operation.

        Error handling
        None.

        Ties to other methods
        Replayed by the dashboard refresh mixin.

        Why this exists
        Defers Tk updates to the main thread.
        """
        self._operations.append(RenderMetricsOperation(key=key, rows=tuple(rows), columns=columns))

    def render_table(
        self,
        key: str,
        headers: tuple[str, ...],
        rows: Sequence[tuple[str, ...]],
        max_col_chars: tuple[int | None, ...] | None = None,
    ) -> None:
        """
        Summary
        Record a general-table update.

        Inputs
        key: Section key. headers: Headers. rows: Rows. max_col_chars: Optional limits.

        Outputs
        None.

        Side effects
        Appends an operation.

        Error handling
        None.

        Ties to other methods
        Replayed by the dashboard refresh mixin.

        Why this exists
        Defers Tk updates to the main thread.
        """
        self._operations.append(
            RenderTableOperation(
                key=key,
                headers=headers,
                rows=tuple(rows),
                max_col_chars=max_col_chars,
            )
        )

    def section_container(self, key: str) -> None:
        """
        Summary
        Report that section containers are unavailable.

        Inputs
        key: Section key.

        Outputs
        None.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Implements `SectionHost.section_container`.

        Why this exists
        Tk containers cannot cross the worker-thread boundary.
        """
        _ = key
        return None

    def run_on_ui(self, fn: Callable[[], None]) -> None:
        """
        Summary
        Record a callback for main-thread execution.

        Inputs
        fn: Callback to replay.

        Outputs
        None.

        Side effects
        Appends an operation.

        Error handling
        None.

        Ties to other methods
        Replayed by the dashboard refresh mixin.

        Why this exists
        Preserves the host contract without executing callbacks in workers.
        """
        self._operations.append(RunOnUiOperation(callback=fn))

    def set_machine_hint(self, descriptor: str) -> None:
        """
        Summary
        Record and locally apply a machine hint.

        Inputs
        descriptor: Machine descriptor.

        Outputs
        None.

        Side effects
        Updates recorder state and appends an operation.

        Error handling
        None.

        Ties to other methods
        Supports ordered section execution and UI replay.

        Why this exists
        Later worker sections may depend on the machine hint.
        """
        self._machine_hint = descriptor
        self._operations.append(SetMachineHintOperation(descriptor=descriptor))

    def machine_hint(self) -> str:
        """
        Summary
        Return the current buffered machine hint.

        Inputs
        None.

        Outputs
        Machine descriptor.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Implements `SectionHost.machine_hint`.

        Why this exists
        Preserves cross-section state without accessing Tk.
        """
        return self._machine_hint

    def drain_operations(self) -> tuple[RenderOperation, ...]:
        """
        Summary
        Return and clear recorded operations.

        Inputs
        None.

        Outputs
        Immutable ordered operation tuple.

        Side effects
        Clears buffered operations.

        Error handling
        None.

        Ties to other methods
        Used after a successful worker section.

        Why this exists
        Associates each render batch with its section result.
        """
        operations = tuple(self._operations)
        self._operations.clear()
        return operations

    def discard_operations(self) -> None:
        """
        Summary
        Clear partial operations from a failed section.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Clears buffered operations.

        Error handling
        None.

        Ties to other methods
        Used by `run_buffered_refresh` on section failure.

        Why this exists
        Failed sections must not replay partial, stale UI state.
        """
        self._operations.clear()


def run_buffered_refresh(
    section_keys: Sequence[str],
    *,
    section_runner: SectionRunner,
    machine_hint: str,
    should_cancel: Callable[[], bool],
) -> BufferedRefreshResult:
    """
    Summary
    Run ordered section collection against a non-Tk recording host.

    Inputs
    section_keys: Ordered section keys. section_runner: Collector callback. machine_hint: Initial hint.
    should_cancel: Cancellation callback checked between sections.

    Outputs
    Buffered refresh result for Tk-thread replay.

    Side effects
    Runs diagnostic collectors and records render operations in memory.

    Error handling
    Isolates ordinary exceptions per section.

    Ties to other methods
    Submitted by `_DashboardRefreshMixin._refresh`.

    Why this exists
    Diagnostics must run off the Tk thread without allowing workers to touch Tk.
    """
    started_at = time.perf_counter()
    host = RecordingSectionHost(machine_hint=machine_hint)
    results: list[BufferedSectionResult] = []
    cancelled = False
    for key in section_keys:
        if should_cancel():
            cancelled = True
            break
        try:
            section_runner(host, key)
            results.append(BufferedSectionResult(key=key, operations=host.drain_operations(), error=None))
        except (
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
            host.discard_operations()
            results.append(BufferedSectionResult(key=key, operations=(), error=exc))
    elapsed_ms = int((time.perf_counter() - started_at) * 1000.0)
    return BufferedRefreshResult(
        total_sections=len(section_keys),
        sections=tuple(results),
        elapsed_ms=elapsed_ms,
        cancelled=cancelled,
    )


class _SetSectionFeedbackFn(Protocol):
    """
    Summary
    Describe the section feedback callback surface used by refresh helpers.

    Inputs
    None.

    Outputs
    Structural callable protocol.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by queueing and per-section refresh helpers.

    Why this exists
    Strict mypy rejects `Callable[..., None]` here, and the dashboard relies on a keyword-only `level` parameter.
    """

    def __call__(self, key: str, message: str, *, level: str) -> None:
        """
        Summary
        Update inline section feedback for one section key.

        Inputs
        key: Section key.
        message: Feedback text.
        level: Severity level.

        Outputs
        None.

        Side effects
        Updates UI feedback state on the host.

        Error handling
        Implementations may raise host-specific runtime errors.

        Ties to other methods
        Used by refresh helpers.

        Why this exists
        Refresh helpers need one precise callback signature for section feedback.
        """


RECOVERABLE_REFRESH_ERRORS: Final = (
    RuntimeError,
    ValueError,
    TypeError,
    AttributeError,
    KeyError,
    IndexError,
    OSError,
)
RECOVERABLE_SECTION_EXCEPTIONS = RECOVERABLE_REFRESH_ERRORS


@dataclass(frozen=True)
class RefreshDependencies:
    """
    Summary
    Hold the resolved section handlers and runner used for one refresh cycle.

    Inputs
    section_handlers: Mapping of section keys to handler objects.
    section_runner: Callable that executes one section against a host.

    Outputs
    Immutable refresh dependency bundle.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Returned by `resolve_refresh_dependencies` and consumed by `run_refresh_cycle`.

    Why this exists
    The refresh loop needs both handlers and runner, and bundling them keeps the mixin interface simple.
    """

    section_handlers: Mapping[str, object]
    section_runner: SectionRunner


@dataclass(frozen=True)
class RefreshMessages:
    """
    Summary
    Hold user-facing feedback strings for one refresh cycle.

    Inputs
    loading_feedback: Per-section loading text.
    error_feedback: Per-section retry/error text.

    Outputs
    Immutable feedback bundle.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Returned by `refresh_messages` and consumed by `run_refresh_cycle`.

    Why this exists
    The mixin should not repeatedly reach into UI token objects while running the refresh loop.
    """

    loading_feedback: str
    error_feedback: str


@dataclass(frozen=True)
class RefreshCycleResult:
    """
    Summary
    Describe the outcome of one refresh cycle.

    Inputs
    total_sections: Number of sections attempted.
    failures: Number of recoverable section failures.
    elapsed_ms: Wall-clock duration in milliseconds.

    Outputs
    Immutable refresh result record.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Returned by `run_refresh_cycle` and consumed by completion-status helpers.

    Why this exists
    Refresh status rendering should be driven by explicit measured results rather than mutable loop state.
    """

    total_sections: int
    failures: int
    elapsed_ms: int


@dataclass(frozen=True)
class RefreshCycle:
    """
    Summary
    Hold the start-of-refresh metadata needed for final status rendering.

    Inputs
    total_sections: Number of sections expected in this cycle.
    refreshed_at: Human-readable timestamp captured at cycle start.
    started_at: Perf-counter timestamp for elapsed time measurement.

    Outputs
    Immutable refresh-cycle metadata.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Returned by `start_refresh_cycle` and consumed by `build_refresh_status_update`.

    Why this exists
    The mixin should not manually thread timestamp and duration state through multiple helper calls.
    """

    total_sections: int
    refreshed_at: str
    started_at: float


@dataclass(frozen=True)
class RefreshStatusUpdate:
    """
    Summary
    Hold the final dashboard status text and severity for a refresh cycle.

    Inputs
    text: User-facing header status text.
    level: Status severity level.

    Outputs
    Immutable status update payload.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Returned by `build_refresh_status_update` and consumed by `refresh_mixin._refresh`.

    Why this exists
    The support layer should return explicit completion state rather than leaking status formatting details.
    """

    text: str
    level: str


def resolve_refresh_dependencies(
    *,
    app_module: object | None,
    default_section_handlers: Mapping[str, object],
    default_runner: SectionRunner,
) -> RefreshDependencies:
    """
    Summary
    Resolve the section handler mapping and runner for the current dashboard refresh.

    Inputs
    app_module: Optional loaded app module that may expose patched refresh collaborators.
    default_section_handlers: Fallback handler mapping from the dashboard package.
    default_runner: Fallback section runner.

    Outputs
    `RefreshDependencies`.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `refresh_mixin._refresh`.

    Why this exists
    Tests patch `mac_health_checkup.app.gui.app` directly, so refresh dependency resolution needs one stable helper.
    """
    section_handlers = default_section_handlers
    section_runner = default_runner
    if app_module is not None:
        section_handlers = getattr(app_module, "SECTION_HANDLERS", section_handlers)
        section_runner = getattr(app_module, "run_section", section_runner)
    return RefreshDependencies(section_handlers=section_handlers, section_runner=section_runner)


def resolve_refresh_runtime(app_module: object | None) -> RefreshDependencies:
    """
    Summary
    Resolve the section handlers and runner used by the dashboard refresh mixin.

    Inputs
    app_module: Optional loaded dashboard app module that may expose patched globals.

    Outputs
    `RefreshDependencies`.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `refresh_mixin._refresh` and direct helper tests.

    Why this exists
    The refresh mixin and its tests both rely on the app-module override seam.
    """
    from mac_health_checkup.app.gui.dashboard.sections import (
        SECTION_HANDLERS as default_section_handlers,
    )
    from mac_health_checkup.app.gui.dashboard.sections import run_section as default_runner

    return resolve_refresh_dependencies(
        app_module=app_module,
        default_section_handlers=default_section_handlers,
        default_runner=default_runner,
    )


def refresh_messages(tokens: object | None) -> RefreshMessages:
    """
    Summary
    Build the user-facing section feedback strings for a refresh cycle.

    Inputs
    tokens: Optional UI token object with section feedback attributes.

    Outputs
    `RefreshMessages`.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `refresh_mixin._refresh`.

    Why this exists
    Refresh messaging should fall back cleanly when the host is partially initialized.
    """
    loading_feedback = "Refreshing section..."
    error_feedback = "Section refresh failed. Auto retry is enabled."
    if tokens is not None:
        loading_feedback = str(getattr(tokens, "section_feedback_loading", loading_feedback))
        error_feedback = str(getattr(tokens, "section_feedback_error", error_feedback))
    return RefreshMessages(loading_feedback=loading_feedback, error_feedback=error_feedback)


def build_refresh_messages(tokens: object | None) -> RefreshMessages:
    """
    Summary
    Build section feedback strings for a refresh cycle.

    Inputs
    tokens: Optional UI token object with section feedback attributes.

    Outputs
    `RefreshMessages`.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `refresh_mixin._refresh`.

    Why this exists
    This helper name keeps the mixin and direct tests explicit about refresh-message construction.
    """
    return refresh_messages(tokens)


def start_refresh_cycle(*, total_sections: int) -> RefreshCycle:
    """
    Summary
    Capture the start metadata for a dashboard refresh cycle.

    Inputs
    total_sections: Number of sections expected in the cycle.

    Outputs
    `RefreshCycle`.

    Side effects
    Reads the system clock and perf counter.

    Error handling
    None.

    Ties to other methods
    Used by `refresh_mixin._refresh`.

    Why this exists
    Refresh timing should be initialized once and then carried explicitly through status rendering.
    """
    return RefreshCycle(
        total_sections=total_sections,
        refreshed_at=datetime.now().strftime("%H:%M:%S"),
        started_at=time.perf_counter(),
    )


def queue_refresh_sections(
    queue: SectionQueue,
    section_handlers: Mapping[str, object],
    set_section_feedback_fn: _SetSectionFeedbackFn,
    *,
    loading_feedback: str,
) -> None:
    """
    Summary
    Enqueue all section keys for one refresh cycle and emit per-section loading feedback.

    Inputs
    queue: Section refresh queue.
    section_handlers: Mapping of section keys to handler objects.
    set_section_feedback_fn: Section feedback callback.
    loading_feedback: Loading message text.

    Outputs
    None.

    Side effects
    Enqueues all sections and emits section loading feedback.

    Error handling
    None.

    Ties to other methods
    Used by `refresh_mixin._refresh` and direct helper tests.

    Why this exists
    Queue population and loading feedback are deterministic setup steps that should not live inline in the mixin.
    """
    for key in section_handlers:
        queue.enqueue(key)
        set_section_feedback_fn(key, loading_feedback, level="loading")


def run_refresh_cycle(
    host: SectionHost,
    *,
    dependencies: RefreshDependencies,
    queue: SectionQueue,
    now: str,
    started_at: float,
    section_feedback_loading: str,
    set_section_feedback_fn: _SetSectionFeedbackFn,
    handle_section_failure_fn: Callable[[str, Exception], None],
) -> RefreshCycleResult:
    """
    Summary
    Execute the per-section refresh loop and report measured results.

    Inputs
    host: Section host implementation.
    dependencies: Resolved refresh dependencies.
    queue: Section refresh queue.
    now: Human-readable timestamp string.
    started_at: Perf-counter timestamp captured before refresh began.
    section_feedback_loading: Per-section loading text.
    set_section_feedback_fn: Section feedback callback.
    handle_section_failure_fn: Recoverable failure callback.

    Outputs
    `RefreshCycleResult`.

    Side effects
    Enqueues section keys, runs section handlers, and emits per-section success/failure feedback.

    Error handling
    Re-raises non-recoverable exceptions. Recoverable section failures are delegated to `handle_section_failure_fn`.

    Ties to other methods
    Used by `refresh_mixin._refresh`.

    Why this exists
    The refresh loop is the highest-value seam to extract because it contains deterministic orchestration but not Tk scheduling.
    """
    total_sections = len(dependencies.section_handlers)
    failures = 0
    for key in dependencies.section_handlers:
        queue.enqueue(key)
        set_section_feedback_fn(key, section_feedback_loading, level="loading")
    for key in queue.drain():
        try:
            dependencies.section_runner(host, key)
            set_section_feedback_fn(key, f"Updated at {now}.", level="success")
        except RECOVERABLE_REFRESH_ERRORS as exc:
            failures += 1
            handle_section_failure_fn(key, exc)
    elapsed_ms = int((time.perf_counter() - started_at) * 1000.0)
    return RefreshCycleResult(total_sections=total_sections, failures=failures, elapsed_ms=elapsed_ms)


def run_refresh_sections(
    queue: SectionQueue,
    host: SectionHost,
    *,
    section_runner: SectionRunner,
    on_section_success: Callable[[str], None],
    on_section_failure: Callable[[str, Exception], None],
) -> int:
    """
    Summary
    Run each queued dashboard section and count recoverable failures.

    Inputs
    queue: Section refresh queue.
    host: Section host implementation.
    section_runner: Section runner callback.
    on_section_success: Success callback.
    on_section_failure: Failure callback.

    Outputs
    Number of recoverable section failures.

    Side effects
    Drains the queue and triggers success/failure callbacks for each section.

    Error handling
    Re-raises non-recoverable exceptions.

    Ties to other methods
    Used by `refresh_mixin._refresh` and direct helper tests.

    Why this exists
    The section-execution loop is the main deterministic refresh seam worth extracting.
    """
    failures = 0
    for key in queue.drain():
        try:
            section_runner(host, key)
            on_section_success(key)
        except RECOVERABLE_SECTION_EXCEPTIONS as exc:
            failures += 1
            on_section_failure(key, exc)
    return failures


def refresh_completion_status(
    *,
    refreshed_at: str,
    result: RefreshCycleResult,
    refresh_status_message_fn: Callable[[str, int, int, int], str],
) -> tuple[str, str]:
    """
    Summary
    Build the top-level refresh status message and severity for a completed cycle.

    Inputs
    refreshed_at: Human-readable completion timestamp.
    result: Measured refresh-cycle outcome.
    refresh_status_message_fn: Status formatter callback.

    Outputs
    Tuple of `(text, level)`.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `refresh_mixin._refresh`.

    Why this exists
    The completion banner should be derived from explicit result state in one place.
    """
    text = refresh_status_message_fn(
        refreshed_at,
        result.total_sections,
        result.failures,
        result.elapsed_ms,
    )
    level = "warn" if result.failures > 0 else "info"
    return text, level


def build_refresh_status_update(cycle: RefreshCycle, *, failures: int) -> RefreshStatusUpdate:
    """
    Summary
    Build the final dashboard status text and severity for a completed refresh cycle.

    Inputs
    cycle: Start-of-refresh metadata.
    failures: Number of recoverable section failures.

    Outputs
    `RefreshStatusUpdate`.

    Side effects
    Reads the perf counter to compute elapsed time.

    Error handling
    None.

    Ties to other methods
    Used by `refresh_mixin._refresh` and direct helper tests.

    Why this exists
    The mixin should receive one explicit completion payload instead of recomputing timing and status details.
    """
    elapsed_ms = int((time.perf_counter() - cycle.started_at) * 1000.0)
    text, level = refresh_completion_status(
        refreshed_at=cycle.refreshed_at,
        result=RefreshCycleResult(
            total_sections=cycle.total_sections,
            failures=failures,
            elapsed_ms=elapsed_ms,
        ),
        refresh_status_message_fn=lambda refreshed_at,
        total_sections,
        failures,
        elapsed_ms: _refresh_status_message(
            refreshed_at=refreshed_at,
            total_sections=total_sections,
            failures=failures,
            elapsed_ms=elapsed_ms,
        ),
    )
    return RefreshStatusUpdate(text=text, level=level)
