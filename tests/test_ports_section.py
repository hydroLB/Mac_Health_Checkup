from __future__ import annotations

import unittest

from mac_health_checkup.app.gui.sections.ports import (
    _annotate_usb_tree_labels,
    _compute_depths,
    _extract_external_display_names,
)

MODULE_PATH = "tests/test_ports_section.py"


class PortsSectionHelpersTests(unittest.TestCase):
    """
    Summary
    Validate Ports section helpers produce stable nesting and user-friendly labels.

    Inputs
    None.

    Outputs
    Assertions on computed depths and annotations.

    Side effects
    None.

    Error handling
    Test methods raise `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises Ports section helper functions.

    Why this exists
    Ports rendering must be correct and understandable, especially when system_profiler indentation varies.
    """

    def test_compute_depths_handles_irregular_indentation(self) -> None:
        """
        Summary
        Ensure depth computation does not rely on a fixed indent step.

        Inputs
        None.

        Outputs
        Assertions on computed depths.

        Side effects
        None.

        Error handling
        Raises `AssertionError` with module and test context when expectations are not met.

        Ties to other methods
        Exercises `_compute_depths`.

        Why this exists
        system_profiler mixes indentation widths, and a fixed step can flatten the USB topology.
        """
        try:
            items: list[dict[str, int | str]] = [
                {"label": "USB 3.1 Bus", "indent": 4},
                {"label": "USB2.0 HUB", "indent": 8},
                {"label": "USB Receiver", "indent": 12},
                {"label": "Keyboard", "indent": 12},
                {"label": "USB 10/100 LAN", "indent": 8},
                {"label": "USB 3.1 Bus", "indent": 4},
                {"label": "USB 2.0 BILLBOARD", "indent": 8},
            ]
            depths = _compute_depths(items)
            self.assertEqual(depths, [0, 1, 2, 2, 1, 0, 1])
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:PortsSectionHelpersTests.test_compute_depths_handles_irregular_indentation failed: {exc}"
            ) from exc

    def test_annotate_usb_tree_labels_marks_display_ports_and_billboard_nodes(self) -> None:
        """
        Summary
        Ensure display hints show up for USB-C billboard devices and their root bus.

        Inputs
        None.

        Outputs
        Assertions on annotated labels.

        Side effects
        None.

        Error handling
        Raises `AssertionError` with module and test context when expectations are not met.

        Ties to other methods
        Exercises `_annotate_usb_tree_labels`.

        Why this exists
        Users should immediately understand which USB port is carrying the external display.
        """
        try:
            labels = [
                "USB 3.1 Bus",
                "USB2.0 HUB",
                "USB Receiver",
                "Keyboard",
                "USB 10/100 LAN",
                "USB 3.1 Bus",
                "USB 2.0 BILLBOARD",
            ]
            depths = [0, 1, 2, 2, 1, 0, 1]
            updated = _annotate_usb_tree_labels(labels, depths, ["DELL U2720Q"])
            self.assertEqual(updated[0], "USB 3.1 Bus")
            self.assertIn("(Display: DELL U2720Q)", updated[5])
            self.assertEqual(updated[6], "Display Alt Mode: DELL U2720Q")
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:PortsSectionHelpersTests.test_annotate_usb_tree_labels_marks_display_ports_and_billboard_nodes failed: {exc}"
            ) from exc

    def test_extract_external_display_names_ignores_gpu_headers_and_builtin_panels(self) -> None:
        """
        Summary
        Extract external display names without picking up GPU headers.

        Inputs
        None.

        Outputs
        Assertions on extracted names.

        Side effects
        None.

        Error handling
        Raises `AssertionError` with module and test context when expectations are not met.

        Ties to other methods
        Exercises `_extract_external_display_names`.

        Why this exists
        SPDisplaysDataType includes GPU blocks that should never be treated as display devices.
        """
        try:
            raw = """
Graphics/Displays:

    Apple M3 Pro:

      Chipset Model: Apple M3 Pro
      Bus: Built-In

        Color LCD:
          Display Type: Built-In Retina LCD
          Connection Type: Internal

        DELL U2720Q:
          Display Type: LCD
          Connection Type: USB-C
"""
            self.assertEqual(_extract_external_display_names(raw), ["DELL U2720Q"])
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:PortsSectionHelpersTests.test_extract_external_display_names_ignores_gpu_headers_and_builtin_panels failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
