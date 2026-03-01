from __future__ import annotations

import unittest

from mac_health_checkup.diagnostics.display_transport import (
    _merge_transports,
    _normalize_transport,
    _parse_refresh_hz,
    _parse_resolution,
    _parse_transports,
    _split_display_blocks,
)

MODULE_PATH = "tests/test_display_transport_parsing.py"


class DisplayTransportParsingTests(unittest.TestCase):
    """
    Summary
    Validate display transport parsing and bandwidth formatting helpers.

    Inputs
    None.

    Outputs
    Assertions on parsed and normalized transport labels.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises helpers in `mac_health_checkup/diagnostics/display_transport.py`.

    Why this exists
    Transport labels are noisy in system_profiler output and must be normalized consistently for UI and reports.
    """

    def test_parse_transports_and_normalize(self) -> None:
        """
        Summary
        Ensure Connection Type values are extracted and normalized to stable labels.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_parse_transports` and `_normalize_transport`.

        Why this exists
        Normalization prevents UI flapping and keeps report diffs stable.
        """
        try:
            raw = "\n".join(
                [
                    "Connection Type: Internal",
                    "Connection Type: Thunderbolt",
                    "Connection Type: HDMI",
                    "Connection Type: USB-C",
                    "Connection Type: AirPlay",
                ]
            )
            parsed = _parse_transports(raw)
            self.assertEqual(parsed, ["Internal", "DisplayPort", "HDMI", "USB", "Wireless"])
            self.assertEqual(_normalize_transport("Built-in"), "Internal")
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
                f"{MODULE_PATH}:DisplayTransportParsingTests.test_parse_transports_and_normalize failed: {exc}"
            ) from exc

    def test_split_blocks_and_parse_resolution_refresh(self) -> None:
        """
        Summary
        Ensure display blocks are split deterministically and resolution/refresh parsing is best-effort.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_split_display_blocks`, `_parse_resolution`, and `_parse_refresh_hz`.

        Why this exists
        Bandwidth estimates depend on correct block segmentation and basic numeric parsing.
        """
        try:
            raw = """
    Color LCD:
      Resolution: 2560 x 1600
      Refresh Rate: 60 Hz

    DELL U2720Q:
      Resolution: 3840 x 2160
      Refresh Rate: 120 Hz
"""
            blocks = _split_display_blocks(raw)
            self.assertEqual(len(blocks), 2)
            w0, h0 = _parse_resolution(blocks[0])
            self.assertEqual((w0, h0), (2560, 1600))
            self.assertEqual(_parse_refresh_hz(blocks[0]), 60.0)
            self.assertEqual(_parse_refresh_hz("no refresh"), None)
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
                f"{MODULE_PATH}:DisplayTransportParsingTests.test_split_blocks_and_parse_resolution_refresh failed: {exc}"
            ) from exc

    def test_merge_transports_formats_estimates(self) -> None:
        """
        Summary
        Ensure transport estimate formatting is stable and does not crash on mismatched list lengths.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if formatting fails.

        Ties to other methods
        Exercises `_merge_transports`.

        Why this exists
        Export and UI paths rely on consistent formatting when estimates are partially available.
        """
        try:
            merged = _merge_transports(["Internal", "HDMI"], [12.345, None])
            self.assertEqual(merged[0], "Internal 12.35 Gbps")
            self.assertEqual(merged[1], "HDMI")
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
                f"{MODULE_PATH}:DisplayTransportParsingTests.test_merge_transports_formats_estimates failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
