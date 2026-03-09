from __future__ import annotations

import builtins
import json
import sys
import types
from dataclasses import replace
from pathlib import Path

import pytest

import mac_health_checkup.app.entrypoint as entrypoint
from mac_health_checkup.app.backend import Snapshot, SnapshotSection, SnapshotTheme
from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.loggers import LogContext, LoggingFields, StructuredLogger

MODULE_PATH = "tests/test_entrypoint_internal_coverage.py"


def _snapshot_with_warn_section(*, ok: bool) -> Snapshot:
    """
    Summary
    Execute `_snapshot_with_warn_section` for its module-level responsibility.

    Inputs
    ok: keyword-only `bool` parameter.

    Outputs
    Returns `Snapshot`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:_snapshot_with_warn_section` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

    Why this exists
    Keeps `_snapshot_with_warn_section` explicit, testable, and maintainable.
    """
    return Snapshot(
        schema_version=2,
        generated_at_unix_ms=0,
        theme=SnapshotTheme(ui={}, colors={}, fonts={}, gui={}),
        section_catalog=[],
        sections=[
            SnapshotSection(
                key="general",
                field="ok",
                metrics=[("Signal", "x", "warn")],
                table=None,
                diagnostics={"ok": True},
            )
        ],
        ok=ok,
        error=None,
    )


def test_snapshot_json_out_fail_on_warn_sets_exit_code(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Summary
    Ensure --fail-on warn overrides snapshot ok and returns exit code 1 when advice severity is warn.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    tmp_path: Temp directory path.

    Outputs
    None.

    Side effects
    Writes a temp snapshot file and patches SnapshotBuilder.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises snapshot_json_out fail-on path in `main`.

    Why this exists
    CI automation relies on exit codes, not parsing output.
    """
    try:
        out_path = tmp_path / "snap.json"
        snap = _snapshot_with_warn_section(ok=True)

        class _StubBuilder:
            def __init__(self, _handlers: object) -> None:
                """
                Summary
                Execute `__init__` for its module-level responsibility.

                Inputs
                _handlers: `object` parameter from the function signature.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:__init__` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

                Why this exists
                Keeps `__init__` explicit, testable, and maintainable.
                """
                return

            def build(self) -> Snapshot:
                """
                Summary
                Execute `build` for its module-level responsibility.

                Inputs
                None.

                Outputs
                Returns `Snapshot`.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:build` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

                Why this exists
                Keeps `build` explicit, testable, and maintainable.
                """
                return snap

        monkeypatch.setattr(sys, "argv", ["prog", "--snapshot-json-out", str(out_path), "--fail-on", "warn"])
        monkeypatch.setattr(
            entrypoint,
            "ShutdownManager",
            lambda: types.SimpleNamespace(install_handlers=lambda: None, trigger_shutdown=lambda: None),
        )
        monkeypatch.setattr("mac_health_checkup.app.entrypoint.SnapshotBuilder", _StubBuilder)

        code = entrypoint.main()
        assert code == 1
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        assert payload.get("ok") is True
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_snapshot_json_out_fail_on_warn_sets_exit_code failed: {exc}"
        ) from exc


def test_snapshot_json_broken_pipe_returns_code(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure snapshot stdout mode handles BrokenPipeError and returns a deterministic code.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches print to raise BrokenPipeError.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises snapshot_json BrokenPipeError handling in `main`.

    Why this exists
    Snapshot mode is frequently piped to other tools; broken pipes should not crash the process.
    """
    try:
        snap = _snapshot_with_warn_section(ok=False)

        class _StubBuilder:
            def __init__(self, _handlers: object) -> None:
                """
                Summary
                Execute `__init__` for its module-level responsibility.

                Inputs
                _handlers: `object` parameter from the function signature.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:__init__` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

                Why this exists
                Keeps `__init__` explicit, testable, and maintainable.
                """
                return

            def build(self) -> Snapshot:
                """
                Summary
                Execute `build` for its module-level responsibility.

                Inputs
                None.

                Outputs
                Returns `Snapshot`.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:build` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

                Why this exists
                Keeps `build` explicit, testable, and maintainable.
                """
                return snap

        monkeypatch.setattr(sys, "argv", ["prog", "--snapshot-json"])
        monkeypatch.setattr(
            entrypoint,
            "ShutdownManager",
            lambda: types.SimpleNamespace(install_handlers=lambda: None, trigger_shutdown=lambda: None),
        )
        monkeypatch.setattr("mac_health_checkup.app.entrypoint.SnapshotBuilder", _StubBuilder)
        monkeypatch.setattr(builtins, "print", lambda _s: (_ for _ in ()).throw(BrokenPipeError()))

        assert entrypoint.main() == 1
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_snapshot_json_broken_pipe_returns_code failed: {exc}"
        ) from exc


def test_serve_mode_lan_tls_disabled_warns(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure LAN mode with TLS disabled prints a warning and still runs.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    capsys: Pytest capture fixture.

    Outputs
    None.

    Side effects
    Patches config and server to avoid network binds.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises serve mode LAN warning branch.

    Why this exists
    Operators need an explicit warning when insecure HTTP is used on LAN.
    """
    try:
        base = get_config()
        api = replace(
            base.api,
            enabled=True,
            allow_lan=True,
            bind_host="0.0.0.0",
            tls_enabled=False,
            allow_insecure_http_lan=True,
        )
        cfg = replace(base, api=api)
        monkeypatch.setattr(entrypoint, "get_config", lambda: cfg)
        monkeypatch.setattr(sys, "argv", ["prog", "--serve"])
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL", "http://public.test:9999")

        class _StubServer:
            def __init__(self, _handlers: object, _api: object) -> None:
                """
                Summary
                Execute `__init__` for its module-level responsibility.

                Inputs
                _handlers: `object` parameter from the function signature.
                _api: `object` parameter from the function signature.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:__init__` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

                Why this exists
                Keeps `__init__` explicit, testable, and maintainable.
                """
                return

            def start(self) -> None:
                """
                Summary
                Execute `start` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:start` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

                Why this exists
                Keeps `start` explicit, testable, and maintainable.
                """
                return

            def stop(self) -> None:
                """
                Summary
                Execute `stop` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:stop` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

                Why this exists
                Keeps `stop` explicit, testable, and maintainable.
                """
                return

            def url(self) -> str:
                """
                Summary
                Execute `url` for its module-level responsibility.

                Inputs
                None.

                Outputs
                Returns `str`.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:url` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

                Why this exists
                Keeps `url` explicit, testable, and maintainable.
                """
                return "http://127.0.0.1:9999"

            def tls_certificate_fingerprint_sha256(self) -> str | None:
                """
                Summary
                Execute `tls_certificate_fingerprint_sha256` for its module-level responsibility.

                Inputs
                None.

                Outputs
                Returns `str | None`.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:tls_certificate_fingerprint_sha256` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

                Why this exists
                Keeps `tls_certificate_fingerprint_sha256` explicit, testable, and maintainable.
                """
                return None

        monkeypatch.setattr(entrypoint, "SnapshotApiServer", _StubServer)
        monkeypatch.setattr(
            entrypoint,
            "ShutdownManager",
            lambda: types.SimpleNamespace(
                install_handlers=lambda: None, wait_for_shutdown=lambda: None, trigger_shutdown=lambda: None
            ),
        )

        assert entrypoint.main() == 0
        out = capsys.readouterr().out
        assert "Public base URL:" in out
        assert "Warning: TLS is disabled." in out
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_serve_mode_lan_tls_disabled_warns failed: {exc}") from exc


def test_serve_mode_requires_api_enabled(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure serve mode fails when api.enabled is false in config.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    capsys: Pytest capture fixture.

    Outputs
    None.

    Side effects
    Patches argv.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises serve mode config guard.

    Why this exists
    The server boundary should fail early with actionable config guidance.
    """
    try:
        monkeypatch.setattr(sys, "argv", ["prog", "--serve"])
        monkeypatch.setattr(
            entrypoint, "ShutdownManager", lambda: types.SimpleNamespace(install_handlers=lambda: None)
        )
        assert entrypoint.main() == 1
        err = capsys.readouterr().err
        assert "api.enabled must be true" in err
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_serve_mode_requires_api_enabled failed: {exc}") from exc


def test_gui_import_failure_falls_back_to_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure GUI import errors fall back to CLI mode.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches __import__ to fail for DashboardApp only.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises GUI-unavailable fallback branch.

    Why this exists
    Some Python installs lack Tk; the entrypoint should still provide useful output.
    """
    try:
        monkeypatch.setattr(sys, "argv", ["prog"])
        monkeypatch.setattr(
            entrypoint,
            "ShutdownManager",
            lambda: types.SimpleNamespace(install_handlers=lambda: None, trigger_shutdown=lambda: None),
        )
        monkeypatch.setattr(entrypoint, "_run_sections_best_effort", lambda _host, *, logger, context: 0)

        real_import = builtins.__import__

        def _import(
            name: str,
            globals: dict[str, object] | None = None,
            locals: dict[str, object] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            """
            Summary
            Execute `_import` for its module-level responsibility.

            Inputs
            name: `str` parameter from the function signature.
            globals: `dict[str, object] | None` parameter from the function signature with a default.
            locals: `dict[str, object] | None` parameter from the function signature with a default.
            fromlist: `tuple[str, ...]` parameter from the function signature with a default.
            level: `int` parameter from the function signature with a default.

            Outputs
            Returns `object`.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:_import` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

            Why this exists
            Keeps `_import` explicit, testable, and maintainable.
            """
            if name == "mac_health_checkup.app.gui.app" and fromlist and "DashboardApp" in fromlist:
                raise ImportError("no tkinter")
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _import)
        assert entrypoint.main() == 0
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_gui_import_failure_falls_back_to_cli failed: {exc}"
        ) from exc


def test_main_error_write_broken_pipe_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure top-level error reporting handles BrokenPipeError from stderr writes.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches stderr.write and argv to trigger a controlled exception.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises main exception handler stderr BrokenPipeError path.

    Why this exists
    In some environments stderr may be piped to a consumer that closes early; the process should still exit cleanly.
    """
    try:
        monkeypatch.setattr(sys, "argv", ["prog", "--diff-against", "/tmp/snap.json"])
        monkeypatch.setattr(
            entrypoint, "ShutdownManager", lambda: types.SimpleNamespace(install_handlers=lambda: None)
        )
        monkeypatch.setattr(sys.stderr, "write", lambda _s: (_ for _ in ()).throw(BrokenPipeError()))
        assert entrypoint.main() == 1
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_main_error_write_broken_pipe_returns_one failed: {exc}"
        ) from exc


def test_print_console_output_prints_tables(capsys: pytest.CaptureFixture[str]) -> None:
    """
    Summary
    Ensure CLI console output includes table headers and rows when present.

    Inputs
    capsys: Pytest capture fixture.

    Outputs
    None.

    Side effects
    Writes to stdout.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_print_console_output` table printing branch.

    Why this exists
    Tables are a key part of the CLI output and should be included in exports and automation logs.
    """
    try:
        host = ConsoleHost()
        host.render_table("devices", ("Bus", "Device"), [("usb", "Keyboard")])
        entrypoint._print_console_output(host)
        out = capsys.readouterr().out
        assert "[devices table]" in out
        assert "Bus | Device" in out
        assert "usb | Keyboard" in out
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_print_console_output_prints_tables failed: {exc}") from exc


def test_print_pairing_qr_best_effort(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure QR printing emits nothing when disabled and prints when the renderer returns a QR string.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    capsys: Pytest capture fixture.

    Outputs
    None.

    Side effects
    Patches the QR renderer.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_print_pairing_qr_best_effort`.

    Why this exists
    QR output is optional and should be best-effort without adding hard dependencies.
    """
    try:
        entrypoint._print_pairing_qr_best_effort("{}", enabled=False)
        assert capsys.readouterr().out == ""

        monkeypatch.setattr(
            "mac_health_checkup.core.utils.maybe_render_qr_ansiutf8",
            lambda _payload, timeout_sec: "QR",
        )
        entrypoint._print_pairing_qr_best_effort("{}", enabled=True)
        out = capsys.readouterr().out
        assert "Pairing QR" in out
        assert "QR" in out
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_print_pairing_qr_best_effort failed: {exc}") from exc


def test_run_sections_best_effort_emits_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure section runner emits structured logs on start/end/error when logger and context are provided.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches SECTION_HANDLERS and run_section.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises logging branches in `_run_sections_best_effort`.

    Why this exists
    Structured logs are critical for automation and debugging.
    """
    try:
        monkeypatch.setattr(
            entrypoint,
            "SECTION_HANDLERS",
            {"ok": lambda _host: {"ok": True}, "bad": lambda _host: {"ok": False}},
        )

        def _fake_run_section(_host: ConsoleHost, key: str) -> dict[str, object]:
            """
            Summary
            Execute `_fake_run_section` for its module-level responsibility.

            Inputs
            _host: `ConsoleHost` parameter from the function signature.
            key: `str` parameter from the function signature.

            Outputs
            Returns `dict[str, object]`.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:_fake_run_section` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

            Why this exists
            Keeps `_fake_run_section` explicit, testable, and maintainable.
            """
            if key == "bad":
                raise RuntimeError("boom")
            return {"ok": True}

        monkeypatch.setattr(entrypoint, "run_section", _fake_run_section)
        host = ConsoleHost()
        events: list[str] = []
        cfg = get_config()
        fields = LoggingFields(
            event_field=cfg.logging.event_field,
            corr_id_field=cfg.logging.correlation_id_field,
            component_field=cfg.logging.component_field,
        )
        logger = StructuredLogger("test", cfg.logging.redaction(), fields)
        context = LogContext(component="test", corr_id="corr")

        def _info(_msg: str, *, event: str, context: LogContext, payload: dict[str, object]) -> None:
            """
            Summary
            Execute `_info` for its module-level responsibility.

            Inputs
            _msg: `str` parameter from the function signature.
            event: keyword-only `str` parameter.
            context: keyword-only `LogContext` parameter.
            payload: keyword-only `dict[str, object]` parameter.

            Outputs
            None.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:_info` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

            Why this exists
            Keeps `_info` explicit, testable, and maintainable.
            """
            _ = context
            _ = payload
            events.append(event)

        def _error(_msg: str, *, event: str, context: LogContext, payload: dict[str, object]) -> None:
            """
            Summary
            Execute `_error` for its module-level responsibility.

            Inputs
            _msg: `str` parameter from the function signature.
            event: keyword-only `str` parameter.
            context: keyword-only `LogContext` parameter.
            payload: keyword-only `dict[str, object]` parameter.

            Outputs
            None.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `tests/test_entrypoint_internal_coverage.py:_error` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_entrypoint_internal_coverage.py`.

            Why this exists
            Keeps `_error` explicit, testable, and maintainable.
            """
            _ = context
            _ = payload
            events.append(event)

        monkeypatch.setattr(logger, "info", _info)
        monkeypatch.setattr(logger, "error", _error)

        assert entrypoint._run_sections_best_effort(host, logger=logger, context=context) == 1
        assert "section_start" in events
        assert "section_end" in events
        assert "section_error" in events
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_run_sections_best_effort_emits_logs failed: {exc}") from exc
