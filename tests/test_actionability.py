from __future__ import annotations

from mac_health_checkup.app.actionability import (
    build_section_advice,
    should_fail_on,
    worst_severity_from_metrics,
)

MODULE_PATH = "tests/test_actionability.py"


def test_worst_severity_from_metrics() -> None:
    """
    Summary
    Ensure worst severity selection prefers bad over warn over ok.

    Inputs
    Synthetic metrics rows with status labels.

    Outputs
    Assertions on severity.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `worst_severity_from_metrics` used by automation.

    Why this exists
    Fail-on behavior must be deterministic.
    """
    try:
        assert worst_severity_from_metrics([("A", "1", "ok")]) == "ok"
        assert worst_severity_from_metrics([("A", "1", "info")]) == "ok"
        assert worst_severity_from_metrics([("A", "1", "warn")]) == "warn"
        assert worst_severity_from_metrics([("A", "1", "warn"), ("B", "2", "bad")]) == "bad"
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
        raise AssertionError(f"{MODULE_PATH}:test_worst_severity_from_metrics failed: {exc}") from exc


def test_should_fail_on_thresholds() -> None:
    """
    Summary
    Ensure fail thresholds behave as expected for warn and bad.

    Inputs
    Synthetic severities.

    Outputs
    Assertions on decisions.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `should_fail_on`.

    Why this exists
    Automation should not silently accept warn or bad signals.
    """
    try:
        assert should_fail_on("ok", None) is False
        assert should_fail_on("ok", "warn") is False
        assert should_fail_on("warn", "warn") is True
        assert should_fail_on("bad", "warn") is True
        assert should_fail_on("warn", "bad") is False
        assert should_fail_on("bad", "bad") is True
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
        raise AssertionError(f"{MODULE_PATH}:test_should_fail_on_thresholds failed: {exc}") from exc


def test_build_section_advice_battery_health_in_diagnosis() -> None:
    """
    Summary
    Ensure battery advice uses the Health metric for the diagnosis string.

    Inputs
    Battery section metrics.

    Outputs
    Assertions on diagnosis and severity.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `build_section_advice` special-casing.

    Why this exists
    The diagnosis string is the primary actionability output users read.
    """
    try:
        advice = build_section_advice(
            "battery",
            field="ignored",
            metrics=[("Health", "85% (good)", "ok"), ("Cycle count", "120", "info")],
            diagnostics={"ok": True},
        )
        assert advice["severity"] == "ok"
        diagnosis = str(advice["diagnosis"])
        assert "Battery health" in diagnosis
        assert "85% (good)" in diagnosis
        assert "Cycle count" in diagnosis
        steps = advice.get("next_steps")
        assert isinstance(steps, list)
        assert steps
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
        raise AssertionError(
            f"{MODULE_PATH}:test_build_section_advice_battery_health_in_diagnosis failed: {exc}"
        ) from exc
