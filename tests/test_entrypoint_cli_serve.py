from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

import mac_health_checkup.app.entrypoint as entrypoint
from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.core.config import get_config

MODULE_PATH = "tests/test_entrypoint_cli_serve.py"


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
    except Exception as exc:
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
            if key == "bad":
                raise RuntimeError("boom")
            return {"ok": True}

        monkeypatch.setattr(entrypoint, "run_section", _fake_run_section)
        host = ConsoleHost()
        code = entrypoint._run_sections_best_effort(host, logger=None, context=None)
        assert code == 1
        assert "bad" in host.fields
        assert host.fields["bad"].startswith("Error:")
    except Exception as exc:
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
                return

            def start(self) -> None:
                return

            def stop(self) -> None:
                calls.append("stop")

            def url(self) -> str:
                return "https://127.0.0.1:9999"

            def tls_certificate_fingerprint_sha256(self) -> str | None:
                return "deadbeef"

        class _StubShutdown:
            def install_handlers(self) -> None:
                return

            def wait_for_shutdown(self) -> None:
                return

            def trigger_shutdown(self) -> None:
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
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_main_serve_mode_prints_pairing_payload failed: {exc}"
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
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_main_diff_and_export_branches_call_helpers failed: {exc}"
        ) from exc
