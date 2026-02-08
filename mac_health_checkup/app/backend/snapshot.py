from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Callable, Mapping, Optional

from mac_health_checkup.app.cli import ConsoleHost
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict, JsonValue
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/backend/snapshot.py"

SectionHandler = Callable[[SectionHost], JsonDict]


@dataclass(frozen=True)
class SnapshotTable:
    """
    Summary
    Represent a tabular section render in a frontend-friendly shape.

    Inputs
    headers: Column headers.
    rows: Row tuples as strings.

    Outputs
    Immutable table container suitable for JSON encoding.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context if inputs are invalid.

    Ties to other methods
    Produced by `SnapshotBuilder.build` from `ConsoleHost` tables.

    Why this exists
    Keeps the JSON schema stable and explicit for Swift decoding.
    """

    headers: tuple[str, ...]
    rows: list[tuple[str, ...]]


@dataclass(frozen=True)
class SnapshotSection:
    """
    Summary
    Represent all UI-facing render outputs for a single section key.

    Inputs
    key: Section key.
    field: Summary field text.
    metrics: Optional metrics rows.
    table: Optional table data.
    diagnostics: Optional raw diagnostics dict returned by the section handler.

    Outputs
    Immutable snapshot section container suitable for JSON encoding.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context if normalization fails.

    Ties to other methods
    Produced by `SnapshotBuilder.build` and consumed by the SwiftUI frontend.

    Why this exists
    Separates frontend rendering output from the collector implementation details.
    """

    key: str
    field: Optional[str]
    metrics: Optional[list[tuple[str, str, str]]]
    table: Optional[SnapshotTable]
    diagnostics: Optional[JsonDict]


@dataclass(frozen=True)
class SnapshotTheme:
    """
    Summary
    Represent a frontend theme derived from central config.

    Inputs
    ui: UI window metadata.
    colors: Color roles used across the UI.
    fonts: Font roles used across the UI.
    gui: GUI layout values used by native frontends.

    Outputs
    Immutable theme container suitable for JSON encoding.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context if normalization fails.

    Ties to other methods
    Produced by `SnapshotBuilder._build_theme`.

    Why this exists
    Ensures native frontends render with the same style as the Python UI without duplicating config.
    """

    ui: JsonDict
    colors: JsonDict
    fonts: JsonDict
    gui: JsonDict


@dataclass(frozen=True)
class SnapshotSectionDescriptor:
    """
    Summary
    Represent stable metadata for a section (title, subtitle, key).

    Inputs
    title: User-facing title.
    subtitle: User-facing subtitle.
    key: Stable section key.

    Outputs
    Immutable section descriptor.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Emitted in `Snapshot.section_catalog` and used by native frontends for navigation.

    Why this exists
    Ensures the frontend can render and order sections without local config files.
    """

    title: str
    subtitle: str
    key: str


@dataclass(frozen=True)
class Snapshot:
    """
    Summary
    Represent a full dashboard snapshot for frontend rendering.

    Inputs
    schema_version: Schema version for forwards-compatible decoding.
    generated_at_unix_ms: Unix time in milliseconds when the snapshot was generated.
    sections: List of per-section render payloads.
    ok: Whether the snapshot completed without section-level failures.
    error: Optional top-level error string when snapshot building fails.

    Outputs
    Immutable snapshot container suitable for JSON encoding.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context if serialization fails.

    Ties to other methods
    Built by `SnapshotBuilder.build` and emitted by `emit_snapshot_json`.

    Why this exists
    Provides a single, stable payload for a native frontend to render.
    """

    schema_version: int
    generated_at_unix_ms: int
    theme: SnapshotTheme
    section_catalog: list[SnapshotSectionDescriptor]
    sections: list[SnapshotSection]
    ok: bool
    error: Optional[str] = None

    def to_json(self, *, pretty: bool) -> str:
        """
        Summary
        Serialize the snapshot to JSON for stdout emission.

        Inputs
        pretty: Whether to pretty-print the JSON with indentation.

        Outputs
        JSON string representing the snapshot.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context if encoding fails.

        Ties to other methods
        Used by `emit_snapshot_json` to produce stdout output.

        Why this exists
        Centralizes JSON serialization to keep encoding behavior consistent across call sites.
        """
        try:
            payload = asdict(self)
            if pretty:
                return json.dumps(payload, indent=2, sort_keys=True)
            return json.dumps(payload, separators=(",", ":"), sort_keys=True)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "Snapshot.to_json", "Failed to encode snapshot JSON", exc)
            ) from exc


class SnapshotBuilder:
    """
    Summary
    Build a dashboard snapshot from a set of section handlers.

    Inputs
    handlers: Mapping of section keys to handler callables.

    Outputs
    `Snapshot` objects built from handler output and render host state.

    Side effects
    Executes section handlers which may run system commands.

    Error handling
    Raises `RuntimeError` with module and method context when snapshot building fails.

    Ties to other methods
    Used by `emit_snapshot_json` and the entrypoint `--snapshot-json` mode.

    Why this exists
    Provides a backend interface for native frontends without coupling them to Tkinter.
    """

    def __init__(self, handlers: Mapping[str, SectionHandler]) -> None:
        """
        Summary
        Initialize the builder with section handlers.

        Inputs
        handlers: Section handler mapping.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context if inputs are invalid.

        Ties to other methods
        Used by `build` to iterate handlers deterministically.

        Why this exists
        Keeps handler injection explicit for tests and alternate frontends.
        """
        try:
            self._handlers = dict(handlers)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SnapshotBuilder.__init__", "Invalid handler mapping", exc)
            ) from exc

    def build(self) -> Snapshot:
        """
        Summary
        Build a snapshot by executing each section handler once.

        Inputs
        None.

        Outputs
        A `Snapshot` containing UI-facing data for all sections.

        Side effects
        Runs section handlers which may perform bounded IO.

        Error handling
        Returns `ok=false` snapshots when handlers fail and includes a per-section error in diagnostics.

        Ties to other methods
        Uses `ConsoleHost` to capture render output and stores diagnostics results per section.

        Why this exists
        Enables a native UI to render the same content as the Tk/CLI hosts with a stable schema.
        """
        try:
            theme = self._build_theme()
            section_catalog = self._build_section_catalog()
            host = ConsoleHost()
            sections: list[SnapshotSection] = []
            ok = True
            failed_sections: list[str] = []
            for key, handler in self._handlers.items():
                diagnostics = self._run_handler(host, key, handler)
                if diagnostics.get("ok") is False:
                    ok = False
                    failed_sections.append(key)
                sections.append(self._build_section_payload(host, key, diagnostics))
            error_text: str | None = None
            if failed_sections:
                error_text = f"Failed sections: {', '.join(failed_sections)}"
            return Snapshot(
                schema_version=2,
                generated_at_unix_ms=int(time.time() * 1000),
                theme=theme,
                section_catalog=section_catalog,
                sections=sections,
                ok=ok,
                error=error_text,
            )
        except Exception as exc:
            return Snapshot(
                schema_version=2,
                generated_at_unix_ms=int(time.time() * 1000),
                theme=SnapshotTheme(ui={}, colors={}, fonts={}, gui={}),
                section_catalog=[],
                sections=[],
                ok=False,
                error=format_error(MODULE_PATH, "SnapshotBuilder.build", "Snapshot build failed", exc),
            )

    def _run_handler(self, host: SectionHost, key: str, handler: SectionHandler) -> JsonDict:
        """
        Summary
        Run a single handler with defensive error capture.

        Inputs
        host: SectionHost used for rendering side effects.
        key: Section key.
        handler: Section handler callable.

        Outputs
        Diagnostics dict with `ok` and optional error details.

        Side effects
        Executes the handler which may run system commands and update the host.

        Error handling
        Captures exceptions into a JSON diagnostics shape so snapshot building can continue.

        Ties to other methods
        Called by `build` for each section.

        Why this exists
        Prevents a single failing section from breaking the entire native UI refresh.
        """
        try:
            diagnostics = handler(host)
            if not isinstance(diagnostics, dict):
                raise TypeError(f"handler for {key} returned non-dict diagnostics")
            diagnostics.setdefault("ok", True)
            return diagnostics
        except Exception as exc:
            return {
                "ok": False,
                "error": format_error(MODULE_PATH, "_run_handler", f"Section {key} failed", exc),
            }

    def _build_section_payload(self, host: ConsoleHost, key: str, diagnostics: JsonDict) -> SnapshotSection:
        """
        Summary
        Convert host render state plus diagnostics into a `SnapshotSection`.

        Inputs
        host: ConsoleHost containing captured render outputs.
        key: Section key.
        diagnostics: Handler diagnostics dict.

        Outputs
        SnapshotSection for the given key.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when normalization fails.

        Ties to other methods
        Called by `build` after each handler completes.

        Why this exists
        Keeps JSON schema conversion logic centralized and testable.
        """
        try:
            field = host.fields.get(key)
            metrics = host.metrics.get(key)
            table = None
            headers = host.headers.get(key)
            rows = host.tables.get(key)
            if headers is not None and rows is not None:
                table = SnapshotTable(headers=headers, rows=rows)
            diag = dict(diagnostics)
            try:
                from mac_health_checkup.app.actionability import build_section_advice

                diag["advice"] = build_section_advice(
                    key,
                    field=field,
                    metrics=metrics,
                    diagnostics=diag,
                )
            except (ImportError, RuntimeError, ValueError, TypeError, AttributeError, KeyError) as exc:
                diag["advice_error"] = format_error(
                    MODULE_PATH,
                    "SnapshotBuilder._build_section_payload",
                    "Failed to build section advice",
                    exc,
                )
            return SnapshotSection(
                key=key,
                field=field,
                metrics=metrics,
                table=table,
                diagnostics=_coerce_json_dict(diag),
            )
        except Exception as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "SnapshotBuilder._build_section_payload", "Failed to build section", exc
                )
            ) from exc

    def _build_theme(self) -> SnapshotTheme:
        """
        Summary
        Build a frontend theme payload from the central config.

        Inputs
        None.

        Outputs
        SnapshotTheme value.

        Side effects
        Reads the application config.

        Error handling
        Raises `RuntimeError` with module and method context if config access fails.

        Ties to other methods
        Used by `build` to include theme metadata in the snapshot payload.

        Why this exists
        Allows native frontends to render with the same style as the Python UI without local config coupling.
        """
        try:
            cfg = get_config()
            ui: JsonDict = {"window_title": cfg.ui.window_title}
            colors: JsonDict = {
                "bg": cfg.colors.bg,
                "fg": cfg.colors.fg,
                "ok": cfg.colors.ok,
                "warn": cfg.colors.warn,
                "bad": cfg.colors.bad,
                "section": cfg.colors.section,
                "label": cfg.colors.label,
                "field": cfg.colors.field,
            }
            fonts: JsonDict = {
                "family_default": cfg.fonts.family_default,
                "family_mono": cfg.fonts.family_mono,
                "size_section": cfg.fonts.size_section,
                "size_banner": cfg.fonts.size_banner,
                "size_field": cfg.fonts.size_field,
                "size_tooltip": cfg.fonts.size_tooltip,
            }
            gui: JsonDict = {
                "card_bg": cfg.gui.card_bg,
                "card_border": cfg.gui.card_border,
                "section_padx": cfg.gui.section_padx,
                "section_pady": cfg.gui.section_pady,
                "auto_refresh_ms": cfg.gui.auto_refresh_ms,
                "fans_refresh_ms": cfg.gui.fans_refresh_ms,
                "scrollable_rows": cfg.gui.scrollable_rows,
            }
            return SnapshotTheme(ui=ui, colors=colors, fonts=fonts, gui=gui)
        except Exception as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "SnapshotBuilder._build_theme", "Failed to build theme", exc)
            ) from exc

    def _build_section_catalog(self) -> list[SnapshotSectionDescriptor]:
        """
        Summary
        Build the section catalog list from config ordering.

        Inputs
        None.

        Outputs
        List of SnapshotSectionDescriptor values.

        Side effects
        Reads application config.

        Error handling
        Raises `RuntimeError` with module and method context if config access fails.

        Ties to other methods
        Used by `build` to include section ordering and labels in the snapshot.

        Why this exists
        Enables native clients to render navigation labels without embedding a duplicate config file.
        """
        try:
            cfg = get_config()
            return [SnapshotSectionDescriptor(title=t, subtitle=s, key=k) for t, s, k in cfg.gui.section_rows]
        except Exception as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "SnapshotBuilder._build_section_catalog", "Failed to build catalog", exc
                )
            ) from exc


def emit_snapshot_json(handlers: Mapping[str, SectionHandler], *, pretty: bool) -> tuple[int, str]:
    """
    Summary
    Build and serialize a snapshot as JSON for frontend consumption.

    Inputs
    handlers: Mapping of section keys to handlers.
    pretty: Whether to pretty-print JSON.

    Outputs
    Tuple of (exit_code, json_text).

    Side effects
    Executes section handlers which may run system commands.

    Error handling
    Always returns a JSON string; uses exit_code 1 on failure and includes `error` in the payload.

    Ties to other methods
    Used by the Python entrypoint `--snapshot-json` mode.

    Why this exists
    Guarantees a stable machine-readable stdout payload for the SwiftUI app.
    """
    try:
        snapshot = SnapshotBuilder(handlers).build()
        return (0 if snapshot.ok else 1, snapshot.to_json(pretty=pretty))
    except Exception as exc:
        snapshot = Snapshot(
            schema_version=2,
            generated_at_unix_ms=int(time.time() * 1000),
            theme=SnapshotTheme(ui={}, colors={}, fonts={}, gui={}),
            section_catalog=[],
            sections=[],
            ok=False,
            error=format_error(MODULE_PATH, "emit_snapshot_json", "Failed to emit snapshot", exc),
        )
        return (1, snapshot.to_json(pretty=pretty))


def emit_section_json(
    handlers: Mapping[str, SectionHandler], *, section_key: str, pretty: bool
) -> tuple[int, str]:
    """
    Summary
    Build and serialize a single-section snapshot as JSON for frontend consumption.

    Inputs
    handlers: Mapping of section keys to handlers.
    section_key: Section key to build.
    pretty: Whether to pretty-print JSON.

    Outputs
    Tuple of (exit_code, json_text).

    Side effects
    Executes a single section handler which may run system commands.

    Error handling
    Always returns a JSON string; uses exit_code 1 on failure and includes `error` in the payload.

    Ties to other methods
    Used by the agent HTTP handler for `/v1/section`.

    Why this exists
    Enables higher-frequency refresh of a single section (fans) without recomputing the full snapshot.
    """
    try:
        key = (section_key or "").strip()
        if not key:
            raise ValueError("section_key must be non-empty")
        if key not in handlers:
            raise KeyError(f"unknown section_key: {key}")

        builder = SnapshotBuilder(handlers)
        theme = builder._build_theme()
        section_catalog = builder._build_section_catalog()
        host = ConsoleHost()
        diagnostics = builder._run_handler(host, key, handlers[key])
        payload = builder._build_section_payload(host, key, diagnostics)
        ok = diagnostics.get("ok") is not False
        error_text: str | None = None
        if not ok:
            err = diagnostics.get("error")
            if isinstance(err, str) and err.strip():
                error_text = err
            elif err is not None:
                error_text = str(err)
        snapshot = Snapshot(
            schema_version=2,
            generated_at_unix_ms=int(time.time() * 1000),
            theme=theme,
            section_catalog=section_catalog,
            sections=[payload],
            ok=ok,
            error=error_text,
        )
        return (0 if snapshot.ok else 1, snapshot.to_json(pretty=pretty))
    except Exception as exc:
        snapshot = Snapshot(
            schema_version=2,
            generated_at_unix_ms=int(time.time() * 1000),
            theme=SnapshotTheme(ui={}, colors={}, fonts={}, gui={}),
            section_catalog=[],
            sections=[],
            ok=False,
            error=format_error(MODULE_PATH, "emit_section_json", "Failed to emit section", exc),
        )
        return (1, snapshot.to_json(pretty=pretty))


def _coerce_json_dict(value: Mapping[str, JsonValue]) -> JsonDict:
    """
    Summary
    Coerce an arbitrary mapping into a JSON dict while preserving nested JSON types.

    Inputs
    value: Mapping expected to contain JSON-compatible values.

    Outputs
    A `JsonDict` copy.

    Side effects
    None.

    Error handling
    Raises `ValueError` with module and method context when values are not JSON compatible.

    Ties to other methods
    Used by `SnapshotBuilder._build_section_payload`.

    Why this exists
    Keeps the snapshot payload deterministic and compatible with strict Swift decoding.
    """
    try:
        return dict(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(format_error(MODULE_PATH, "_coerce_json_dict", "Invalid JSON dict", exc)) from exc
