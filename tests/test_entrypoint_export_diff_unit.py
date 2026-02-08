from __future__ import annotations

import argparse
import builtins
import sys
import types
from pathlib import Path

import pytest

import mac_health_checkup.app.entrypoint as entrypoint
from mac_health_checkup.app.backend.snapshot import Snapshot, SnapshotSection, SnapshotTheme

MODULE_PATH = "tests/test_entrypoint_export_diff_unit.py"


def _snapshot_with_warn_section(*, ok: bool) -> Snapshot:
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


def test_run_diff_mode_prints_markdown(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure diff mode loads snapshots and prints rendered markdown to stdout.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    capsys: Pytest capture fixture.

    Outputs
    None.

    Side effects
    Patches report helpers to avoid file IO.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_run_diff_mode`.

    Why this exists
    Diff mode should not run collectors and should remain fast and deterministic.
    """
    try:
        monkeypatch.setattr("mac_health_checkup.app.reports.load_snapshot_from_path", lambda _p: object())
        monkeypatch.setattr("mac_health_checkup.app.reports.diff_snapshots", lambda _a, _b: {"diff": True})
        monkeypatch.setattr("mac_health_checkup.app.reports.render_diff_markdown", lambda _d: "DIFF\n")

        args = argparse.Namespace(diff_snapshots=("a.json", "b.json"))
        assert entrypoint._run_diff_mode(args) == 0
        out = capsys.readouterr().out
        assert out == "DIFF\n"
    except Exception as exc:
        raise AssertionError(f"{MODULE_PATH}:test_run_diff_mode_prints_markdown failed: {exc}") from exc


def test_run_export_mode_diff_snapshots_writes_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure export mode writes a diff report when --diff-snapshots is set.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    tmp_path: Temp directory path.
    capsys: Pytest capture fixture.

    Outputs
    None.

    Side effects
    Patches report helpers and file writes.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_run_export_mode` diff snapshot export branch.

    Why this exists
    Exported diff reports are a primary sharing workflow.
    """
    try:
        export_path = tmp_path / "diff.md"
        monkeypatch.setattr(entrypoint, "_resolve_export_path", lambda *_a, **_k: export_path)
        written: dict[str, str] = {}

        monkeypatch.setattr("mac_health_checkup.app.reports.load_snapshot_from_path", lambda _p: object())
        monkeypatch.setattr("mac_health_checkup.app.reports.diff_snapshots", lambda _a, _b: {"diff": True})
        monkeypatch.setattr("mac_health_checkup.app.reports.render_diff_markdown", lambda _d: "MD")
        monkeypatch.setattr("mac_health_checkup.app.reports.render_diff_html", lambda _d: "<html/>")

        def _write(path: Path, content: str) -> None:
            written[str(path)] = content

        monkeypatch.setattr(entrypoint, "_write_text_file", _write)

        args = argparse.Namespace(
            export="markdown",
            export_include_diagnostics=False,
            fail_on=None,
            export_path=None,
            diff_snapshots=("a.json", "b.json"),
            diff_against=None,
            export_from_snapshot=None,
        )
        assert entrypoint._run_export_mode(args) == 0
        assert written[str(export_path)] == "MD"
        assert capsys.readouterr().out.strip() == str(export_path)
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_run_export_mode_diff_snapshots_writes_file failed: {exc}"
        ) from exc


def test_run_export_mode_diff_against_uses_current_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Summary
    Ensure --diff-against exports a diff and returns 1 when the current snapshot is not ok.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    tmp_path: Temp directory path.

    Outputs
    None.

    Side effects
    Patches SnapshotBuilder and report helpers.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_run_export_mode` diff-against branch.

    Why this exists
    diff-against is intended for automation (baseline comparisons) and must propagate snapshot failure via exit code.
    """
    try:
        export_path = tmp_path / "diff.html"
        monkeypatch.setattr(entrypoint, "_resolve_export_path", lambda *_a, **_k: export_path)
        monkeypatch.setattr(entrypoint, "_write_text_file", lambda _p, _c: None)
        monkeypatch.setattr(
            "mac_health_checkup.app.reports.load_snapshot_from_path",
            lambda _p: _snapshot_with_warn_section(ok=True),
        )
        monkeypatch.setattr("mac_health_checkup.app.reports.diff_snapshots", lambda _a, _b: {"diff": True})
        monkeypatch.setattr("mac_health_checkup.app.reports.render_diff_markdown", lambda _d: "MD")
        monkeypatch.setattr("mac_health_checkup.app.reports.render_diff_html", lambda _d: "<html/>")

        current = _snapshot_with_warn_section(ok=False)

        class _StubBuilder:
            def __init__(self, _handlers: object) -> None:
                return

            def build(self) -> Snapshot:
                return current

        monkeypatch.setattr("mac_health_checkup.app.backend.snapshot.SnapshotBuilder", _StubBuilder)

        args = argparse.Namespace(
            export="html",
            export_include_diagnostics=False,
            fail_on=None,
            export_path=None,
            diff_snapshots=None,
            diff_against="baseline.json",
            export_from_snapshot=None,
        )
        assert entrypoint._run_export_mode(args) == 1
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_run_export_mode_diff_against_uses_current_snapshot failed: {exc}"
        ) from exc


def test_run_export_mode_export_from_snapshot_respects_fail_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Summary
    Ensure exporting from an existing snapshot applies --fail-on to the computed advice severity.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    tmp_path: Temp directory path.

    Outputs
    None.

    Side effects
    Patches rendering and file write behavior.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_run_export_mode` export-from-snapshot branch.

    Why this exists
    Exporting existing snapshots should still support automation gates without rerunning collectors.
    """
    try:
        export_path = tmp_path / "snap.md"
        monkeypatch.setattr(entrypoint, "_resolve_export_path", lambda *_a, **_k: export_path)
        monkeypatch.setattr(entrypoint, "_write_text_file", lambda _p, _c: None)
        monkeypatch.setattr(
            "mac_health_checkup.app.reports.load_snapshot_from_path",
            lambda _p: _snapshot_with_warn_section(ok=True),
        )
        monkeypatch.setattr(
            "mac_health_checkup.app.reports.render_snapshot_markdown", lambda _s, include_diagnostics: "MD"
        )
        monkeypatch.setattr(
            "mac_health_checkup.app.reports.render_snapshot_html", lambda _s, include_diagnostics: "<html/>"
        )

        args = argparse.Namespace(
            export="markdown",
            export_include_diagnostics=False,
            fail_on="warn",
            export_path=None,
            diff_snapshots=None,
            diff_against=None,
            export_from_snapshot="snap.json",
        )
        assert entrypoint._run_export_mode(args) == 1
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_run_export_mode_export_from_snapshot_respects_fail_on failed: {exc}"
        ) from exc


def test_resolve_export_path_default_uses_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure default export paths live under `.local/reports` and include a timestamp.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches time.strftime.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_resolve_export_path`.

    Why this exists
    Default exports should not clutter the repo root and should be deterministic for tests.
    """
    try:
        monkeypatch.setattr("mac_health_checkup.app.entrypoint.time.strftime", lambda _fmt: "20260205-120000")
        p = entrypoint._resolve_export_path("markdown", explicit_path=None, kind="snapshot")
        assert str(p).endswith(".local/reports/mac-health-checkup-snapshot-20260205-120000.md")
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_resolve_export_path_default_uses_timestamp failed: {exc}"
        ) from exc


def test_gui_success_path_starts_dashboard(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure GUI path instantiates DashboardApp and calls start when import succeeds.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches __import__ to provide a stub DashboardApp without requiring Tk.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises GUI happy path in `main`.

    Why this exists
    The entrypoint should prefer GUI mode when available.
    """
    try:
        monkeypatch.setattr(sys, "argv", ["prog"])
        monkeypatch.setattr(
            entrypoint, "ShutdownManager", lambda: types.SimpleNamespace(install_handlers=lambda: None)
        )
        started: list[str] = []

        stub_module = types.ModuleType("mac_health_checkup.app.gui.app")

        class _StubDashboard:
            def start(self) -> None:
                started.append("start")

        setattr(stub_module, "DashboardApp", _StubDashboard)
        real_import = builtins.__import__

        def _import(
            name: str,
            globals: dict[str, object] | None = None,
            locals: dict[str, object] | None = None,
            fromlist: tuple[str, ...] = (),
            level: int = 0,
        ) -> object:
            if name == "mac_health_checkup.app.gui.app":
                return stub_module
            return real_import(name, globals, locals, fromlist, level)

        monkeypatch.setattr(builtins, "__import__", _import)
        assert entrypoint.main() == 0
        assert started == ["start"]
    except Exception as exc:
        raise AssertionError(f"{MODULE_PATH}:test_gui_success_path_starts_dashboard failed: {exc}") from exc


def test_main_error_write_non_broken_pipe_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Summary
    Ensure top-level error handler returns 1 when stderr writes raise a non-BrokenPipe exception.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.

    Outputs
    None.

    Side effects
    Patches stderr.write.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `main` stderr generic exception path.

    Why this exists
    The entrypoint should not crash if stderr is unavailable; it should still return a failure exit code.
    """
    try:
        monkeypatch.setattr(sys, "argv", ["prog", "--diff-against", "/tmp/snap.json"])
        monkeypatch.setattr(
            entrypoint, "ShutdownManager", lambda: types.SimpleNamespace(install_handlers=lambda: None)
        )
        monkeypatch.setattr(sys.stderr, "write", lambda _s: (_ for _ in ()).throw(RuntimeError("no stderr")))
        assert entrypoint.main() == 1
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_main_error_write_non_broken_pipe_returns_one failed: {exc}"
        ) from exc


def test_print_pairing_qr_no_output_when_renderer_empty(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure QR printing returns early when the renderer returns an empty value.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    capsys: Pytest capture fixture.

    Outputs
    None.

    Side effects
    Patches the QR renderer to return an empty string.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_print_pairing_qr_best_effort` early return branch.

    Why this exists
    QR generation is optional; missing tooling should not produce noisy output.
    """
    try:
        monkeypatch.setattr(
            "mac_health_checkup.core.utils.qr.maybe_render_qr_ansiutf8", lambda _p, timeout_sec: ""
        )
        entrypoint._print_pairing_qr_best_effort("{}", enabled=True)
        assert capsys.readouterr().out == ""
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_print_pairing_qr_no_output_when_renderer_empty failed: {exc}"
        ) from exc
