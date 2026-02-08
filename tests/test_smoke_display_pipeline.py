from mac_health_checkup.app.gui.sections.display.parsing import _parse_raw_display_rows
from mac_health_checkup.app.gui.sections.display.rendering import render_display_table

MODULE_PATH = "tests/test_smoke_display_pipeline.py"


def test_smoke_display_pipeline() -> None:
    """
    Summary
    Smoke test the display parsing and rendering pipeline.

    Inputs
    Synthetic `system_profiler` display output.

    Outputs
    Assertions on generated header and body content.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `_parse_raw_display_rows` and `render_display_table`.

    Why this exists
    Confirms parsing and rendering stay compatible for basic inputs.
    """
    try:
        raw = (
            "Graphics/Displays:\n"
            "    Color LCD:\n"
            "      Resolution: 2560 x 1600\n"
            "      Mirror: Off\n"
            "      Connection Type: Internal\n"
            "      Refresh Rate: 60 Hz\n"
        )
        parsed_rows = _parse_raw_display_rows(raw)
        rows_with_transport = [row + ("?",) for row in parsed_rows]
        header, body = render_display_table(rows_with_transport)
        assert "Resolution" in header
        assert "Color LCD" in body
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_smoke_display_pipeline failed: {exc}") from exc
