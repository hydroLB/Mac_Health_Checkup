from __future__ import annotations

from typing import Sequence

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.text import render_table_parts

MODULE_PATH = "mac_health_checkup/app/gui/sections/display/rendering.py"


def render_display_table(rows: Sequence[tuple[str, ...]]) -> tuple[str, str]:
    """
    Purpose: Render the display table header and body text.
    Ties: Used by display section and tests.
    Inputs: rows are display row tuples including transport.
    Outputs: Tuple of (header_text, body_text).
    Side effects: None.
    Why: Centralizes display table rendering.
    """
    try:
        headers = tuple(get_config().gui.display_headers)
        return render_table_parts(headers, rows)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "render_display_table", "Failed to render display table", exc)
        ) from exc
