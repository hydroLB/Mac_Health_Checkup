from __future__ import annotations

from mac_health_checkup.app.gui.sections.devices import _filter_device_labels


def test_devices_filter_keeps_real_adapters_and_hides_infrastructure() -> None:
    """
    Summary
    Execute `test_devices_filter_keeps_real_adapters_and_hides_infrastructure` for its module-level responsibility.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tests/test_devices_section.py:test_devices_filter_keeps_real_adapters_and_hides_infrastructure` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tests/test_devices_section.py`.

    Why this exists
    Keeps `test_devices_filter_keeps_real_adapters_and_hides_infrastructure` explicit, testable, and maintainable.
    """
    labels = [
        "USB 3.1 Bus",
        "USB2.0 HUB",
        "USB 2.0 BILLBOARD",
        "USB 10/100/1G/2.5G LAN",
        "USB Receiver",
        "Ethernet Adapter",
    ]
    filtered = _filter_device_labels(
        labels,
        skip_keywords=["hub", "billboard", "bus", "lan", "ethernet"],
        allow_keywords=["receiver"],
        max_len=200,
    )
    assert "USB Receiver" in filtered
    assert "USB 10/100/1G/2.5G LAN" in filtered
    assert "Ethernet Adapter" in filtered
    assert "USB 3.1 Bus" not in filtered
    assert "USB2.0 HUB" not in filtered
    assert "USB 2.0 BILLBOARD" not in filtered
