from __future__ import annotations

import argparse
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar

from mac_health_checkup.app.backend import Snapshot
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/entrypoint.py"
_DiffT = TypeVar("_DiffT", contravariant=True)


class ResolveExportPathFn(Protocol):
    """
    Summary
    Describe the export-path resolver interface used by export helpers.

    Inputs
    None.

    Outputs
    Structural protocol used only for type checking.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `run_export_mode` and `build_export_settings`.

    Why this exists
    The entrypoint wrapper preserves a patchable resolver surface while keeping strict typing.
    """

    def __call__(self, format_name: str, *, explicit_path: str | None, kind: str) -> Path:
        """
        Summary
        Resolve an export path for the requested format and export kind.

        Inputs
        format_name: Export format string.
        explicit_path: Optional caller-provided output path.
        kind: Export kind string such as "snapshot" or "diff".

        Outputs
        Resolved output `Path`.

        Side effects
        None.

        Error handling
        Implementations may raise `ValueError` when inputs are invalid.

        Ties to other methods
        Used by `run_export_mode` and `build_export_settings`.

        Why this exists
        Export helpers need a strictly typed hook that still matches the patchable entrypoint facade.
        """

        ...


class SnapshotRenderer(Protocol):
    """
    Summary
    Describe the snapshot renderer interface used by export helpers.

    Inputs
    None.

    Outputs
    Structural protocol used only for type checking.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by snapshot export helpers.

    Why this exists
    Snapshot renderers share a common signature across Markdown and HTML modes.
    """

    def __call__(self, snapshot: Snapshot, *, include_diagnostics: bool) -> str:
        """
        Summary
        Render a snapshot report into text.

        Inputs
        snapshot: Snapshot payload to render.
        include_diagnostics: Whether raw diagnostics should be embedded.

        Outputs
        Rendered snapshot report string.

        Side effects
        None.

        Error handling
        Implementations may raise renderer-specific errors.

        Ties to other methods
        Used by snapshot export helpers.

        Why this exists
        Snapshot export flows need a shared renderer contract for Markdown and HTML implementations.
        """

        ...


class ShouldFailOnSnapshotFn(Protocol):
    """
    Summary
    Describe the fail-policy callback used by snapshot export helpers.

    Inputs
    None.

    Outputs
    Structural protocol used only for type checking.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `run_export_mode` and `_resolve_snapshot_exit_code`.

    Why this exists
    Export flows should depend on the minimal fail-policy surface.
    """

    def __call__(self, snapshot: Snapshot, fail_on: str) -> bool:
        """
        Summary
        Evaluate whether a snapshot should force a non-zero exit code.

        Inputs
        snapshot: Snapshot payload to evaluate.
        fail_on: Requested threshold string.

        Outputs
        True when the snapshot should fail the current process.

        Side effects
        None.

        Error handling
        Implementations may raise policy-specific errors.

        Ties to other methods
        Used by `run_export_mode` and `_resolve_snapshot_exit_code`.

        Why this exists
        Snapshot export flows should depend on one typed fail-policy hook.
        """

        ...


class DiffRenderer(Protocol[_DiffT]):
    """
    Summary
    Describe the diff renderer interface used by export helpers.

    Inputs
    None.

    Outputs
    Structural protocol used only for type checking.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by diff export helpers.

    Why this exists
    Diff renderers accept one diff payload type and produce formatted text.
    """

    def __call__(self, diff: _DiffT) -> str:
        """
        Summary
        Render a diff payload into text.

        Inputs
        diff: Diff payload to render.

        Outputs
        Rendered diff string.

        Side effects
        None.

        Error handling
        Implementations may raise renderer-specific errors.

        Ties to other methods
        Used by diff export helpers.

        Why this exists
        Diff export flows need one typed renderer contract for multiple output formats.
        """

        ...


@dataclass(frozen=True)
class ExportModeSettings:
    """
    Summary
    Hold normalized export settings derived from CLI args.

    Inputs
    format_name: Export format string.
    include_diagnostics: Whether raw diagnostics should be embedded in exports.
    fail_on: Optional fail threshold.
    path: Final output path.

    Outputs
    Immutable settings object.

    Side effects
    None.

    Error handling
    Validation occurs in `build_export_settings`.

    Ties to other methods
    Used by `run_export_mode` and its specialized helper flows.

    Why this exists
    Normalized export settings prevent each export branch from re-parsing the same CLI flags.
    """

    format_name: str
    include_diagnostics: bool
    fail_on: str
    path: Path


def run_diff_mode(args: argparse.Namespace) -> int:
    """
    Summary
    Execute standalone snapshot diff mode.

    Inputs
    args: Parsed CLI args with `diff_snapshots`.

    Outputs
    Process exit code (0 when diff rendered successfully).

    Side effects
    Reads snapshot files and writes to stdout.

    Error handling
    Raises `RuntimeError` with module and method context when diff computation or rendering fails.

    Ties to other methods
    Called by `mac_health_checkup.app.entrypoint._run_diff_mode` before GUI or CLI execution paths.

    Why this exists
    Diffs between existing snapshots should be fast and should not run collectors.
    """
    try:
        from mac_health_checkup.app.reports import (
            diff_snapshots,
            load_snapshot_from_path,
            render_diff_markdown,
        )

        before_path, after_path = _resolve_diff_paths(args.diff_snapshots)
        before = load_snapshot_from_path(before_path)
        after = load_snapshot_from_path(after_path)
        diff = diff_snapshots(before, after)
        print(render_diff_markdown(diff), end="")
        return 0
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_run_diff_mode", "Diff mode failed", exc)) from exc


def run_export_mode(
    args: argparse.Namespace,
    *,
    build_snapshot: Callable[[], Snapshot],
    resolve_export_path_fn: ResolveExportPathFn,
    write_text_file_fn: Callable[[Path, str], None],
    should_fail_on_snapshot_fn: ShouldFailOnSnapshotFn,
) -> int:
    """
    Summary
    Execute snapshot or diff export mode.

    Inputs
    args: Parsed CLI args with export settings.
    build_snapshot: Callback that builds the current live snapshot.
    resolve_export_path_fn: Callback that resolves export output paths.
    write_text_file_fn: Callback used to persist export content.
    should_fail_on_snapshot_fn: Callback used to evaluate automation exit semantics.

    Outputs
    Process exit code.

    Side effects
    May run collectors, reads snapshot files, and writes export output to disk.

    Error handling
    Raises `RuntimeError` with module and method context when export fails.

    Ties to other methods
    Called by `mac_health_checkup.app.entrypoint._run_export_mode` prior to serve or GUI modes.

    Why this exists
    Exports produce shareable artifacts without requiring the recipient to run the program.
    """
    try:
        from mac_health_checkup.app.reports import (
            diff_snapshots,
            load_snapshot_from_path,
            render_diff_html,
            render_diff_markdown,
            render_snapshot_html,
            render_snapshot_markdown,
        )

        settings = build_export_settings(args, resolve_export_path_fn=resolve_export_path_fn)
        if args.diff_snapshots:
            return _export_existing_snapshot_diff(
                args=args,
                settings=settings,
                load_snapshot_from_path=load_snapshot_from_path,
                diff_snapshots=diff_snapshots,
                render_diff_markdown=render_diff_markdown,
                render_diff_html=render_diff_html,
                write_text_file_fn=write_text_file_fn,
            )
        if args.diff_against:
            return _export_live_snapshot_diff(
                args=args,
                settings=settings,
                build_snapshot=build_snapshot,
                load_snapshot_from_path=load_snapshot_from_path,
                diff_snapshots=diff_snapshots,
                render_diff_markdown=render_diff_markdown,
                render_diff_html=render_diff_html,
                write_text_file_fn=write_text_file_fn,
            )
        if args.export_from_snapshot:
            return _export_existing_snapshot_report(
                args=args,
                settings=settings,
                load_snapshot_from_path=load_snapshot_from_path,
                render_snapshot_markdown=render_snapshot_markdown,
                render_snapshot_html=render_snapshot_html,
                write_text_file_fn=write_text_file_fn,
                should_fail_on_snapshot_fn=should_fail_on_snapshot_fn,
            )
        return _export_live_snapshot_report(
            settings=settings,
            build_snapshot=build_snapshot,
            render_snapshot_markdown=render_snapshot_markdown,
            render_snapshot_html=render_snapshot_html,
            write_text_file_fn=write_text_file_fn,
            should_fail_on_snapshot_fn=should_fail_on_snapshot_fn,
        )
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_run_export_mode", "Export mode failed", exc)) from exc


def write_text_file(path: Path, content: str) -> None:
    """
    Summary
    Write UTF-8 text to disk, creating parent directories as needed.

    Inputs
    path: Output path.
    content: Text content.

    Outputs
    None.

    Side effects
    Writes a file to disk.

    Error handling
    Raises `RuntimeError` with module and method context when writing fails.

    Ties to other methods
    Used by snapshot and diff export flows.

    Why this exists
    Exports should be deterministic and should fail with actionable messages when paths are invalid.
    """
    try:
        out_path = path.expanduser()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_write_text_file", f"Write failed: {path}", exc)
        ) from exc


def resolve_export_path(
    format_name: str,
    *,
    explicit_path: str | None,
    kind: str,
    strftime_fn: Callable[[str], str] = time.strftime,
) -> Path:
    """
    Summary
    Resolve an export output path from CLI flags, falling back to a git-ignored default location.

    Inputs
    format_name: "markdown" or "html".
    explicit_path: Optional explicit path string.
    kind: "snapshot" or "diff" for default naming.

    Outputs
    Resolved output path.

    Side effects
    None.

    Error handling
    Raises `ValueError` when inputs are invalid.

    Ties to other methods
    Used by `run_export_mode` to determine export file location.

    Why this exists
    Default exports should not clutter the repo root and should live under `.local/` by default.
    """
    if explicit_path:
        return Path(explicit_path)
    ext = "md" if format_name == "markdown" else "html"
    timestamp = strftime_fn("%Y%m%d-%H%M%S")
    return Path(".local") / "reports" / f"mac-health-checkup-{kind}-{timestamp}.{ext}"


def build_export_settings(
    args: argparse.Namespace, *, resolve_export_path_fn: ResolveExportPathFn
) -> ExportModeSettings:
    """
    Summary
    Normalize export settings from parsed CLI args.

    Inputs
    args: Parsed CLI args.
    resolve_export_path_fn: Callback used to resolve the final output path.

    Outputs
    `ExportModeSettings`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when settings cannot be normalized.

    Ties to other methods
    Used by `run_export_mode` before delegating to specialized branches.

    Why this exists
    A single normalization step keeps all export flows consistent.
    """
    try:
        format_name = str(args.export)
        return ExportModeSettings(
            format_name=format_name,
            include_diagnostics=bool(args.export_include_diagnostics),
            fail_on=str(args.fail_on) if getattr(args, "fail_on", None) else "",
            path=resolve_export_path_fn(
                format_name,
                explicit_path=str(args.export_path) if args.export_path else None,
                kind="diff" if args.diff_snapshots or args.diff_against else "snapshot",
            ),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "build_export_settings", "Failed to normalize export settings", exc)
        ) from exc


def _resolve_diff_paths(values: Sequence[object] | None) -> tuple[Path, Path]:
    """
    Summary
    Convert diff snapshot CLI inputs into `Path` objects.

    Inputs
    values: Raw `diff_snapshots` CLI payload.

    Outputs
    Tuple of before and after snapshot paths.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context if the diff arguments are malformed.

    Ties to other methods
    Used by `run_diff_mode` and `_export_existing_snapshot_diff`.

    Why this exists
    Centralizing path normalization avoids duplicated path handling logic across diff modes.
    """
    try:
        if values is None or len(values) != 2:
            raise ValueError("diff snapshot arguments must contain exactly two paths")
        before_value, after_value = values
        return Path(str(before_value)), Path(str(after_value))
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_resolve_diff_paths", "Invalid diff snapshot arguments", exc)
        ) from exc


def _export_existing_snapshot_diff(
    *,
    args: argparse.Namespace,
    settings: ExportModeSettings,
    load_snapshot_from_path: Callable[[Path], Snapshot],
    diff_snapshots: Callable[[Snapshot, Snapshot], _DiffT],
    render_diff_markdown: DiffRenderer[_DiffT],
    render_diff_html: DiffRenderer[_DiffT],
    write_text_file_fn: Callable[[Path, str], None],
) -> int:
    """
    Summary
    Export a diff report between two existing snapshot files.

    Inputs
    args: Parsed CLI args.
    settings: Normalized export settings.
    load_snapshot_from_path: Snapshot loading callback.
    diff_snapshots: Diff builder callback.
    render_diff_markdown: Markdown diff renderer.
    render_diff_html: HTML diff renderer.
    write_text_file_fn: File writer callback.

    Outputs
    Exit code `0`.

    Side effects
    Reads snapshot files, writes an export file, and prints the output path.

    Error handling
    Raises contextual export errors from upstream helpers.

    Ties to other methods
    Used by `run_export_mode` when `--diff-snapshots` is set.

    Why this exists
    Existing snapshot diffs are the simplest export path and should stay isolated from live collection code.
    """
    before_path, after_path = _resolve_diff_paths(args.diff_snapshots)
    before = load_snapshot_from_path(before_path)
    after = load_snapshot_from_path(after_path)
    diff = diff_snapshots(before, after)
    content = _render_diff_content(
        diff=diff,
        format_name=settings.format_name,
        render_diff_markdown=render_diff_markdown,
        render_diff_html=render_diff_html,
    )
    _write_export(settings.path, content, write_text_file_fn=write_text_file_fn)
    return 0


def _export_live_snapshot_diff(
    *,
    args: argparse.Namespace,
    settings: ExportModeSettings,
    build_snapshot: Callable[[], Snapshot],
    load_snapshot_from_path: Callable[[Path], Snapshot],
    diff_snapshots: Callable[[Snapshot, Snapshot], _DiffT],
    render_diff_markdown: DiffRenderer[_DiffT],
    render_diff_html: DiffRenderer[_DiffT],
    write_text_file_fn: Callable[[Path, str], None],
) -> int:
    """
    Summary
    Export a diff report between a baseline snapshot file and the current live snapshot.

    Inputs
    args: Parsed CLI args.
    settings: Normalized export settings.
    build_snapshot: Callback that builds the current live snapshot.
    load_snapshot_from_path: Snapshot loading callback.
    diff_snapshots: Diff builder callback.
    render_diff_markdown: Markdown diff renderer.
    render_diff_html: HTML diff renderer.
    write_text_file_fn: File writer callback.

    Outputs
    Exit code based on the current live snapshot health.

    Side effects
    Runs collectors, reads a baseline snapshot, writes an export file, and prints the output path.

    Error handling
    Raises contextual export errors from upstream helpers.

    Ties to other methods
    Used by `run_export_mode` when `--diff-against` is set.

    Why this exists
    Baseline-vs-current comparisons are an automation workflow and should keep exit code logic close to the diff export.
    """
    baseline = load_snapshot_from_path(Path(str(args.diff_against)))
    current = build_snapshot()
    diff = diff_snapshots(baseline, current)
    content = _render_diff_content(
        diff=diff,
        format_name=settings.format_name,
        render_diff_markdown=render_diff_markdown,
        render_diff_html=render_diff_html,
    )
    _write_export(settings.path, content, write_text_file_fn=write_text_file_fn)
    return 0 if current.ok else 1


def _export_existing_snapshot_report(
    *,
    args: argparse.Namespace,
    settings: ExportModeSettings,
    load_snapshot_from_path: Callable[[Path], Snapshot],
    render_snapshot_markdown: SnapshotRenderer,
    render_snapshot_html: SnapshotRenderer,
    write_text_file_fn: Callable[[Path, str], None],
    should_fail_on_snapshot_fn: ShouldFailOnSnapshotFn,
) -> int:
    """
    Summary
    Export a report from an existing snapshot JSON file.

    Inputs
    args: Parsed CLI args.
    settings: Normalized export settings.
    load_snapshot_from_path: Snapshot loading callback.
    render_snapshot_markdown: Markdown snapshot renderer.
    render_snapshot_html: HTML snapshot renderer.
    write_text_file_fn: File writer callback.
    should_fail_on_snapshot_fn: Fail policy callback.

    Outputs
    Exit code derived from snapshot health and fail-on policy.

    Side effects
    Reads a snapshot file, writes an export file, and prints the output path.

    Error handling
    Raises contextual export errors from upstream helpers.

    Ties to other methods
    Used by `run_export_mode` when `--export-from-snapshot` is set.

    Why this exists
    Report rendering from a saved snapshot should not require live collectors.
    """
    snapshot = load_snapshot_from_path(Path(str(args.export_from_snapshot)))
    content = _render_snapshot_content(
        snapshot=snapshot,
        settings=settings,
        render_snapshot_markdown=render_snapshot_markdown,
        render_snapshot_html=render_snapshot_html,
    )
    _write_export(settings.path, content, write_text_file_fn=write_text_file_fn)
    return _resolve_snapshot_exit_code(
        snapshot, fail_on=settings.fail_on, should_fail_on_snapshot_fn=should_fail_on_snapshot_fn
    )


def _export_live_snapshot_report(
    *,
    settings: ExportModeSettings,
    build_snapshot: Callable[[], Snapshot],
    render_snapshot_markdown: SnapshotRenderer,
    render_snapshot_html: SnapshotRenderer,
    write_text_file_fn: Callable[[Path, str], None],
    should_fail_on_snapshot_fn: ShouldFailOnSnapshotFn,
) -> int:
    """
    Summary
    Export a report from the current live snapshot.

    Inputs
    settings: Normalized export settings.
    build_snapshot: Callback that builds the current live snapshot.
    render_snapshot_markdown: Markdown snapshot renderer.
    render_snapshot_html: HTML snapshot renderer.
    write_text_file_fn: File writer callback.
    should_fail_on_snapshot_fn: Fail policy callback.

    Outputs
    Exit code derived from snapshot health and fail-on policy.

    Side effects
    Runs collectors, writes an export file, and prints the output path.

    Error handling
    Raises contextual export errors from upstream helpers.

    Ties to other methods
    Used by `run_export_mode` for the default live export path.

    Why this exists
    Live snapshot report export is the common sharing path and benefits from a focused helper.
    """
    snapshot = build_snapshot()
    content = _render_snapshot_content(
        snapshot=snapshot,
        settings=settings,
        render_snapshot_markdown=render_snapshot_markdown,
        render_snapshot_html=render_snapshot_html,
    )
    _write_export(settings.path, content, write_text_file_fn=write_text_file_fn)
    return _resolve_snapshot_exit_code(
        snapshot, fail_on=settings.fail_on, should_fail_on_snapshot_fn=should_fail_on_snapshot_fn
    )


def _render_diff_content(
    *,
    diff: _DiffT,
    format_name: str,
    render_diff_markdown: DiffRenderer[_DiffT],
    render_diff_html: DiffRenderer[_DiffT],
) -> str:
    """
    Summary
    Render diff content in the requested export format.

    Inputs
    diff: Diff payload.
    format_name: Export format string.
    render_diff_markdown: Markdown diff renderer.
    render_diff_html: HTML diff renderer.

    Outputs
    Rendered diff content.

    Side effects
    None.

    Error handling
    Propagates renderer errors to the caller.

    Ties to other methods
    Used by diff export helpers.

    Why this exists
    Rendering format selection should not be duplicated across diff branches.
    """
    return render_diff_markdown(diff) if format_name == "markdown" else render_diff_html(diff)


def _render_snapshot_content(
    *,
    snapshot: Snapshot,
    settings: ExportModeSettings,
    render_snapshot_markdown: SnapshotRenderer,
    render_snapshot_html: SnapshotRenderer,
) -> str:
    """
    Summary
    Render snapshot report content in the requested export format.

    Inputs
    snapshot: Snapshot payload.
    settings: Normalized export settings.
    render_snapshot_markdown: Markdown snapshot renderer.
    render_snapshot_html: HTML snapshot renderer.

    Outputs
    Rendered snapshot report content.

    Side effects
    None.

    Error handling
    Propagates renderer errors to the caller.

    Ties to other methods
    Used by snapshot export helpers.

    Why this exists
    Snapshot rendering format selection should stay consistent across saved and live snapshot exports.
    """
    if settings.format_name == "markdown":
        return render_snapshot_markdown(snapshot, include_diagnostics=settings.include_diagnostics)
    return render_snapshot_html(snapshot, include_diagnostics=settings.include_diagnostics)


def _resolve_snapshot_exit_code(
    snapshot: Snapshot,
    *,
    fail_on: str,
    should_fail_on_snapshot_fn: ShouldFailOnSnapshotFn,
) -> int:
    """
    Summary
    Determine the exit code for snapshot export flows.

    Inputs
    snapshot: Snapshot payload.
    fail_on: Optional fail threshold.
    should_fail_on_snapshot_fn: Fail policy callback.

    Outputs
    Integer exit code.

    Side effects
    None.

    Error handling
    Propagates fail policy evaluation errors to the caller.

    Ties to other methods
    Used by snapshot export helpers.

    Why this exists
    Snapshot export branches share the same exit code semantics and should not reimplement them separately.
    """
    code = 0 if snapshot.ok else 1
    if fail_on and should_fail_on_snapshot_fn(snapshot, fail_on):
        return 1
    return code


def _write_export(path: Path, content: str, *, write_text_file_fn: Callable[[Path, str], None]) -> None:
    """
    Summary
    Persist rendered export content and echo the resulting path.

    Inputs
    path: Output path.
    content: Rendered export content.
    write_text_file_fn: File writer callback.

    Outputs
    None.

    Side effects
    Writes the export file and prints the file path to stdout.

    Error handling
    Propagates writer failures to the caller.

    Ties to other methods
    Used by all export helper branches.

    Why this exists
    Every export path should write and announce the output location consistently.
    """
    write_text_file_fn(path, content)
    print(str(path))
