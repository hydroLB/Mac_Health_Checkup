from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Protocol

from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.app.entrypoint_support.runtime_mode import _ShutdownManagerProtocol
from mac_health_checkup.core.utils import LogContext, StructuredLogger


class _RuntimeStateProtocol(Protocol):
    """
    Summary
    Describe the runtime state surface consumed by interactive entrypoint helpers.

    Inputs
    None.

    Outputs
    Structural protocol for the entrypoint runtime state.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `run_cli_mode`, `run_gui_mode`, and `run_gui_fallback_mode`.

    Why this exists
    Interactive mode helpers should depend only on the runtime fields they actually use.
    """

    @property
    def logger(self) -> StructuredLogger:
        """
        Summary
        Return the structured runtime logger.

        Inputs
        None.

        Outputs
        `StructuredLogger`.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used by GUI fallback logging.

        Why this exists
        Interactive helpers need read-only logger access.
        """

    @property
    def context(self) -> LogContext:
        """
        Summary
        Return the shared runtime log context.

        Inputs
        None.

        Outputs
        `LogContext`.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used by GUI fallback logging.

        Why this exists
        Interactive helpers need read-only context access.
        """

    @property
    def shutdown(self) -> _ShutdownManagerProtocol:
        """
        Summary
        Return the installed shutdown manager.

        Inputs
        None.

        Outputs
        Shutdown manager implementation.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used by CLI and GUI fallback mode completion.

        Why this exists
        Helpers should not depend on the concrete shutdown class.
        """


def run_cli_mode(
    args: argparse.Namespace,
    runtime: _RuntimeStateProtocol,
    *,
    console_host_type: type[ConsoleHost],
    run_sections_best_effort_fn: Callable[[ConsoleHost, StructuredLogger, LogContext], int],
    print_console_output_fn: Callable[[ConsoleHost], None],
    print_cli_advice_fn: Callable[[ConsoleHost], None],
    should_fail_on_host_fn: Callable[[ConsoleHost, str], bool],
    finish_mode_fn: Callable[[_ShutdownManagerProtocol, int], int],
) -> int:
    """
    Summary
    Run all sections through the console host and emit CLI output.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.
    console_host_type: Console host constructor.
    run_sections_best_effort_fn: Section runner callback.
    print_console_output_fn: Console output callback.
    print_cli_advice_fn: Advice renderer callback.
    should_fail_on_host_fn: Fail-policy callback.
    finish_mode_fn: Shutdown completion callback.

    Outputs
    CLI-mode process exit code.

    Side effects
    Runs collectors, prints CLI output, optionally prints advice, and triggers shutdown.

    Error handling
    Propagates section execution or rendering failures to the caller.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._run_cli_mode`.

    Why this exists
    Interactive CLI behavior should stay outside the top-level entrypoint router.
    """
    host = console_host_type()
    code = run_sections_best_effort_fn(host, runtime.logger, runtime.context)
    print_console_output_fn(host)
    if bool(args.advice):
        print_cli_advice_fn(host)
    if args.fail_on and should_fail_on_host_fn(host, str(args.fail_on)):
        code = 1
    return finish_mode_fn(runtime.shutdown, code)


def run_gui_mode(
    args: argparse.Namespace,
    runtime: _RuntimeStateProtocol,
    *,
    run_gui_fallback_mode_fn: Callable[[argparse.Namespace, _RuntimeStateProtocol, Exception], int],
) -> int:
    """
    Summary
    Start the GUI when available, falling back to CLI when the GUI stack cannot load.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.
    run_gui_fallback_mode_fn: GUI fallback callback.

    Outputs
    GUI or CLI fallback exit code.

    Side effects
    Starts the GUI app or runs the CLI fallback path.

    Error handling
    Propagates contextual runtime errors from the selected path.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._run_gui_mode`.

    Why this exists
    GUI availability depends on the local environment, so import/startup handling should stay isolated.
    """
    try:
        from mac_health_checkup.app.gui.app import DashboardApp

        app = DashboardApp()
    except (ImportError, RuntimeError) as exc:
        return run_gui_fallback_mode_fn(args, runtime, exc)
    start_fn = getattr(app, "start")
    start_fn()
    return 0


def run_gui_fallback_mode(
    args: argparse.Namespace,
    runtime: _RuntimeStateProtocol,
    exc: Exception,
    *,
    console_host_type: type[ConsoleHost],
    run_sections_best_effort_fn: Callable[[ConsoleHost, StructuredLogger | None, LogContext | None], int],
    print_console_output_fn: Callable[[ConsoleHost], None],
    print_cli_advice_fn: Callable[[ConsoleHost], None],
    should_fail_on_host_fn: Callable[[ConsoleHost, str], bool],
    finish_mode_fn: Callable[[_ShutdownManagerProtocol, int], int],
) -> int:
    """
    Summary
    Fall back to CLI mode when GUI startup is unavailable.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.
    exc: GUI import or startup exception.
    console_host_type: Console host constructor.
    run_sections_best_effort_fn: Section runner callback.
    print_console_output_fn: Console output callback.
    print_cli_advice_fn: Advice renderer callback.
    should_fail_on_host_fn: Fail-policy callback.
    finish_mode_fn: Shutdown completion callback.

    Outputs
    CLI fallback exit code.

    Side effects
    Logs the GUI failure, runs collectors through the CLI host, prints output, and triggers shutdown.

    Error handling
    Propagates contextual runtime errors from the fallback CLI path.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._run_gui_fallback_mode`.

    Why this exists
    GUI fallback needs explicit behavior distinct from the main CLI mode.
    """
    runtime.logger.warning(
        "tkinter unavailable, falling back to CLI",
        event="gui_unavailable",
        context=runtime.context,
        payload={"error": str(exc)},
    )
    host = console_host_type()
    code = run_sections_best_effort_fn(host, None, None)
    print_console_output_fn(host)
    if bool(args.advice):
        print_cli_advice_fn(host)
    if args.fail_on and should_fail_on_host_fn(host, str(args.fail_on)):
        code = 1
    return finish_mode_fn(runtime.shutdown, code)
