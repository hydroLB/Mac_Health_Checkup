from __future__ import annotations

import math

from mac_health_checkup.diagnostics.thermals.processing.dedupe import update_best_by_label
from mac_health_checkup.diagnostics.thermals.processing.status import status_for_temp


def test_update_best_by_label_keeps_hottest_and_ignores_blank_labels() -> None:
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
    assert status_for_temp(50.0, warn=70.0, bad=90.0) == "ok"
    assert status_for_temp(70.0, warn=70.0, bad=90.0) == "warn"
    assert status_for_temp(89.9, warn=70.0, bad=90.0) == "warn"
    assert status_for_temp(90.0, warn=70.0, bad=90.0) == "bad"
    assert status_for_temp(float("nan"), warn=70.0, bad=90.0) == "ok"
    assert status_for_temp(math.inf, warn=70.0, bad=90.0) == "ok"
