from __future__ import annotations

import argparse
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from mac_health_checkup.app.backend import (
    Snapshot,
    SnapshotSection,
    SnapshotSectionDescriptor,
    SnapshotTable,
    SnapshotTheme,
)
from mac_health_checkup.app.entrypoint_support.args import _build_parser
from mac_health_checkup.app.entrypoint_support.export_mode import run_export_mode, write_text_file
from mac_health_checkup.app.entrypoint_support.modes import (
    _RuntimeStateProtocol,
    run_snapshot_json_mode,
    serialize_snapshot,
)
from mac_health_checkup.app.reports import redact_snapshot_sensitive
from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_snapshot_redaction.py"


def _sensitive_snapshot() -> Snapshot:
    """
    Summary
    Build a representative snapshot containing each supported sensitive value category.

    Inputs
    None.

    Outputs
    Snapshot with serial, SSID, IPv4/IPv6, PID, process path, and raw diagnostics values.

    Side effects
    None.

    Error handling
    Raises constructor errors when the test fixture shape is invalid.

    Ties to other methods
    Used by safe-share redaction and output integration tests in this module.

    Why this exists
    A single realistic fixture proves the redactor handles UI-facing fields, metrics, tables, nested diagnostics, and
    raw blobs consistently.
    """
    general_diagnostics = cast(
        JsonDict,
        {
            "serial": "C02SECRET123",
            "raw": "Serial Number (system): C02SECRET123",
        },
    )
    network_diagnostics = cast(
        JsonDict,
        {
            "ssid": "Home Secret Network",
            "ipv4": "192.168.50.23",
            "ipv6": "fd00::1234",
            "nested": {"gateway": "192.168.50.1"},
        },
    )
    process_diagnostics = cast(
        JsonDict,
        {
            "top_cpu": [
                {
                    "pid": 4242,
                    "cpu_percent": 18.2,
                    "command": "/Users/alice/Projects/private/secret-tool",
                }
            ],
            "raw_cpu": "4242 18.2 1.1 /Users/alice/Projects/private/secret-tool",
        },
    )
    return Snapshot(
        schema_version=2,
        generated_at_unix_ms=0,
        theme=SnapshotTheme(ui={"title": "Test"}, colors={}, fonts={}, gui={}),
        section_catalog=[
            SnapshotSectionDescriptor(title="General", subtitle="Model", key="general"),
            SnapshotSectionDescriptor(title="Network", subtitle="Connectivity", key="network"),
            SnapshotSectionDescriptor(title="Processes", subtitle="Top CPU / MEM", key="processes"),
        ],
        sections=[
            SnapshotSection(
                key="general",
                field="MacBook Pro | M3 Pro | macOS 15.5 | C02SECRET123",
                metrics=None,
                table=None,
                diagnostics=general_diagnostics,
            ),
            SnapshotSection(
                key="network",
                field="Wi‑Fi  •  Home Secret Network  •  192.168.50.23  •  ↓ 75.0 Mbps",
                metrics=[
                    ("SSID", "Home Secret Network", "info"),
                    ("IPv4", "192.168.50.23", "info"),
                    ("IPv6", "fd00::1234", "info"),
                    ("Down (live)", "75.0 Mbps", "info"),
                ],
                table=None,
                diagnostics=network_diagnostics,
            ),
            SnapshotSection(
                key="processes",
                field="Top offenders (rows: 2)",
                metrics=None,
                table=SnapshotTable(
                    headers=("Type", "PID", "CPU%", "MEM%", "Command"),
                    rows=[
                        (
                            "CPU",
                            "4242",
                            "18.2",
                            "1.1",
                            "/Users/alice/Projects/private/secret-tool",
                        ),
                        ("MEM", "1", "1.0", "2.0", "kernel_task"),
                    ],
                ),
                diagnostics=process_diagnostics,
            ),
        ],
        ok=True,
        error=None,
    )


def test_redact_snapshot_sensitive_is_deterministic_and_does_not_mutate_source() -> None:
    """
    Summary
    Verify safe-share redaction covers known sensitive surfaces without mutating its source.

    Inputs
    Representative sensitive snapshot fixture.

    Outputs
    Assertions on deterministic JSON, retained table shape, placeholders, and source equality.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with test context when a sensitive value leaks or structure changes unexpectedly.

    Ties to other methods
    Exercises `redact_snapshot_sensitive` directly.

    Why this exists
    Safe-share output must be repeatable and trustworthy while leaving cached or live snapshot objects untouched for
    the UI and automation policy evaluation.
    """
    try:
        snapshot = _sensitive_snapshot()
        source_json = snapshot.to_json(pretty=False)

        first = redact_snapshot_sensitive(snapshot)
        second = redact_snapshot_sensitive(snapshot)
        redacted_json = first.to_json(pretty=False)

        assert first is not snapshot
        assert redacted_json == second.to_json(pretty=False)
        assert snapshot.to_json(pretty=False) == source_json
        for sensitive_value in (
            "C02SECRET123",
            "Home Secret Network",
            "192.168.50.23",
            "192.168.50.1",
            "fd00::1234",
            '"4242"',
            "/Users/alice/Projects/private/secret-tool",
        ):
            assert sensitive_value not in redacted_json

        assert "[REDACTED: serial]" in redacted_json
        assert "[REDACTED: SSID]" in redacted_json
        assert "[REDACTED: IP address]" in redacted_json
        assert "[REDACTED: PID]" in redacted_json
        assert "[REDACTED: raw diagnostics]" in redacted_json

        sections = {section.key: section for section in first.sections}
        process_table = sections["processes"].table
        assert process_table is not None
        assert process_table.headers == ("Type", "PID", "CPU%", "MEM%", "Command")
        assert len(process_table.rows) == 2
        assert process_table.rows[0][4] == "[REDACTED: process path]/secret-tool"
        assert process_table.rows[1][4] == "kernel_task"
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
            f"{MODULE_PATH}:test_redact_snapshot_sensitive_is_deterministic_and_does_not_mutate_source failed: {exc}"
        ) from exc


@pytest.mark.parametrize("format_name", ["markdown", "html"])
def test_export_mode_redacts_markdown_and_html_when_enabled(
    format_name: str,
    tmp_path: Path,
) -> None:
    """
    Summary
    Verify the export CLI path applies safe-share redaction to Markdown and HTML artifacts.

    Inputs
    Parametrized export format and temporary output directory.

    Outputs
    Assertions that exported content contains placeholders and no original sensitive values.

    Side effects
    Writes one temporary report file and prints its path.

    Error handling
    Raises `AssertionError` with test context when export or redaction behavior differs from expectations.

    Ties to other methods
    Exercises `run_export_mode`, the format renderers, and the safe-share redaction callback wiring.

    Why this exists
    Direct helper correctness is insufficient unless the public report workflow actually opts into it for both
    supported artifact formats.
    """
    try:
        snapshot = _sensitive_snapshot()
        source_json = snapshot.to_json(pretty=False)
        suffix = "md" if format_name == "markdown" else "html"
        export_path = tmp_path / f"safe-report.{suffix}"
        args = argparse.Namespace(
            export=format_name,
            export_include_diagnostics=True,
            redact_sensitive=True,
            fail_on=None,
            export_path=str(export_path),
            diff_snapshots=None,
            diff_against=None,
            export_from_snapshot=None,
        )

        result = run_export_mode(
            args,
            build_snapshot=lambda: snapshot,
            resolve_export_path_fn=lambda _format, *, explicit_path, kind: export_path,
            write_text_file_fn=write_text_file,
            should_fail_on_snapshot_fn=lambda _snapshot, _fail_on: False,
        )

        content = export_path.read_text(encoding="utf-8")
        assert result == 0
        assert snapshot.to_json(pretty=False) == source_json
        assert "C02SECRET123" not in content
        assert "Home Secret Network" not in content
        assert "192.168.50.23" not in content
        assert "/Users/alice/Projects/private/secret-tool" not in content
        assert "[REDACTED: serial]" in content
        assert "[REDACTED: process path]/secret-tool" in content
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
            f"{MODULE_PATH}:test_export_mode_redacts_markdown_and_html_when_enabled[{format_name}] failed: {exc}"
        ) from exc


def test_export_mode_preserves_sensitive_output_default(tmp_path: Path) -> None:
    """
    Summary
    Verify report output remains unchanged when safe-share redaction is not requested.

    Inputs
    Representative sensitive snapshot and temporary output directory.

    Outputs
    Assertions that existing default export content still contains source values.

    Side effects
    Writes one temporary Markdown report and prints its path.

    Error handling
    Raises `AssertionError` with test context when default behavior changes.

    Ties to other methods
    Exercises `run_export_mode` with `redact_sensitive` disabled.

    Why this exists
    The new privacy mode is explicitly opt-in and must not silently change established report or automation output.
    """
    try:
        snapshot = _sensitive_snapshot()
        export_path = tmp_path / "default-report.md"
        args = argparse.Namespace(
            export="markdown",
            export_include_diagnostics=True,
            redact_sensitive=False,
            fail_on=None,
            export_path=str(export_path),
            diff_snapshots=None,
            diff_against=None,
            export_from_snapshot=None,
        )

        result = run_export_mode(
            args,
            build_snapshot=lambda: snapshot,
            resolve_export_path_fn=lambda _format, *, explicit_path, kind: export_path,
            write_text_file_fn=write_text_file,
            should_fail_on_snapshot_fn=lambda _snapshot, _fail_on: False,
        )

        content = export_path.read_text(encoding="utf-8")
        assert result == 0
        assert "C02SECRET123" in content
        assert "Home Secret Network" in content
        assert "192.168.50.23" in content
        assert "/Users/alice/Projects/private/secret-tool" in content
        assert stat.S_IMODE(export_path.stat().st_mode) == 0o600
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
            f"{MODULE_PATH}:test_export_mode_preserves_sensitive_output_default failed: {exc}"
        ) from exc


def test_snapshot_json_mode_applies_redaction_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Summary
    Verify opt-in JSON snapshot output serializes a redacted copy.

    Inputs
    Representative sensitive snapshot and pytest stdout capture.

    Outputs
    Assertions on JSON stdout and source snapshot immutability.

    Side effects
    Writes one JSON payload to captured stdout.

    Error handling
    Raises `AssertionError` with test context when JSON output leaks a protected value.

    Ties to other methods
    Exercises `run_snapshot_json_mode` and `serialize_snapshot` through the same callback boundary as the entrypoint.

    Why this exists
    Saved snapshot JSON is often attached to support tickets, so the same explicit safe-share flag should protect that
    coherent export surface as Markdown and HTML.
    """
    try:
        snapshot = _sensitive_snapshot()
        source_json = snapshot.to_json(pretty=False)
        args = argparse.Namespace(fail_on=None, snapshot_pretty=False, redact_sensitive=True)
        runtime = cast(_RuntimeStateProtocol, SimpleNamespace(shutdown=object()))

        result = run_snapshot_json_mode(
            args,
            runtime,
            build_snapshot_fn=lambda: snapshot,
            snapshot_exit_code_fn=lambda _snapshot, _fail_on: 0,
            serialize_snapshot_fn=lambda value, pretty, trailing: serialize_snapshot(
                value,
                pretty=pretty,
                ensure_trailing_newline=trailing,
            ),
            finish_mode_fn=lambda _shutdown, code: code,
        )

        output = capsys.readouterr().out
        assert result == 0
        assert snapshot.to_json(pretty=False) == source_json
        assert "C02SECRET123" not in output
        assert "Home Secret Network" not in output
        assert "/Users/alice/Projects/private/secret-tool" not in output
        assert "[REDACTED: serial]" in output
        assert "[REDACTED: PID]" in output
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
            f"{MODULE_PATH}:test_snapshot_json_mode_applies_redaction_flag failed: {exc}"
        ) from exc


def test_cli_parser_exposes_redact_sensitive_as_opt_in() -> None:
    """
    Summary
    Verify the root CLI parser exposes safe-share redaction without enabling it by default.

    Inputs
    Root argument parser with empty and flagged argv lists.

    Outputs
    Assertions on parsed `redact_sensitive` values.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with test context when parser defaults or flag wiring regress.

    Ties to other methods
    Exercises `_build_parser` argument registration.

    Why this exists
    Privacy behavior must be explicit and discoverable while preserving all existing output defaults.
    """
    try:
        parser = _build_parser()
        assert parser.parse_args([]).redact_sensitive is False
        assert parser.parse_args(["--snapshot-json", "--redact-sensitive"]).redact_sensitive is True
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
            f"{MODULE_PATH}:test_cli_parser_exposes_redact_sensitive_as_opt_in failed: {exc}"
        ) from exc
