from __future__ import annotations

import unittest

from mac_health_checkup.diagnostics.power import _parse_charging_state, _parse_thermal_state, _parse_usb_power

MODULE_PATH = "tests/test_power_parsing.py"


class PowerParsingTests(unittest.TestCase):
    """
    Summary
    Validate power diagnostics parsing helpers remain robust to noisy output.

    Inputs
    None.

    Outputs
    Assertions on parsed states and hub rows.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises helpers in `mac_health_checkup/diagnostics/power.py`.

    Why this exists
    These parsers are used in the UI and exports; malformed input should degrade safely without exceptions.
    """

    def test_parse_thermal_state_is_case_insensitive(self) -> None:
        """
        Summary
        Ensure thermal state parsing extracts a stable lowercase state.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_parse_thermal_state`.

        Why this exists
        The thermal state influences actionability; normalization prevents flapping due to capitalization.
        """
        try:
            self.assertEqual(_parse_thermal_state("Thermal Level: Nominal"), "nominal")
            self.assertEqual(_parse_thermal_state("no match"), "unknown")
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
                f"{MODULE_PATH}:PowerParsingTests.test_parse_thermal_state_is_case_insensitive failed: {exc}"
            ) from exc

    def test_parse_charging_state_is_best_effort(self) -> None:
        """
        Summary
        Ensure charging state parsing returns True/False when present, else None.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_parse_charging_state`.

        Why this exists
        Some system_profiler outputs omit charging state; the parser must avoid guessing.
        """
        try:
            self.assertEqual(_parse_charging_state("Charging: Yes"), True)
            self.assertEqual(_parse_charging_state("Charging: No"), False)
            self.assertIsNone(_parse_charging_state("no charging key"))
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
                f"{MODULE_PATH}:PowerParsingTests.test_parse_charging_state_is_best_effort failed: {exc}"
            ) from exc

    def test_parse_usb_power_extracts_hubs_and_devices(self) -> None:
        """
        Summary
        Ensure USB power parsing extracts hub blocks and nested device rows.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_parse_usb_power`.

        Why this exists
        USB power headroom issues can explain flaky peripherals; output should be readable and deterministic.
        """
        try:
            raw = """
        USB Hub:
            Current Available (mA): 900
            Current Required (mA): 500
            Keyboard:
"""
            hubs = _parse_usb_power(raw)
            self.assertEqual(len(hubs), 1)
            hub = hubs[0]
            self.assertEqual(hub.get("name"), "USB Hub")
            self.assertEqual(hub.get("available_ma"), 900)
            self.assertEqual(hub.get("required_ma"), 500)
            self.assertEqual(hub.get("headroom_ma"), 400)
            devices = hub.get("devices")
            self.assertIsInstance(devices, list)
            if isinstance(devices, list):
                self.assertEqual(devices[0].get("name"), "Keyboard")
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
                f"{MODULE_PATH}:PowerParsingTests.test_parse_usb_power_extracts_hubs_and_devices failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
