from __future__ import annotations

import shutil

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/executables.py"


def resolve_executable(name: str) -> str | None:
    """
    Summary
    Resolve an executable path for usage when PATH may differ under sudo.

    Inputs
    name: Tool name such as `istats`.

    Outputs
    Absolute path string, or `None` when not found.

    Side effects
    Reads PATH via `shutil.which`.

    Error handling
    Raises `RuntimeError` with module and method context when resolution fails unexpectedly.

    Ties to other methods
    Used by thermals authorization and collection to call `istats` reliably on macOS.

    Why this exists
    `sudo` on macOS can use a restricted secure_path, which breaks lookups for `/usr/local/bin` tools.
    """
    try:
        path = shutil.which(name)
        if not path:
            return None
        return str(path)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "resolve_executable", f"Failed to resolve executable: {name}", exc)
        ) from exc
