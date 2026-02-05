from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

import run_mac_health_checkup
import run_mac_health_checkup_ui

MODULE_PATH = "tests/test_one_click_runner_help.py"


class OneClickRunnerHelpTests(unittest.TestCase):
    """
    Summary
    Ensure the one-click runner scripts support `--help` without launching services or UIs.

    Inputs
    None.

    Outputs
    None.

    Side effects
    Patches `sys.argv` and runner dependencies for the duration of each test.

    Error handling
    Relies on unittest assertions.

    Ties to other methods
    Exercises `run_mac_health_checkup.main` and `run_mac_health_checkup_ui.main`.

    Why this exists
    `--help` should be safe to run in restricted environments and should not attempt socket binds or Swift builds.
    """

    def test_agent_runner_help_exits_cleanly(self) -> None:
        """
        Summary
        Verify `run_mac_health_checkup.py --help` exits with code 0 without calling the agent starter.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches argv and `run_one_click_agent` to ensure it is not invoked.

        Error handling
        Fails via assertions when `--help` does not short-circuit.

        Ties to other methods
        Calls `run_mac_health_checkup.main`.

        Why this exists
        Prevents accidental socket bind attempts when users just want usage text.
        """
        with (
            patch.object(sys, "argv", ["run_mac_health_checkup.py", "--help"]),
            patch.object(
                run_mac_health_checkup, "run_one_click_agent", side_effect=AssertionError("should not run")
            ),
        ):
            with self.assertRaises(SystemExit) as ctx:
                run_mac_health_checkup.main()
        self.assertEqual(ctx.exception.code, 0)

    def test_ui_runner_help_exits_cleanly(self) -> None:
        """
        Summary
        Verify `run_mac_health_checkup_ui.py --help` exits with code 0 without attempting a Swift build.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches argv and the Swift runner to ensure it is not invoked.

        Error handling
        Fails via assertions when `--help` does not short-circuit.

        Ties to other methods
        Calls `run_mac_health_checkup_ui.main`.

        Why this exists
        Prevents long-running builds from starting when requesting help.
        """
        with (
            patch.object(sys, "argv", ["run_mac_health_checkup_ui.py", "--help"]),
            patch.object(
                run_mac_health_checkup_ui,
                "_run_make_swift_run_with_retry",
                side_effect=AssertionError("should not run"),
            ),
        ):
            with self.assertRaises(SystemExit) as ctx:
                run_mac_health_checkup_ui.main()
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
