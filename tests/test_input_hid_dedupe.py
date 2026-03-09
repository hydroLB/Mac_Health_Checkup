from __future__ import annotations

from mac_health_checkup.diagnostics.devices import _finalize_hid_kinds


def test_finalize_hid_kinds_collapses_keyboard_mouse_duplicates() -> None:
    """
    Summary
    Execute `test_finalize_hid_kinds_collapses_keyboard_mouse_duplicates` for its module-level responsibility.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_input_hid_dedupe.py:test_finalize_hid_kinds_collapses_keyboard_mouse_duplicates` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_input_hid_dedupe.py`.

    Why this exists
    Keeps `test_finalize_hid_kinds_collapses_keyboard_mouse_duplicates` explicit, testable, and maintainable.
    """
    assert _finalize_hid_kinds("Razer BlackWidow V3 Tenkeyless", {"Keyboard", "Mouse"}) == "Keyboard"


def test_finalize_hid_kinds_backlight_and_receiver_are_special() -> None:
    """
    Summary
    Execute `test_finalize_hid_kinds_backlight_and_receiver_are_special` for its module-level responsibility.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_input_hid_dedupe.py:test_finalize_hid_kinds_backlight_and_receiver_are_special` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_input_hid_dedupe.py`.

    Why this exists
    Keeps `test_finalize_hid_kinds_backlight_and_receiver_are_special` explicit, testable, and maintainable.
    """
    assert _finalize_hid_kinds("Keyboard Backlight", {"Keyboard"}) == "Backlight"
    assert _finalize_hid_kinds("USB Receiver", {"Keyboard", "Mouse"}) == "Mouse"
