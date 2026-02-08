from __future__ import annotations

import unittest

from mac_health_checkup.core.utils.usb_tree import _extract_usb_tree_items

MODULE_PATH = "tests/test_usb_tree.py"


class UsbTreeParserTests(unittest.TestCase):
    """
    Summary
    Validate USB tree parsing does not treat property lines as devices.

    Inputs
    None.

    Outputs
    Assertions on parsed labels.

    Side effects
    None.

    Error handling
    Failures bubble as unittest assertions with module context.

    Ties to other methods
    Exercises `mac_health_checkup.core.utils.usb_tree._extract_usb_tree_items`.

    Why this exists
    Prevents noisy, misleading device lists like "Host Controller Driver" appearing in the UI.
    """

    def test_extract_usb_tree_items_ignores_key_value_properties(self) -> None:
        """
        Summary
        Ensure key:value properties are ignored while device header lines are preserved.

        Inputs
        None.

        Outputs
        Assertions on extracted device labels.

        Side effects
        None.

        Error handling
        Raises `AssertionError` with module and test context on unexpected outcomes.

        Ties to other methods
        Exercises `_extract_usb_tree_items`.

        Why this exists
        `system_profiler SPUSBDataType` includes many properties that should not show as devices.
        """
        try:
            raw = """
USB:

    USB 3.1 Bus:

        Host Controller Driver: AppleUSBXHCISPT
        PCI Device ID: 0x0000
        PCI Revision ID: 0x0000

        USB2.0 HUB:

            Manufacturer: Example Corp.
            Product ID: 0x1234
            Vendor ID: 0x5678
            Device: My Keyboard
"""
            items = _extract_usb_tree_items(raw)
            labels = [item.get("label") for item in items if isinstance(item.get("label"), str)]
            self.assertIn("USB 3.1 Bus", labels)
            self.assertIn("USB2.0 HUB", labels)
            self.assertIn("My Keyboard", labels)
            self.assertNotIn("Host Controller Driver", labels)
            self.assertNotIn("PCI Device ID", labels)
            self.assertNotIn("Manufacturer", labels)
            self.assertNotIn("Product ID", labels)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:UsbTreeParserTests.test_extract_usb_tree_items_ignores_key_value_properties failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
