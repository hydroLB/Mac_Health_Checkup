from __future__ import annotations

from mac_health_checkup.app.help_text import metric, section, table_header

MODULE_PATH = "tests/test_help_text.py"


def test_section_help_text_non_empty() -> None:
    """
    Purpose: Ensure section help text exists for core sections.
    Ties: Exercises mac_health_checkup.app.help_text.section.
    Inputs: None.
    Outputs: Assertions on returned strings.
    Side effects: None.
    Why: Prevents hover tooltips from regressing into empty strings.
    """
    try:
        for key in ("performance", "general", "power", "battery", "network", "devices", "ports", "input"):
            text = section(key)
            assert isinstance(text, str)
            assert text.strip()
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_section_help_text_non_empty failed: {exc}") from exc


def test_metric_and_table_help_fallbacks() -> None:
    """
    Purpose: Ensure metric and table header help fall back to section help when unknown.
    Ties: Exercises mac_health_checkup.app.help_text.metric and table_header.
    Inputs: Unknown labels/headers.
    Outputs: Assertions that fallbacks are non-empty.
    Side effects: None.
    Why: UI hover should always show something informative.
    """
    try:
        out1 = metric("battery", "Not A Metric")
        assert out1.strip()
        out2 = table_header("display", "Not A Header")
        assert out2.strip()
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_metric_and_table_help_fallbacks failed: {exc}") from exc
