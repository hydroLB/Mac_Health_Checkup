from __future__ import annotations

from collections.abc import Iterable

from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/entrypoint.py"


def print_console_output(host: ConsoleHost) -> None:
    """
    Summary
    Print rendered section output to stdout for CLI mode.

    Inputs
    host: ConsoleHost holding fields, metrics, and tables.

    Outputs
    None.

    Side effects
    Writes to stdout.

    Error handling
    Raises `RuntimeError` with module and method context if printing fails.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._print_console_output`.

    Why this exists
    Provides a readable CLI summary without requiring a GUI.
    """
    try:
        _print_fields(host)
        _print_metrics(host)
        _print_tables(host)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_print_console_output", "Failed to print output", exc)
        ) from exc


def print_cli_advice(host: ConsoleHost, *, section_keys: Iterable[str]) -> None:
    """
    Summary
    Print per-section diagnosis and recommended next steps for CLI mode.

    Inputs
    host: ConsoleHost containing rendered fields, metrics, and captured diagnostics.
    section_keys: Ordered section keys to evaluate.

    Outputs
    None.

    Side effects
    Writes to stdout.

    Error handling
    Raises `RuntimeError` with module and method context when printing fails.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._print_cli_advice`.

    Why this exists
    Actionability belongs next to the rendered snapshot so users can move directly from signals to next steps.
    """
    try:
        from mac_health_checkup.app.actionability import build_section_advice

        print("\n[advice]")
        for key in section_keys:
            advice = build_section_advice(
                key,
                field=host.fields.get(key),
                metrics=host.metrics.get(key),
                diagnostics=host.diagnostics.get(key),
            )
            _print_advice_section(key, advice)
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_print_cli_advice", "Failed to print advice", exc)
        ) from exc


def print_pairing_qr_best_effort(pairing_payload: str, *, enabled: bool) -> None:
    """
    Summary
    Print a pairing QR code best-effort for the iOS client when enabled and supported.

    Inputs
    pairing_payload: Compact JSON payload used by the iOS app.
    enabled: Whether QR output is enabled via config.

    Outputs
    None.

    Side effects
    May execute `qrencode` and writes to stdout.

    Error handling
    Never raises; emits nothing on failure.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._print_pairing_qr_best_effort`.

    Why this exists
    Pairing via QR reduces manual typing of tokens on mobile devices.
    """
    try:
        if not enabled:
            return
        from mac_health_checkup.core.utils import maybe_render_qr_ansiutf8

        qr = maybe_render_qr_ansiutf8(pairing_payload, timeout_sec=3)
        if not qr:
            return
        print()
        print("Pairing QR (scan in iOS app):")
        print(qr)
        print()
    except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, OSError):
        return


def _print_fields(host: ConsoleHost) -> None:
    """
    Summary
    Print simple section summary fields.

    Inputs
    host: ConsoleHost holding field values.

    Outputs
    None.

    Side effects
    Writes summary lines to stdout.

    Error handling
    Propagates printing failures to the caller.

    Ties to other methods
    Used by `print_console_output`.

    Why this exists
    Fields are the top-level CLI summary and should render before tables and metrics.
    """
    for key, value in host.fields.items():
        print(f"[{key}] {value}")


def _print_metrics(host: ConsoleHost) -> None:
    """
    Summary
    Print metrics sections from the console host.

    Inputs
    host: ConsoleHost holding metrics rows.

    Outputs
    None.

    Side effects
    Writes metrics blocks to stdout.

    Error handling
    Propagates printing failures to the caller.

    Ties to other methods
    Used by `print_console_output`.

    Why this exists
    Metrics deserve a dedicated rendering pass to keep the console layout predictable.
    """
    for key, metric_rows in host.metrics.items():
        print(f"\n[{key} metrics]")
        for label, value, status in metric_rows:
            print(f"- {label}: {value} ({status})")


def _print_tables(host: ConsoleHost) -> None:
    """
    Summary
    Print tabular sections from the console host.

    Inputs
    host: ConsoleHost holding table rows and headers.

    Outputs
    None.

    Side effects
    Writes table blocks to stdout.

    Error handling
    Propagates printing failures to the caller.

    Ties to other methods
    Used by `print_console_output`.

    Why this exists
    Tables have a distinct rendering shape and are easier to debug when isolated from other output types.
    """
    for key, table_rows in host.tables.items():
        print(f"\n[{key} table]")
        headers = host.headers.get(key)
        if headers:
            print(" | ".join(headers))
        for row in table_rows:
            print(" | ".join(row))


def _print_advice_section(key: str, advice: object) -> None:
    """
    Summary
    Print one advice block for a section.

    Inputs
    key: Section key.
    advice: Advice payload returned by `build_section_advice`.

    Outputs
    None.

    Side effects
    Writes one advice block to stdout.

    Error handling
    Propagates payload shape or printing failures to the caller.

    Ties to other methods
    Used by `print_cli_advice`.

    Why this exists
    Section-by-section advice formatting should live in one place so CLI output stays uniform.
    """
    severity = str(getattr(advice, "get", lambda _k, _d=None: _d)("severity", "ok")).upper()
    diagnosis = str(getattr(advice, "get", lambda _k, _d=None: _d)("diagnosis", "")).strip()
    steps = getattr(advice, "get", lambda _k, _d=None: _d)("next_steps")
    print(f"\n[{key}] {severity}")
    if diagnosis:
        print(diagnosis)
    if isinstance(steps, list):
        for step in steps:
            text = str(step).strip()
            if text:
                print(f"- {text}")
