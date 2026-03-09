from __future__ import annotations

import math

from mac_health_checkup.diagnostics.thermals.processing.dedupe import update_best_by_label
from mac_health_checkup.diagnostics.thermals.processing.status import status_for_temp


def test_update_best_by_label_keeps_hottest_and_ignores_blank_labels() -> None:
    """
    Summary
    Execute `test_update_best_by_label_keeps_hottest_and_ignores_blank_labels` for its module-level responsibility.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_thermals_processing_unit.py:test_update_best_by_label_keeps_hottest_and_ignores_blank_labels` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_thermals_processing_unit.py`.

    Why this exists
    Keeps `test_update_best_by_label_keeps_hottest_and_ignores_blank_labels` explicit, testable, and maintainable.
    """
    best: dict[str, float] = {"CPU": 72.0}
    update_best_by_label(
        best,
        samples=[
            ("", 90.0),
            ("CPU", 71.0),
            ("CPU", 73.5),
            ("GPU", 65.0),
        ],
    )
    assert best == {"CPU": 73.5, "GPU": 65.0}


def test_status_for_temp_maps_thresholds_and_handles_non_finite_values() -> None:
    """
    Summary
    Execute `test_status_for_temp_maps_thresholds_and_handles_non_finite_values` for its module-level responsibility.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_thermals_processing_unit.py:test_status_for_temp_maps_thresholds_and_handles_non_finite_values` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_thermals_processing_unit.py`.

    Why this exists
    Keeps `test_status_for_temp_maps_thresholds_and_handles_non_finite_values` explicit, testable, and maintainable.
    """
    assert status_for_temp(50.0, warn=70.0, bad=90.0) == "ok"
    assert status_for_temp(70.0, warn=70.0, bad=90.0) == "warn"
    assert status_for_temp(89.9, warn=70.0, bad=90.0) == "warn"
    assert status_for_temp(90.0, warn=70.0, bad=90.0) == "bad"
    assert status_for_temp(float("nan"), warn=70.0, bad=90.0) == "ok"
    assert status_for_temp(math.inf, warn=70.0, bad=90.0) == "ok"
