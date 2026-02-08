from __future__ import annotations

import shutil
import subprocess  # nosec B404

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/qr.py"


def qrencode_available() -> bool:
    """
    Summary
    Determine whether the optional `qrencode` command is available on the host.

    Inputs
    None.

    Outputs
    True when `qrencode` is discoverable on PATH, else false.

    Side effects
    Reads PATH via `shutil.which`.

    Error handling
    Never raises; returns false on unexpected errors.

    Ties to other methods
    Used by `maybe_render_qr_ansiutf8` to decide whether QR rendering is possible.

    Why this exists
    QR generation is best-effort and should degrade gracefully when optional tooling is missing.
    """
    try:
        return shutil.which("qrencode") is not None
    except Exception:
        return False


def maybe_render_qr_ansiutf8(data: str, *, timeout_sec: int) -> str | None:
    """
    Summary
    Render a QR code for a given payload using `qrencode` (ANSI UTF-8), when available.

    Inputs
    data: Payload to encode in the QR code.
    timeout_sec: Subprocess timeout in seconds.

    Outputs
    Rendered QR code string suitable for terminal output, or None when unavailable.

    Side effects
    Executes `qrencode` as a subprocess.

    Error handling
    Returns None when `qrencode` is missing. Raises `RuntimeError` with context when the subprocess fails
    unexpectedly.

    Ties to other methods
    Used by the `--serve` entrypoint to display a pairing QR code for the iOS client.

    Why this exists
    A terminal QR code improves pairing ergonomics without introducing a required runtime dependency.
    """
    try:
        if not isinstance(data, str) or not data:
            return None
        qrencode_path = shutil.which("qrencode")
        if qrencode_path is None:
            return None
        timeout = max(1, int(timeout_sec))
        completed = subprocess.run(  # nosec B603
            [qrencode_path, "-t", "ANSIUTF8"],
            input=data,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            return None
        out = completed.stdout or ""
        qr = out.rstrip("\n")
        return qr if qr.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "maybe_render_qr_ansiutf8", "Failed to render QR", exc)
        ) from exc
