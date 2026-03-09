from mac_health_checkup.core.utils.regex_utils import (
    hz_from_text,
    regex_extract_float,
    regex_extract_int,
    regex_extract_str,
)

MODULE_PATH = "tests/test_regex_utils.py"


def test_regex_extract_int() -> None:
    """
    Summary
    Verify integer extraction from regex helpers.

    Inputs
    Sample text and regex pattern.

    Outputs
    Assertions on parsed integer value.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `regex_extract_int`.

    Why this exists
    Confirms integer parsing for diagnostics output.
    """
    try:
        text = "Cycle Count: 120"
        assert regex_extract_int(text, r"Cycle Count:\s*(\d+)") == 120
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
        raise AssertionError(f"{MODULE_PATH}:test_regex_extract_int failed: {exc}") from exc


def test_regex_extract_float() -> None:
    """
    Summary
    Verify float extraction from regex helpers.

    Inputs
    Sample text and regex pattern.

    Outputs
    Assertions on parsed float value.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `regex_extract_float`.

    Why this exists
    Confirms float parsing for diagnostics output.
    """
    try:
        text = "Temperature: 42.5 C"
        assert regex_extract_float(text, r"Temperature:\s*([\d.]+)") == 42.5
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
        raise AssertionError(f"{MODULE_PATH}:test_regex_extract_float failed: {exc}") from exc


def test_regex_extract_str() -> None:
    """
    Summary
    Verify string extraction from regex helpers.

    Inputs
    Sample text and regex pattern.

    Outputs
    Assertions on parsed string value.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `regex_extract_str`.

    Why this exists
    Confirms string parsing for diagnostics output.
    """
    try:
        text = "Model: MacBookPro"
        assert regex_extract_str(text, r"Model:\s*(\w+)") == "MacBookPro"
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
        raise AssertionError(f"{MODULE_PATH}:test_regex_extract_str failed: {exc}") from exc


def test_hz_from_text() -> None:
    """
    Summary
    Verify refresh rate extraction and normalization.

    Inputs
    Sample display strings with refresh rates.

    Outputs
    Assertions on normalized Hz strings.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `hz_from_text`.

    Why this exists
    Ensures refresh rate parsing stays consistent.
    """
    try:
        assert hz_from_text("Refresh Rate: 60 Hz") == "60Hz"
        assert hz_from_text("Resolution @ 144.00Hz") == "144Hz"
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
        raise AssertionError(f"{MODULE_PATH}:test_hz_from_text failed: {exc}") from exc
