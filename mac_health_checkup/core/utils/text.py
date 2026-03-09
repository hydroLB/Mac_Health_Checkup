from __future__ import annotations

from typing import Sequence

from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/utils/text.py"


def calc_col_widths(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> tuple[int, ...]:
    """
    Summary
    Calculate maximum column widths for table rendering.

    Inputs
    headers: Header strings.
    rows: Table rows.

    Outputs
    Tuple of integer column widths.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when width computation fails.

    Ties to other methods
    Used by `render_table_parts` and GUI sections.

    Why this exists
    Keeps table alignment consistent across sections.
    """
    try:
        widths = [len(header) for header in headers]
        for row in rows:
            for idx, cell in enumerate(row):
                if idx < len(widths):
                    widths[idx] = max(widths[idx], len(cell))
        return tuple(widths)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "calc_col_widths", "Failed to calc widths", exc)
        ) from exc


def render_table_parts(headers: tuple[str, ...], rows: Sequence[tuple[str, ...]]) -> tuple[str, str]:
    """
    Summary
    Render table headers and body as aligned text.

    Inputs
    headers: Header strings.
    rows: Table rows.

    Outputs
    Tuple of (header_line, body_text).

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails.

    Ties to other methods
    Uses `calc_col_widths` and is used by display rendering and CLI table output.

    Why this exists
    Provides a consistent text table rendering utility.
    """
    try:
        widths = calc_col_widths(headers, rows)
        fmt_row = "  ".join(f"{{:<{w}}}" for w in widths)
        header_line = fmt_row.format(*headers)
        sep_line = "-" * len(header_line)
        body_lines = [fmt_row.format(*row) for row in rows]
        return f"{header_line}\n{sep_line}", "\n".join(body_lines)
    except (TypeError, ValueError, IndexError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "render_table_parts", "Failed to render table", exc)
        ) from exc
