from __future__ import annotations

import json
import os
import secrets
import socket
import subprocess
import sys
from pathlib import Path
from typing import Mapping

from mac_health_checkup.core.types import JsonDict, JsonValue
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/backend/one_click.py"


def run_one_click_agent(*, repo_root: Path) -> int:
    """
    Purpose: Start a secure agent server with minimal user interaction.
    Ties: Used by the repository root one-click script to make running the project effortless.
    Inputs: repo_root is the repository root directory.
    Outputs: Process exit code from the agent entrypoint.
    Side effects: Writes a generated config under `.local/`, may generate TLS cert files, and starts the API server.
    Why: Enables "press Run on one file" developer ergonomics without weakening security defaults.
    """
    try:
        root = repo_root.resolve()
        base_config_path = root / "config" / "config.json"
        if not base_config_path.is_file():
            raise ValueError(f"Missing base config file: {base_config_path}")

        base = _read_json_dict(base_config_path)
        tls_dir = root / ".local" / "tls"
        tls_dir.mkdir(parents=True, exist_ok=True)
        cert_path = tls_dir / "agent-cert.pem"
        key_path = tls_dir / "agent-key.pem"

        lan_ip = _best_effort_lan_ip()
        token = secrets.token_urlsafe(32)
        port = _pick_free_port("0.0.0.0")

        tls_ready, tls_error = _ensure_self_signed_cert(cert_path=cert_path, key_path=key_path)
        allow_lan = lan_ip is not None
        tls_enabled = bool(tls_ready and allow_lan)

        api_overrides: JsonDict = {
            "enabled": True,
            "bind_host": "0.0.0.0" if allow_lan else "127.0.0.1",
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
        }

        if allow_lan and not tls_enabled:
            api_overrides["allow_insecure_http_lan"] = True

        derived = _build_config_with_api_overrides(base, api_overrides)
        derived_path = root / ".local" / "one-click-config.json"
        derived_path.parent.mkdir(parents=True, exist_ok=True)
        derived_path.write_text(json.dumps(derived, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        os.environ["MAC_HEALTH_CHECKUP_CONFIG"] = str(derived_path)
        if allow_lan and lan_ip is not None:
            scheme = "https" if tls_enabled else "http"
            os.environ["MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL"] = f"{scheme}://{lan_ip}:{port}"

        print("One-click agent configuration written to:")
        print(str(derived_path))
        if allow_lan:
            scheme = "https" if tls_enabled else "http"
            print(f"LAN URL: {scheme}://{lan_ip}:{port}")
            if tls_error:
                print(f"TLS warning: {tls_error}")
        else:
            print(f"Local URL: http://127.0.0.1:{port}")
            if tls_error:
                print(f"TLS note: {tls_error}")

        print()
        print(
            "This one-click runner starts the agent API server only (headless). No UI window opens on this Mac."
        )
        print("Next steps:")
        print("- iOS UI: open the iOS app and paste the pairing payload JSON (QR code is optional).")
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


def _build_config_with_api_overrides(base: JsonDict, api_overrides: Mapping[str, JsonValue]) -> JsonDict:
    """
    Purpose: Return a full config with only the API section overridden.
    Ties: Used by run_one_click_agent to avoid requiring users to edit config/config.json.
    Inputs: base is the existing full config dict, api_overrides are values for the `api` section.
    Outputs: A new dict representing the derived config.
    Side effects: None.
    Why: Keeps configuration centralized while enabling a per-run developer overlay.
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
    Purpose: Read a JSON object from disk and validate it is a dict.
    Ties: Used by run_one_click_agent.
    Inputs: path to JSON file.
    Outputs: JSON dict.
    Side effects: Reads from disk.
    Why: Keeps IO and validation centralized with clear error messages.
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
    Purpose: Pick a free TCP port on the given bind host.
    Ties: Used by one-click runner.
    Inputs: bind_host string.
    Outputs: Port int.
    Side effects: Binds and closes a temporary socket.
    Why: Avoids port conflicts and reduces setup friction.
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((bind_host, 0))
            return int(sock.getsockname()[1])
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_pick_free_port", "Failed to pick port", exc)) from exc


def _best_effort_lan_ip() -> str | None:
    """
    Purpose: Best-effort derive a LAN-reachable IP address for the current machine.
    Ties: Used by one-click runner to print a usable URL.
    Inputs: None.
    Outputs: IP string or None if unavailable.
    Side effects: Opens a UDP socket without sending traffic.
    Why: Users should not have to manually find their LAN IP to pair the iOS app.
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
    Purpose: Ensure a self-signed TLS certificate exists for the agent.
    Ties: Used by one-click runner to enable secure LAN mode.
    Inputs: cert_path and key_path output paths.
    Outputs: (ready, warning_message).
    Side effects: May run openssl to generate cert files.
    Why: TLS should be easy to enable without manual certificate tooling steps.
    """
    try:
        if cert_path.is_file() and key_path.is_file():
            return True, None

        openssl = _find_executable("openssl")
        if openssl is None:
            return False, "openssl not found, cannot auto-generate TLS certs"

        cert_path.parent.mkdir(parents=True, exist_ok=True)
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
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
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
    Purpose: Locate an executable in PATH.
    Ties: Used by TLS generation helper.
    Inputs: name of the executable.
    Outputs: Absolute path string or None.
    Side effects: Reads PATH environment variable.
    Why: Avoids brittle assumptions about tool install locations.
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
