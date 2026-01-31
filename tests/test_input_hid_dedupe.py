from __future__ import annotations

from mac_health_checkup.diagnostics.devices import _finalize_hid_kinds


def test_finalize_hid_kinds_collapses_keyboard_mouse_duplicates() -> None:
    assert _finalize_hid_kinds("Razer BlackWidow V3 Tenkeyless", {"Keyboard", "Mouse"}) == "Keyboard"


def test_finalize_hid_kinds_backlight_and_receiver_are_special() -> None:
    assert _finalize_hid_kinds("Keyboard Backlight", {"Keyboard"}) == "Backlight"
    assert _finalize_hid_kinds("USB Receiver", {"Keyboard", "Mouse"}) == "Mouse"
