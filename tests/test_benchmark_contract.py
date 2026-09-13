from __future__ import annotations

from benchmarks.run import _sample_display_text, _sample_usb_text
from mac_health_checkup.app.gui.sections.display.parsing import _parse_raw_display_rows
from mac_health_checkup.core.utils import parse_usb_tree_items

MODULE_PATH = "tests/test_benchmark_contract.py"


def test_benchmark_fixtures_exercise_real_multiline_parser_paths() -> None:
    """
    Summary
    Prove the benchmark fixtures drive representative multiline display and USB parsing.

    Inputs
    None.

    Outputs
    Assertions on the normalized display rows and USB device hierarchy.

    Side effects
    Loads the cached repository configuration used by display parsing.

    Error handling
    Raises `AssertionError` with module and test context if a fixture becomes synthetic or stops exercising a parser.

    Ties to other methods
    Exercises the fixtures timed by `benchmarks/run.py` through their production parser entrypoints.

    Why this exists
    A literal backslash-n fixture can benchmark an empty fallback path at impressive but meaningless throughput.
    """
    try:
        display_rows = _parse_raw_display_rows(_sample_display_text())
        usb_items = parse_usb_tree_items(_sample_usb_text())

        assert display_rows == [
            ("Color LCD", "2560 x 1600", "", "Internal", "60Hz"),
            ("DELL U2718Q", "3840 x 2160", "", "DisplayPort", "60Hz"),
        ]
        assert usb_items == [
            {"label": "USB 3.0 Bus", "indent": 8},
            {"label": "Magic Trackpad", "indent": 12},
            {"label": "USB 2.0 Bus", "indent": 8},
            {"label": "USB Keyboard", "indent": 12},
        ]
    except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_benchmark_fixtures_exercise_real_multiline_parser_paths failed: {exc}"
        ) from exc
