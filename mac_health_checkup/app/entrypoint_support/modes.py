from __future__ import annotations

import argparse
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from mac_health_checkup.app.backend import Snapshot, SnapshotApiServer, SnapshotBuilder
from mac_health_checkup.app.entrypoint_support.runtime_mode import _ShutdownManagerProtocol
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.app.reports import redact_snapshot_sensitive
from mac_health_checkup.core.config import Config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import LogContext, StructuredLogger

SectionHandler = Callable[[SectionHost], JsonDict]


class _RuntimeStateProtocol(Protocol):
    """
    Summary
    Describe the runtime state surface consumed by entrypoint mode helpers.

    Inputs
    None.

    Outputs
    Structural protocol for the entrypoint runtime state.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by snapshot, CLI, GUI, and serve mode helpers.

    Why this exists
    Mode helpers depend on only a narrow shared runtime surface and should not require the concrete dataclass type.
    """

    @property
    def cfg(self) -> Config:
        """
        Summary
        Return the loaded config object.

        Inputs
        None.

        Outputs
        `Config`.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used by snapshot and serve mode helpers.

        Why this exists
        Runtime helpers only need read access to config.
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
        Used by mode helpers that emit structured logs.

        Why this exists
        The support layer depends only on read access to the configured logger.
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
        Used by mode helpers that need correlation-aware logs.

        Why this exists
        Support helpers should not mutate shared runtime context.
        """

    @property
    def shutdown(self) -> _ShutdownManagerProtocol:
        """
        Summary
        Return the lifecycle shutdown manager.

        Inputs
        None.

        Outputs
        Shutdown manager protocol implementation.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used by mode completion and serve helpers.

        Why this exists
        Runtime helpers only need read access to the installed shutdown manager.
        """


def run_snapshot_json_out_mode(
    args: argparse.Namespace,
    runtime: _RuntimeStateProtocol,
    *,
    build_snapshot_fn: Callable[[], Snapshot],
    snapshot_exit_code_fn: Callable[[Snapshot, str], int],
    serialize_snapshot_fn: Callable[[Snapshot, bool, bool], str],
    write_text_file_fn: Callable[[Path, str], None],
    finish_mode_fn: Callable[[_ShutdownManagerProtocol, int], int],
) -> int:
    """
    Summary
    Build a live snapshot and write it to a JSON file.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.
    build_snapshot_fn: Snapshot builder callback.
    snapshot_exit_code_fn: Snapshot exit-code callback.
    serialize_snapshot_fn: Snapshot serialization callback.
    write_text_file_fn: Text file writer callback.
    finish_mode_fn: Shutdown completion callback.

    Outputs
    Snapshot-mode process exit code.

    Side effects
    Runs collectors, writes a snapshot file, and triggers shutdown.

    Error handling
    Propagates snapshot building or file writing failures to the caller.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._run_snapshot_json_out_mode`.

    Why this exists
    Snapshot file emission is a distinct mode and should stay outside the top-level router.
    """
    snapshot = build_snapshot_fn()
    fail_on = str(args.fail_on) if args.fail_on else ""
    code = snapshot_exit_code_fn(snapshot, fail_on)
    output_snapshot = snapshot_for_output(
        snapshot,
        redact_sensitive=bool(getattr(args, "redact_sensitive", False)),
    )
    payload = serialize_snapshot_fn(output_snapshot, bool(args.snapshot_pretty), True)
    write_text_file_fn(Path(str(args.snapshot_json_out)), payload)
    return finish_mode_fn(runtime.shutdown, code)


def run_snapshot_json_mode(
    args: argparse.Namespace,
    runtime: _RuntimeStateProtocol,
    *,
    build_snapshot_fn: Callable[[], Snapshot],
    snapshot_exit_code_fn: Callable[[Snapshot, str], int],
    serialize_snapshot_fn: Callable[[Snapshot, bool, bool], str],
    finish_mode_fn: Callable[[_ShutdownManagerProtocol, int], int],
) -> int:
    """
    Summary
    Build a live snapshot and print it to stdout as JSON.

    Inputs
    args: Parsed CLI args.
    runtime: Initialized runtime state.
    build_snapshot_fn: Snapshot builder callback.
    snapshot_exit_code_fn: Snapshot exit-code callback.
    serialize_snapshot_fn: Snapshot serialization callback.
    finish_mode_fn: Shutdown completion callback.

    Outputs
    Snapshot-mode process exit code.

    Side effects
    Runs collectors, writes JSON to stdout, and triggers shutdown.

    Error handling
    Propagates snapshot building or serialization failures. Broken pipe output is handled safely.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._run_snapshot_json_mode`.

    Why this exists
    Stdout snapshot emission is a stable machine interface and should stay outside the router.
    """
    snapshot = build_snapshot_fn()
    fail_on = str(args.fail_on) if args.fail_on else ""
    code = snapshot_exit_code_fn(snapshot, fail_on)
    output_snapshot = snapshot_for_output(
        snapshot,
        redact_sensitive=bool(getattr(args, "redact_sensitive", False)),
    )
    payload = serialize_snapshot_fn(output_snapshot, bool(args.snapshot_pretty), False)
    try:
        print(payload)
    except BrokenPipeError:
        return finish_mode_fn(runtime.shutdown, code)
    return finish_mode_fn(runtime.shutdown, code)


def build_snapshot(
    *,
    section_handlers: Mapping[str, SectionHandler],
    snapshot_builder_type: type[SnapshotBuilder],
) -> Snapshot:
    """
    Summary
    Build a live snapshot from the configured section handlers.

    Inputs
    section_handlers: Mapping of section handlers.
    snapshot_builder_type: Snapshot builder class.

    Outputs
    `Snapshot`.

    Side effects
    Runs section collectors and renderers through the snapshot builder.

    Error handling
    Propagates snapshot builder failures to the caller.

    Ties to other methods
    Used by snapshot, export, and diff-against mode helpers.

    Why this exists
    Snapshot construction should live behind one helper so entrypoint wrappers stay small and testable.
    """
    return snapshot_builder_type(section_handlers).build()


def snapshot_for_output(snapshot: Snapshot, *, redact_sensitive: bool) -> Snapshot:
    """
    Summary
    Select the original or safe-share snapshot for an output path.

    Inputs
    snapshot: Source snapshot.
    redact_sensitive: Whether safe-share redaction is enabled.

    Outputs
    The original snapshot when redaction is disabled, otherwise an independent redacted copy.

    Side effects
    None.

    Error handling
    Propagates redaction failures to the snapshot mode boundary.

    Ties to other methods
    Used by JSON stdout and file output modes before serialization.

    Why this exists
    Exit-code evaluation must use the unmodified snapshot while only the emitted artifact receives optional
    safe-share redaction.
    """
    if not redact_sensitive:
        return snapshot
    return redact_snapshot_sensitive(snapshot)


def serialize_snapshot(snapshot: Snapshot, *, pretty: bool, ensure_trailing_newline: bool) -> str:
    """
    Summary
    Convert a snapshot into JSON with the requested formatting behavior.

    Inputs
    snapshot: Snapshot to serialize.
    pretty: Whether to pretty-print JSON.
    ensure_trailing_newline: Whether to guarantee a trailing newline in the returned text.

    Outputs
    Serialized snapshot JSON text.

    Side effects
    None.

    Error handling
    Propagates snapshot serialization failures to the caller.

    Ties to other methods
    Used by snapshot stdout and snapshot file mode helpers.

    Why this exists
    Snapshot serialization rules should stay in one place so file and stdout modes remain consistent.
    """
    payload = snapshot.to_json(pretty=pretty)
    if ensure_trailing_newline and not payload.endswith("\n"):
        return payload + "\n"
    return payload


def snapshot_exit_code(
    snapshot: Snapshot,
    *,
    fail_on: str,
    should_fail_on_snapshot_fn: Callable[[Snapshot, str], bool],
) -> int:
    """
    Summary
    Resolve the exit code for snapshot emission modes.

    Inputs
    snapshot: Built snapshot.
    fail_on: Optional fail threshold.
    should_fail_on_snapshot_fn: Fail-policy callback.

    Outputs
    Snapshot-mode exit code.

    Side effects
    None.

    Error handling
    Propagates fail-policy failures to the caller.

    Ties to other methods
    Used by snapshot stdout and snapshot file mode helpers.

    Why this exists
    Snapshot exit semantics should stay aligned across both machine-readable snapshot outputs.
    """
    code = 0 if snapshot.ok else 1
    if fail_on and should_fail_on_snapshot_fn(snapshot, fail_on):
        return 1
    return code


def ensure_api_enabled(cfg: Config) -> None:
    """
    Summary
    Validate that API serve mode is enabled in config.

    Inputs
    cfg: Loaded config object.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` when serve mode is requested while `api.enabled` is false.

    Ties to other methods
    Used by `run_serve_mode`.

    Why this exists
    Serve mode should fail fast with an actionable config error instead of partially initializing.
    """
    if not cfg.api.enabled:
        raise RuntimeError("api.enabled must be true in config to use --serve")


def print_server_banner(*, server_url: str, public_url: str) -> None:
    """
    Summary
    Print the primary server startup banner and optional public URL override.

    Inputs
    server_url: Bound server URL.
    public_url: Effective public URL for pairing payloads.

    Outputs
    None.

    Side effects
    Writes startup information to stdout.

    Error handling
    None.

    Ties to other methods
    Used by `run_serve_mode`.

    Why this exists
    Core server connection details should render before the more detailed networking guidance.
    """
    print(f"Snapshot API running at {server_url} (endpoints: /v1/health, /v1/snapshot, /v1/section)")
    if public_url != server_url:
        print(f"Public base URL: {public_url}")


def print_server_network_guidance(cfg: Config) -> None:
    """
    Summary
    Print LAN and TLS guidance for serve mode.

    Inputs
    cfg: Loaded config object.

    Outputs
    None.

    Side effects
    Writes operational guidance to stdout.

    Error handling
    None.

    Ties to other methods
    Used by `run_serve_mode`.

    Why this exists
    Networking guidance is a separate concern from banner and pairing output, so it should stay isolated.
    """
    if cfg.api.allow_lan:
        print("LAN access is enabled (api.allow_lan=true). Use a strong token and avoid sharing it.")
        print("If the URL shows 127.0.0.1, use your Mac's LAN IP address with the same port.")
        if not cfg.api.tls_enabled:
            print(
                "Warning: TLS is disabled. This is insecure on untrusted networks. "
                "Enable api.tls_enabled or disable LAN access."
            )


def print_server_tls_guidance(
    *,
    server: SnapshotApiServer,
    runtime: _RuntimeStateProtocol,
    public_url: str,
    print_pairing_qr_best_effort_fn: Callable[[str, bool], None],
) -> None:
    """
    Summary
    Print TLS pairing details for serve mode when TLS is enabled and a certificate fingerprint is available.

    Inputs
    server: Running snapshot API server.
    runtime: Initialized runtime state.
    public_url: Effective public URL for pairing payloads.
    print_pairing_qr_best_effort_fn: QR rendering callback.

    Outputs
    None.

    Side effects
    Writes TLS and pairing guidance to stdout and may render a QR code.

    Error handling
    None. Missing fingerprints simply suppress pairing output.

    Ties to other methods
    Used by `run_serve_mode`.

    Why this exists
    TLS pairing output is substantial enough to deserve its own helper.
    """
    if not runtime.cfg.api.tls_enabled:
        return
    fingerprint = server.tls_certificate_fingerprint_sha256()
    if not fingerprint:
        return
    print("TLS is enabled (api.tls_enabled=true).")
    print(f"Certificate fingerprint (sha256): {fingerprint}")
    print("Pairing payload for the optional iOS app (you can ignore this if using the macOS SwiftUI app):")
    pairing_payload = json.dumps(
        {"url": public_url, "token": runtime.cfg.api.auth_token, "pin": fingerprint},
        separators=(",", ":"),
        sort_keys=True,
    )
    print(pairing_payload)
    print_pairing_qr_best_effort_fn(pairing_payload, bool(runtime.cfg.api.pairing_qr_enabled))


def run_serve_mode(
    runtime: _RuntimeStateProtocol,
    *,
    section_handlers: Mapping[str, SectionHandler],
    snapshot_api_server_type: type[SnapshotApiServer],
    resolve_public_base_url_fn: Callable[[str], str],
    print_pairing_qr_best_effort_fn: Callable[[str, bool], None],
    ensure_api_enabled_fn: Callable[[Config], None],
    print_server_banner_fn: Callable[[str, str], None],
    print_server_network_guidance_fn: Callable[[Config], None],
    print_server_tls_guidance_fn: Callable[
        [SnapshotApiServer, _RuntimeStateProtocol, str, Callable[[str, bool], None]], None
    ],
) -> int:
    """
    Summary
    Start the headless snapshot API server and keep it running until shutdown is requested.

    Inputs
    runtime: Initialized runtime state.
    section_handlers: Mapping of section handlers.
    snapshot_api_server_type: Snapshot API server class.
    resolve_public_base_url_fn: Public-base-url resolver callback.
    print_pairing_qr_best_effort_fn: QR rendering callback.
    ensure_api_enabled_fn: Serve-mode config validator.
    print_server_banner_fn: Server banner printer callback.
    print_server_network_guidance_fn: Network guidance printer callback.
    print_server_tls_guidance_fn: TLS guidance printer callback.

    Outputs
    Process exit code `0` after clean shutdown.

    Side effects
    Starts the HTTP server, prints connection details, waits for shutdown, then stops the server.

    Error handling
    Propagates serve mode prerequisite or server lifecycle failures to the caller.

    Ties to other methods
    Used by `mac_health_checkup.app.entrypoint._run_serve_mode`.

    Why this exists
    Serve mode has the largest amount of user-facing operational output and should stay isolated from the router.
    """
    ensure_api_enabled_fn(runtime.cfg)
    server = snapshot_api_server_type(section_handlers, runtime.cfg.api)
    server.start()
    try:
        public_url = resolve_public_base_url_fn(server.url())
        print_server_banner_fn(server.url(), public_url)
        print_server_network_guidance_fn(runtime.cfg)
        print_server_tls_guidance_fn(server, runtime, public_url, print_pairing_qr_best_effort_fn)
        print(
            "This is the Mac agent (headless). For the macOS UI, run `python3 run.py` or `python3 run_mac_health_checkup_ui.py`."
        )
        print("Press Ctrl+C to stop.")
        runtime.shutdown.wait_for_shutdown()
        return 0
    finally:
        server.stop()
        runtime.shutdown.trigger_shutdown()
