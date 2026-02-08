from __future__ import annotations

MODULE_PATH = "mac_health_checkup/diagnostics/thermals/processing/dedupe.py"


def update_best_by_label(best_by_label: dict[str, float], samples: list[tuple[str, float]]) -> None:
    """
    Summary
    Merge temperature samples into a best-by-label map, keeping the hottest reading per sensor label.

    Inputs
    best_by_label: Mutable mapping of label to best (max) temperature seen so far.
    samples: List of (label, celsius) tuples.

    Outputs
    None.

    Side effects
    Mutates `best_by_label` in place.

    Error handling
    Never raises. Invalid entries are ignored.

    Ties to other methods
    Used by thermals collectors when combining readings across multiple HID page/usage candidates.

    Why this exists
    IOHID can expose duplicate services across candidates; keeping a single stable value per label prevents confusing duplicate rows in the UI.
    """
    try:
        for name, celsius in samples:
            if not name:
                continue
            existing = best_by_label.get(name)
            if existing is None or float(celsius) > float(existing):
                best_by_label[name] = float(celsius)
    except Exception:
        return
