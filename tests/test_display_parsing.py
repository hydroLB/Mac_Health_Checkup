from __future__ import annotations

import unittest

from mac_health_checkup.app.gui.sections.display.parsing import (
    _parse_ioreg_display_rows,
    _parse_raw_display_rows,
)

MODULE_PATH = "tests/test_display_parsing.py"


class DisplayParsingTests(unittest.TestCase):
    """
    Summary
    Validate display parsing only returns real display rows, not chipset blocks.

    Inputs
    None.

    Outputs
    Assertions on parsed rows.

    Side effects
    None.

    Error handling
    Test methods raise `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `_parse_raw_display_rows`.

    Why this exists
    Some system_profiler outputs include a chipset model section that must not be treated as a display.
    """

    def test_parse_raw_display_rows_ignores_chipset_and_reads_displays(self) -> None:
        """
        Summary
        Ensure the parser keys off the Displays section and extracts display properties.

        Inputs
        None.

        Outputs
        Assertions on parsed rows.

        Side effects
        None.

        Error handling
        Raises `AssertionError` with module and test context when expectations are not met.

        Ties to other methods
        Exercises `_parse_raw_display_rows` state machine.

        Why this exists
        Prevents bogus display names like the GPU model showing up in the Display table.
        """
        try:
            raw = """
Graphics/Displays:

    Apple M3 Pro:

      Chipset Model: Apple M3 Pro
      Type: GPU

      Displays:

        Color LCD:
          Display Type: Built-In Liquid Retina XDR Display
          Resolution: 3456 x 2234 Retina
          Mirror: Off
          Connection Type: Internal
          Refresh Rate: 120 Hz

        DELL U2720Q:
          Resolution: 3840 x 2160 @ 60Hz
          Mirror: Off
          Connection Type: USB-C
          Refresh Rate: 60 Hz
"""
            rows = _parse_raw_display_rows(raw)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][0], "Color LCD")
            self.assertIn("3456", rows[0][1])
            self.assertEqual(rows[0][2], "")
            self.assertEqual(rows[0][3], "Internal")
            self.assertIn("120", rows[0][4])
            self.assertEqual(rows[1][0], "DELL U2720Q")
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:DisplayParsingTests.test_parse_raw_display_rows_ignores_chipset_and_reads_displays failed: {exc}"
            ) from exc

    def test_parse_ioreg_display_rows_extracts_resolution_and_refresh(self) -> None:
        """
        Summary
        Ensure ioreg parsing extracts resolution and fixed-point refresh rates.

        Inputs
        None.

        Outputs
        Assertions on parsed rows.

        Side effects
        None.

        Error handling
        Raises `AssertionError` with module and test context when expectations are not met.

        Ties to other methods
        Exercises `_parse_ioreg_display_rows` fallback path.

        Why this exists
        Some macOS builds omit per-display inventory in SPDisplaysDataType; IORegistry should still populate the Display table.
        """
        try:
            raw = """
+-o IOMobileFramebufferShim  <class IOMobileFramebufferShim, id 0x1, registered, matched, active, busy 0, retain 16>
  | {
  |   "DisplayHeight" = 2234
  |   "PreferredTimingElements" = ({"VerticalAttributes"={"SyncRate"=7864320}})
  |   "DisplayWidth" = 3456
  | }

+-o IOMobileFramebufferShim  <class IOMobileFramebufferShim, id 0x2, registered, matched, active, busy 0, retain 13>
  | {
  |   "external" = Yes
  |   "EDID UUID" = "10AC75A2-0000-0000-0C23-0104B53C2278"
  |   "DisplayWidth" = 3840
  |   "DisplayHeight" = 2160
  |   "PreferredTimingElements" = ({"VerticalAttributes"={"SyncRate"=3932160}})
  | }
"""
            rows = _parse_ioreg_display_rows(raw)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0][0], "Built-in Display")
            self.assertEqual(rows[0][1], "3456 x 2234")
            self.assertIn("120", rows[0][4])
            self.assertEqual(rows[0][5], "Internal")
            self.assertTrue(rows[1][0].startswith("External Display 10AC75A2"))
            self.assertEqual(rows[1][1], "3840 x 2160")
            self.assertIn("60", rows[1][4])
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:DisplayParsingTests.test_parse_ioreg_display_rows_extracts_resolution_and_refresh failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
