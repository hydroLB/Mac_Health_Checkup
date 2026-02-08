from __future__ import annotations

from mac_health_checkup.app.gui.sections.display.section import _display_row_sort_key

MODULE_PATH = "tests/test_display_section_order.py"


def test_display_internal_row_sorted_first() -> None:
    """
    Summary
    Ensure the built-in display (Color LCD) sorts to the top of the display list.

    Inputs
    Representative display rows.

    Outputs
    Assertion that internal display sorts first.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `_display_row_sort_key`.

    Why this exists
    Makes the built-in display easy to find when multiple displays are connected.
    """
    try:
        rows = [
            ("External Display AAAA", "3840 x 2160", "", "External", "60 Hz", "External"),
            ("Color LCD", "3456 x 2234", "", "Built-In", "120 Hz", "Internal"),
            ("External Display BBBB", "3840 x 2160", "", "External", "60 Hz", "External"),
        ]
        sorted_rows = [row for _, row in sorted(enumerate(rows), key=_display_row_sort_key)]
        assert sorted_rows[0][0] == "Color LCD"
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_display_internal_row_sorted_first failed: {exc}") from exc
