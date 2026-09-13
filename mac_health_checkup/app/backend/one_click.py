from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path
from typing import Mapping

from mac_health_checkup.core.types import JsonDict, JsonValue
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/backend/one_click.py"
PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600


def run_one_click_agent(*, repo_root: Path) -> int:
    """
    Summary
    Start a secure agent server with minimal user interaction.

    Inputs
    repo_root: Repository root directory.

    Outputs
    Process exit code from the agent entrypoint.

    Side effects
    Writes a generated config under `.local/`, may generate TLS cert files, and starts the API server.

    Error handling
    Raises `RuntimeError` with module and method context when configuration or startup fails.

    Ties to other methods
    Used by the repository root one-click script to make running the project effortless.

    Why this exists
    Enables press-run developer ergonomics without weakening security defaults. LAN exposure is enabled only when
    TLS material is ready; otherwise the agent falls back to loopback-only HTTP.
    """
    try:
        root = repo_root.resolve()
        base_config_path = root / "config" / "config.json"
        if not base_config_path.is_file():
            raise ValueError(f"Missing base config file: {base_config_path}")

        base = _read_json_dict(base_config_path)
        local_dir = root / ".local"
        _ensure_private_directory(local_dir)
        tls_dir = local_dir / "tls"
        _ensure_private_directory(tls_dir)
        cert_path = tls_dir / "agent-cert.pem"
        key_path = tls_dir / "agent-key.pem"

        lan_ip = _best_effort_lan_ip()
        token = secrets.token_urlsafe(32)

        tls_ready, tls_error = _ensure_self_signed_cert(cert_path=cert_path, key_path=key_path)
        allow_lan = bool(tls_ready and lan_ip is not None)
        bind_host_for_port = lan_ip if allow_lan and lan_ip is not None else "127.0.0.1"
        port = _pick_free_port(bind_host_for_port)
        tls_enabled = allow_lan

        api_overrides: JsonDict = {
            "enabled": True,
            "bind_host": bind_host_for_port,
            "port": port,
            "allow_lan": allow_lan,
            "allow_insecure_http_lan": False,
            "tls_enabled": tls_enabled,
            "tls_cert_path": str(cert_path),
            "tls_key_path": str(key_path),
            "auth_token": token,
            "min_auth_token_length": 24,
            "blocked_auth_tokens": ["change-me", "changeme", "password", "token"],
            "rate_limit_requests_per_minute": 120,
            "max_auth_failures_per_minute": 10,
            "auth_ban_seconds": 120,
            "request_timeout_sec": 15,
            "pairing_qr_enabled": True,
        }

        derived = _build_config_with_api_overrides(base, api_overrides)
        derived_path = local_dir / "one-click-config.json"
        _write_private_text(
            derived_path,
            json.dumps(derived, indent=2, sort_keys=True) + "\n",
        )

        os.environ["MAC_HEALTH_CHECKUP_CONFIG"] = str(derived_path)
        if allow_lan and lan_ip is not None:
            scheme = "https" if tls_enabled else "http"
            os.environ["MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL"] = f"{scheme}://{lan_ip}:{port}"
        else:
            os.environ.pop("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL", None)

        print("One-click agent configuration written to:")
        print(str(derived_path))
        if allow_lan:
            scheme = "https" if tls_enabled else "http"
            print(f"LAN URL: {scheme}://{lan_ip}:{port}")
            if tls_error:
                print(f"TLS warning: {tls_error}")
        else:
            print(f"Local URL: http://127.0.0.1:{port}")
            if lan_ip is not None and not tls_ready:
                print("LAN access disabled because TLS material is unavailable; serving on loopback only.")
            if tls_error:
                print(f"TLS note: {tls_error}")

        print()
        print(
            "This one-click runner starts the agent API server only (headless). No UI window opens on this Mac."
        )
        print("Next steps:")
        if allow_lan:
            print("- iOS UI: open the iOS app and paste the pairing payload JSON (QR code is optional).")
        else:
            print("- iOS UI: pairing requires a LAN-reachable HTTPS URL; this loopback server is Mac-only.")
        print(
            "- macOS UI: run `make swift-run` (or `python3 run_mac_health_checkup_ui.py`) to launch the SwiftUI dashboard."
        )
        print()

        from mac_health_checkup.app.entrypoint import main as entrypoint_main

        argv_backup = list(sys.argv)
        try:
            sys.argv = [argv_backup[0], "--serve"]
            return int(entrypoint_main())
        finally:
            sys.argv = argv_backup
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "run_one_click_agent", "Failed to run one-click agent", exc)
        ) from exc


def _ensure_private_directory(path: Path) -> None:
    """
    Summary
    Create a directory when needed and enforce owner-only access.

    Inputs
    path: Directory that will contain generated credentials or credential-bearing configuration.

    Outputs
    None.

    Side effects
    Creates the directory and changes its POSIX mode to 0700, including when it already exists.

    Error handling
    Raises `RuntimeError` with module and method context when directory creation or permission changes fail.

    Ties to other methods
    Used by the one-click runner and private-file writer before storing generated secrets.

    Why this exists
    Ambient process umasks are not a sufficient access-control boundary for generated authentication material.
    """
    try:
        path.mkdir(parents=True, mode=PRIVATE_DIRECTORY_MODE, exist_ok=True)
        path.chmod(PRIVATE_DIRECTORY_MODE)
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_ensure_private_directory",
                "Failed ensuring private directory",
                exc,
            )
        ) from exc


def _write_private_text(path: Path, value: str) -> None:
    """
    Summary
    Atomically write text to an owner-only file.

    Inputs
    path: Destination file path.
    value: Text to encode as UTF-8.

    Outputs
    None.

    Side effects
    Creates a temporary file beside the destination, writes and syncs it, then atomically replaces the destination.

    Error handling
    Removes an unfinished temporary file and raises `RuntimeError` with module and method context on failure.

    Ties to other methods
    Used by the one-click runner to store its generated token-bearing configuration.

    Why this exists
    The generated auth token must never depend on the caller's umask or be left in a partially written file.
    """
    descriptor: int | None = None
    temporary_path: Path | None = None
    try:
        _ensure_private_directory(path.parent)
        if path.exists():
            path.chmod(PRIVATE_FILE_MODE)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
        temporary_path = Path(temporary_name)
        os.fchmod(descriptor, PRIVATE_FILE_MODE)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = None
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
        path.chmod(PRIVATE_FILE_MODE)
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise RuntimeError(
            format_error(MODULE_PATH, "_write_private_text", "Failed writing private file", exc)
        ) from exc


def _build_config_with_api_overrides(base: JsonDict, api_overrides: Mapping[str, JsonValue]) -> JsonDict:
    """
    Summary
    Return a full config with only the API section overridden.

    Inputs
    base: Existing full config dict.
    api_overrides: Values to apply to the `api` section.

    Outputs
    A new dict representing the derived config.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when the base config is malformed.

    Ties to other methods
    Used by `run_one_click_agent` to avoid requiring users to edit `config/config.json`.

    Why this exists
    Keeps configuration centralized while enabling a per-run developer overlay.
    """
    try:
        out: JsonDict = dict(base)
        api_section = base.get("api")
        if not isinstance(api_section, dict):
            raise ValueError("base config missing api section")
        merged: JsonDict = dict(api_section)
        for key, value in api_overrides.items():
            merged[str(key)] = value
        out["api"] = merged
        return out
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH, "_build_config_with_api_overrides", "Failed to build derived config", exc
            )
        ) from exc


def _read_json_dict(path: Path) -> JsonDict:
    """
    Summary
    Read a JSON object from disk and validate it is a dict.

    Inputs
    path: Path to JSON file.

    Outputs
    JSON dict.

    Side effects
    Reads from disk.

    Error handling
    Raises `RuntimeError` with module and method context when file IO or JSON decoding fails.

    Ties to other methods
    Used by `run_one_click_agent`.

    Why this exists
    Keeps IO and validation centralized with clear error messages.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("root must be object")
        return data
    except (OSError, json.JSONDecodeError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_read_json_dict", "Failed reading JSON", exc)) from exc


def _pick_free_port(bind_host: str) -> int:
    """
    Summary
    Pick a free TCP port on the given bind host.

    Inputs
    bind_host: Bind host string.

    Outputs
    Port int.

    Side effects
    Binds and closes a temporary socket.

    Error handling
    Raises `RuntimeError` with module and method context when port selection fails.

    Ties to other methods
    Used by the one-click runner.

    Why this exists
    Avoids port conflicts and reduces setup friction.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((bind_host, 0))
            return int(sock.getsockname()[1])
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_pick_free_port", "Failed to pick port", exc)) from exc


def _best_effort_lan_ip() -> str | None:
    """
    Summary
    Best-effort derive a LAN-reachable IP address for the current machine.

    Inputs
    None.

    Outputs
    IP string or None if unavailable.

    Side effects
    Opens a UDP socket without sending traffic.

    Error handling
    Never raises for OS-level socket failures; returns None. Raises `RuntimeError` with module and method context
    when unexpected failures occur.

    Ties to other methods
    Used by the one-click runner to print a usable URL.

    Why this exists
    Users should not have to manually find their LAN IP to pair the iOS app.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("1.1.1.1", 80))
            ip = sock.getsockname()[0]
            if ip and not ip.startswith("127."):
                return str(ip)
        return None
    except OSError:
        return None
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_best_effort_lan_ip", "Failed to get LAN IP", exc)
        ) from exc


def _ensure_self_signed_cert(*, cert_path: Path, key_path: Path) -> tuple[bool, str | None]:
    """
    Summary
    Ensure a self-signed TLS certificate exists for the agent.

    Inputs
    cert_path: Certificate output path.
    key_path: Private key output path.

    Outputs
    (ready, warning_message).

    Side effects
    May run openssl to generate cert files.

    Error handling
    Returns a warning message for common openssl failures. Raises `RuntimeError` with module and method context on
    unexpected failures.

    Ties to other methods
    Used by the one-click runner to enable secure LAN mode.

    Why this exists
    TLS should be easy to enable without manual certificate tooling steps.
    """
    try:
        if cert_path.is_file() and key_path.is_file():
            return True, None

        openssl = _find_executable("openssl")
        if openssl is None:
            return False, "openssl not found, cannot auto-generate TLS certs"

        _ensure_private_directory(cert_path.parent)
        cmd = [
            openssl,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-days",
            "3650",
            "-subj",
            "/CN=mac-health-checkup-agent",
        ]
        subprocess.run(  # nosec B603
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        if cert_path.is_file() and key_path.is_file():
            return True, None
        return False, "TLS cert generation did not produce expected files"
    except subprocess.TimeoutExpired:
        return False, "openssl timed out while generating TLS certs"
    except subprocess.CalledProcessError:
        return False, "openssl failed to generate TLS certs"
    except (OSError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_ensure_self_signed_cert", "Failed ensuring TLS certs", exc)
        ) from exc


def _find_executable(name: str) -> str | None:
    """
    Summary
    Locate an executable in PATH.

    Inputs
    name: Executable name.

    Outputs
    Absolute path string or None.

    Side effects
    Reads PATH environment variable.

    Error handling
    Raises `RuntimeError` with module and method context when PATH inspection fails unexpectedly.

    Ties to other methods
    Used by the TLS generation helper.

    Why this exists
    Avoids brittle assumptions about tool install locations.
    """
    try:
        if not name.strip():
            return None
        path = os.environ.get("PATH", "")
        for part in path.split(os.pathsep):
            candidate = Path(part) / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
        return None
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_find_executable", "Failed to locate executable", exc)
        ) from exc
