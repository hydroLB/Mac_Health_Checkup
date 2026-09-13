from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
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

    def test_ui_runner_honors_environment_config_override(self) -> None:
        """
        Summary
        Verify the UI runner forwards config and repo overrides from the environment into `SWIFT_APP_ARGS`.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates temporary repo/config paths and patches the Swift runner.

        Error handling
        Fails via assertions when override paths are ignored.

        Ties to other methods
        Exercises `run_mac_health_checkup_ui.main` and `_build_swift_app_args`.

        Why this exists
        Native app automation needs disposable config and state paths without editing the checked-in config file.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            config_path = repo_root / "config" / "qa.json"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("{}", encoding="utf-8")

            captured_env: dict[str, str] = {}

            def _fake_run_make(*, repo_root: Path, env: dict[str, str]) -> int:
                """
                Summary
                Capture the Swift launcher environment instead of invoking `make`.

                Inputs
                repo_root: Repository root supplied by the launcher.
                env: Environment passed to the Swift run command.

                Outputs
                Exit code `0`.

                Side effects
                Updates `captured_env` and asserts the launcher repo root.

                Error handling
                Fails the test through unittest assertions.

                Ties to other methods
                Replaces `run_mac_health_checkup_ui._run_make_swift_run_with_retry`.

                Why this exists
                The test needs to inspect forwarded arguments without starting a Swift build.
                """
                captured_env.update(env)
                self.assertEqual(repo_root, Path(run_mac_health_checkup_ui.__file__).resolve().parent)
                return 0

            with (
                patch.dict(
                    os.environ,
                    {
                        "MAC_HEALTH_CHECKUP_REPO_ROOT": str(repo_root),
                        "MAC_HEALTH_CHECKUP_CONFIG": str(config_path),
                    },
                    clear=False,
                ),
                patch.object(run_mac_health_checkup_ui, "which", return_value="/usr/bin/true"),
                patch.object(
                    run_mac_health_checkup_ui, "_run_make_swift_run_with_retry", side_effect=_fake_run_make
                ),
            ):
                exit_code = run_mac_health_checkup_ui.main()

            self.assertEqual(exit_code, 0)
            self.assertIn("--repo-root", captured_env["SWIFT_APP_ARGS"])
            self.assertIn(str(repo_root), captured_env["SWIFT_APP_ARGS"])
            self.assertIn("--config", captured_env["SWIFT_APP_ARGS"])
            self.assertIn(str(config_path), captured_env["SWIFT_APP_ARGS"])

    def test_ui_runner_cli_overrides_include_python(self) -> None:
        """
        Summary
        Verify CLI overrides are forwarded into the native app launch arguments.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates temporary repo/config paths and patches argv plus the Swift runner.

        Error handling
        Fails via assertions when CLI overrides are not propagated.

        Ties to other methods
        Exercises `run_mac_health_checkup_ui.main` and `_build_swift_app_args`.

        Why this exists
        QA and recovery workflows need deterministic control over repo, config, and Python paths from the launcher.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir) / "repo"
            config_path = repo_root / "config" / "qa.json"
            python_path = Path(temp_dir) / "python3-custom"
            config_path.parent.mkdir(parents=True)
            config_path.write_text("{}", encoding="utf-8")
            python_path.write_text("", encoding="utf-8")

            captured_env: dict[str, str] = {}

            def _fake_run_make(*, repo_root: Path, env: dict[str, str]) -> int:
                """
                Summary
                Capture the Swift launcher environment instead of invoking `make`.

                Inputs
                repo_root: Repository root supplied by the launcher.
                env: Environment passed to the Swift run command.

                Outputs
                Exit code `0`.

                Side effects
                Updates `captured_env` and asserts the launcher repo root.

                Error handling
                Fails the test through unittest assertions.

                Ties to other methods
                Replaces `run_mac_health_checkup_ui._run_make_swift_run_with_retry`.

                Why this exists
                The test needs to inspect forwarded arguments without starting a Swift build.
                """
                captured_env.update(env)
                self.assertEqual(repo_root, Path(run_mac_health_checkup_ui.__file__).resolve().parent)
                return 0

            with (
                patch.object(
                    sys,
                    "argv",
                    [
                        "run_mac_health_checkup_ui.py",
                        "--repo-root",
                        str(repo_root),
                        "--config",
                        str(config_path),
                        "--python",
                        str(python_path),
                    ],
                ),
                patch.object(run_mac_health_checkup_ui, "which", return_value="/usr/bin/true"),
                patch.object(
                    run_mac_health_checkup_ui, "_run_make_swift_run_with_retry", side_effect=_fake_run_make
                ),
            ):
                exit_code = run_mac_health_checkup_ui.main()

            self.assertEqual(exit_code, 0)
            self.assertIn(str(repo_root), captured_env["SWIFT_APP_ARGS"])
            self.assertIn(str(config_path), captured_env["SWIFT_APP_ARGS"])
            self.assertIn(str(python_path), captured_env["SWIFT_APP_ARGS"])


if __name__ == "__main__":
    unittest.main()
