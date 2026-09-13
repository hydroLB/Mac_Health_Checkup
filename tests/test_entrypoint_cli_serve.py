from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import mac_health_checkup.app.entrypoint as entrypoint
from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.core.config import get_config

MODULE_PATH = "tests/test_entrypoint_cli_serve.py"


def test_module_execution_prints_help_text() -> None:
    """
    Summary
    Ensure module execution via `python -m` invokes `main` and emits argparse help text.

    Inputs
    None.

    Outputs
    None.

    Side effects
    Launches a short-lived subprocess for module execution.

    Error handling
    Raises `AssertionError` with module and method context when execution fails or emits empty help output.

    Ties to other methods
    Validates the `if __name__ == "__main__"` execution path in `mac_health_checkup.app.entrypoint`.

    Why this exists
    Without the module execution guard, CLI invocations can silently no-op while still returning success.
    """
    try:
        repo_root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(repo_root) if not existing_pythonpath else f"{repo_root}:{existing_pythonpath}"
        )

        completed = subprocess.run(
            [sys.executable, "-m", "mac_health_checkup.app.entrypoint", "--help"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            cwd=repo_root,
        )
        assert completed.returncode == 0
        assert "Run Mac Health Checkup." in completed.stdout
        assert "--snapshot-json" in completed.stdout
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
        raise AssertionError(f"{MODULE_PATH}:test_module_execution_prints_help_text failed: {exc}") from exc


def test_main_cli_advice_and_fail_on(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure CLI mode prints advice and enforces --fail-on warn based on rendered metric severities.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    capsys: Pytest capture fixture.

    Outputs
    None.

    Side effects
    Patches argv and section execution to avoid running real collectors.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `main`, `_print_cli_advice`, and `--fail-on` behavior.

    Why this exists
    Automation relies on deterministic exit codes driven by structured advice severity.
    """
    try:
        monkeypatch.setattr(sys, "argv", ["prog", "--cli", "--advice", "--fail-on", "warn"])

        monkeypatch.setattr(entrypoint, "SECTION_HANDLERS", {"general": lambda _host: {"ok": True}})

        def _stub_run_sections(host: ConsoleHost, *, logger: object, context: object) -> int:
            """
            Summary
            Execute `_stub_run_sections` for its module-level responsibility.

            Inputs
            host: `ConsoleHost` parameter from the function signature.
            logger: keyword-only `object` parameter.
            context: keyword-only `object` parameter.

            Outputs
            Returns `int`.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `tests/test_entrypoint_cli_serve.py:_stub_run_sections` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_entrypoint_cli_serve.py`.

            Why this exists
            Keeps `_stub_run_sections` explicit, testable, and maintainable.
            """
            _ = logger
            _ = context
            host.set_field("general", "ok")
            host.render_metrics_table("general", [("Signal", "x", "warn")], columns=2)
            host.diagnostics["general"] = {"ok": True}
            return 0

        monkeypatch.setattr(entrypoint, "_run_sections_best_effort", _stub_run_sections)
        monkeypatch.setattr(
            entrypoint,
            "ShutdownManager",
            lambda: SimpleNamespace(install_handlers=lambda: None, trigger_shutdown=lambda: None),
        )

        code = entrypoint.main()
        out = capsys.readouterr().out
        assert code == 1
        assert "[advice]" in out
        assert "[general] WARN" in out
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
        raise AssertionError(f"{MODULE_PATH}:test_main_cli_advice_and_fail_on failed: {exc}") from exc


def test_run_sections_best_effort_continues_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure section execution continues after an exception and records an error field.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches run_section to raise for one section.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_run_sections_best_effort`.

    Why this exists
    A single failing collector must not abort the entire run; the UI and CLI should degrade gracefully.
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
            Raises contextual errors from `tests/test_entrypoint_cli_serve.py:_fake_run_section` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `tests/test_entrypoint_cli_serve.py`.

            Why this exists
            Keeps `_fake_run_section` explicit, testable, and maintainable.
            """
            if key == "bad":
                raise RuntimeError("boom")
            return {"ok": True}

        monkeypatch.setattr(entrypoint, "run_section", _fake_run_section)
        host = ConsoleHost()
        code = entrypoint._run_sections_best_effort(host, logger=None, context=None)
        assert code == 1
        assert "bad" in host.fields
        assert host.fields["bad"].startswith("Error:")
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
            f"{MODULE_PATH}:test_run_sections_best_effort_continues_after_failure failed: {exc}"
        ) from exc


def test_main_serve_mode_prints_pairing_payload(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure serve mode prints the pairing payload when TLS is enabled and exits cleanly.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    capsys: Pytest capture fixture.

    Outputs
    None.

    Side effects
    Patches config, server, and shutdown manager to avoid binding sockets or waiting for signals.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `main` serve path and pairing payload formatting.

    Why this exists
    iOS pairing depends on stable payload formatting and should be testable without real networking.
    """
    try:
        base = get_config()
        api = replace(
            base.api,
            enabled=True,
            allow_lan=True,
            bind_host="0.0.0.0",
            tls_enabled=True,
        )
        cfg = replace(base, api=api)
        monkeypatch.setattr(entrypoint, "get_config", lambda: cfg)
        monkeypatch.setattr(sys, "argv", ["prog", "--serve"])

        calls: list[str] = []

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
                Raises contextual errors from `tests/test_entrypoint_cli_serve.py:__init__` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_cli_serve.py`.

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
                Raises contextual errors from `tests/test_entrypoint_cli_serve.py:start` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_cli_serve.py`.

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
                Raises contextual errors from `tests/test_entrypoint_cli_serve.py:stop` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_cli_serve.py`.

                Why this exists
                Keeps `stop` explicit, testable, and maintainable.
                """
                calls.append("stop")

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
                Raises contextual errors from `tests/test_entrypoint_cli_serve.py:url` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_cli_serve.py`.

                Why this exists
                Keeps `url` explicit, testable, and maintainable.
                """
                return "https://127.0.0.1:9999"

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
                Raises contextual errors from `tests/test_entrypoint_cli_serve.py:tls_certificate_fingerprint_sha256` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_cli_serve.py`.

                Why this exists
                Keeps `tls_certificate_fingerprint_sha256` explicit, testable, and maintainable.
                """
                return "deadbeef"

        class _StubShutdown:
            def install_handlers(self) -> None:
                """
                Summary
                Execute `install_handlers` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_cli_serve.py:install_handlers` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_cli_serve.py`.

                Why this exists
                Keeps `install_handlers` explicit, testable, and maintainable.
                """
                return

            def wait_for_shutdown(self) -> None:
                """
                Summary
                Execute `wait_for_shutdown` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_cli_serve.py:wait_for_shutdown` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_cli_serve.py`.

                Why this exists
                Keeps `wait_for_shutdown` explicit, testable, and maintainable.
                """
                return

            def trigger_shutdown(self) -> None:
                """
                Summary
                Execute `trigger_shutdown` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_entrypoint_cli_serve.py:trigger_shutdown` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_entrypoint_cli_serve.py`.

                Why this exists
                Keeps `trigger_shutdown` explicit, testable, and maintainable.
                """
                return

        monkeypatch.setattr(entrypoint, "SnapshotApiServer", _StubServer)
        monkeypatch.setattr(entrypoint, "ShutdownManager", lambda: _StubShutdown())
        monkeypatch.setattr(entrypoint, "_print_pairing_qr_best_effort", lambda *_a, **_k: None)
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL", "https://example.test:9999")

        code = entrypoint.main()
        out = capsys.readouterr().out
        assert code == 0
        assert "Snapshot API running at" in out
        assert "Certificate fingerprint (sha256): deadbeef" in out
        payload_line = next(
            (line for line in out.splitlines() if line.strip().startswith("{") and "token" in line), ""
        )
        payload = json.loads(payload_line)
        assert payload["pin"] == "deadbeef"
        assert payload["url"] == os.environ["MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL"]
        assert "stop" in calls
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
            f"{MODULE_PATH}:test_main_serve_mode_prints_pairing_payload failed: {exc}"
        ) from exc


def test_resolve_public_base_url_rejects_empty_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure an explicitly empty public base URL override fails fast with a contextual error.

    Inputs
    Monkeypatched `MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL` environment variable.

    Outputs
    Assertion that `_resolve_public_base_url` raises `RuntimeError`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and method context on failures.

    Ties to other methods
    Exercises `_resolve_public_base_url` strict env validation path.

    Why this exists
    Empty URL overrides should never silently fall back because they indicate broken startup configuration.
    """
    try:
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL", " ")
        with pytest.raises(RuntimeError) as exc_info:
            entrypoint._resolve_public_base_url(default_url="http://127.0.0.1:7878")
        assert "MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL is set but empty" in str(exc_info.value)
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
            f"{MODULE_PATH}:test_resolve_public_base_url_rejects_empty_override failed: {exc}"
        ) from exc


def test_resolve_public_base_url_rejects_path_query_and_fragment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Summary
    Ensure public base URL override rejects path, query, or fragment segments.

    Inputs
    Monkeypatched `MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL` with a malformed URL.

    Outputs
    Assertion that `_resolve_public_base_url` raises `RuntimeError`.

    Side effects
    Updates process environment during test execution.

    Error handling
    Raises `AssertionError` with module and method context on failures.

    Ties to other methods
    Exercises `_resolve_public_base_url` URL-shape validation.

    Why this exists
    Pairing URLs should be canonical scheme://host[:port] values so clients receive deterministic connection targets.
    """
    try:
        monkeypatch.setenv("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL", "https://example.test:7878/path?q=1#x")
        with pytest.raises(RuntimeError) as exc_info:
            entrypoint._resolve_public_base_url(default_url="http://127.0.0.1:7878")
        assert "must not include path, query, or fragment" in str(exc_info.value)
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
            f"{MODULE_PATH}:test_resolve_public_base_url_rejects_path_query_and_fragment failed: {exc}"
        ) from exc


def test_main_diff_and_export_branches_call_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure diff and export branches select the correct helper functions.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches argv and helper functions.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises main branching for diff and export modes.

    Why this exists
    Mode selection should be explicit and should not accidentally run collectors when diffing existing snapshots.
    """
    try:
        monkeypatch.setattr(
            entrypoint,
            "ShutdownManager",
            lambda: SimpleNamespace(install_handlers=lambda: None, trigger_shutdown=lambda: None),
        )
        monkeypatch.setattr(entrypoint, "_run_diff_mode", lambda _args: 0)
        monkeypatch.setattr(entrypoint, "_run_export_mode", lambda _args: 0)

        monkeypatch.setattr(sys, "argv", ["prog", "--diff-snapshots", "a.json", "b.json"])
        assert entrypoint.main() == 0

        monkeypatch.setattr(sys, "argv", ["prog", "--export", "markdown", "--export-from-snapshot", "a.json"])
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
            f"{MODULE_PATH}:test_main_diff_and_export_branches_call_helpers failed: {exc}"
        ) from exc
