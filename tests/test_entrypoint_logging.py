from __future__ import annotations

import argparse
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import mac_health_checkup.app.entrypoint as entrypoint

MODULE_PATH = "tests/test_entrypoint_logging.py"


class _FakeShutdownManager:
    """
    Summary
    Provide a minimal shutdown manager test double.

    Inputs
    None.

    Outputs
    Instance used to satisfy the entrypoint lifecycle calls.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Injected into `mac_health_checkup.app.entrypoint.main` to avoid installing OS signal handlers.

    Why this exists
    Keeps the unit test deterministic and avoids mutating global process signal state.
    """

    def install_handlers(self) -> None:
        """
        Summary
        No-op handler installer.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Called by the entrypoint during startup.

        Why this exists
        Prevents tests from registering real signal handlers.
        """

    def trigger_shutdown(self) -> None:
        """
        Summary
        No-op shutdown trigger.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Called by the entrypoint before returning.

        Why this exists
        Matches the production interface without affecting test execution.
        """

    def wait_for_shutdown(self) -> None:
        """
        Summary
        No-op wait method.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used in server mode (not exercised by this test).

        Why this exists
        Completes the shutdown manager surface area for entrypoint compatibility.
        """


class EntrypointLoggingTests(unittest.TestCase):
    """
    Summary
    Validate that CLI mode writes structured logs to stderr, not stdout.

    Inputs
    None.

    Outputs
    None.

    Side effects
    Patches entrypoint module globals for the duration of the test.

    Error handling
    Relies on unittest assertions.

    Ties to other methods
    Tests `mac_health_checkup.app.entrypoint.main`.

    Why this exists
    Prevents CLI output from being polluted by structured logs, keeping stdout safe for humans and piping.
    """

    def test_cli_logging_stream_is_stderr(self) -> None:
        """
        Summary
        Ensure `configure_logging_once` is called with stderr for CLI mode.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches entrypoint configuration, argument parsing, and section handlers.

        Error handling
        Fails the test via assertions when the wrong stream is used.

        Ties to other methods
        Verifies the log stream selection inside `main`.

        Why this exists
        Keeps the CLI stdout channel clean for the rendered section summary.
        """

        args = argparse.Namespace(
            cli=True,
            snapshot_json=False,
            snapshot_json_out=None,
            snapshot_pretty=False,
            serve=False,
            fail_on=None,
            advice=False,
            export=None,
            export_path=None,
            export_from_snapshot=None,
            export_include_diagnostics=False,
            diff_snapshots=None,
            diff_against=None,
        )
        captured: dict[str, object] = {}

        class _FakeLoggingConfig:
            """
            Summary
            Minimal logging config stub for the entrypoint.

            Inputs
            None.

            Outputs
            Instance with required logging fields.

            Side effects
            None.

            Error handling
            None.

            Ties to other methods
            Returned by `_FakeConfig.logging` and consumed by `entrypoint.main`.

            Why this exists
            Avoids importing full config machinery in a focused unit test.
            """

            event_field = "event"
            correlation_id_field = "corr_id"
            component_field = "component"

            def redaction(self) -> dict[str, str]:
                """
                Summary
                Provide an empty redaction mapping.

                Inputs
                None.

                Outputs
                Empty redaction dict.

                Side effects
                None.

                Error handling
                None.

                Ties to other methods
                Used by `configure_logging_once` and `StructuredLogger` initialization.

                Why this exists
                Allows entrypoint wiring to proceed without loading config files.
                """

                return {}

        fake_cfg = SimpleNamespace(
            logging=_FakeLoggingConfig(),
            api=SimpleNamespace(enabled=False, allow_lan=False, tls_enabled=False),
            gui=SimpleNamespace(section_rows=[]),
        )

        def _fake_configure_logging_once(*_args: object, **kwargs: object) -> None:
            """
            Summary
            Capture the selected log stream without configuring global logging.

            Inputs
            _args: Ignored positional args.
            kwargs: Keyword args; expects `stream`.

            Outputs
            None.

            Side effects
            Stores the provided stream in the `captured` dict.

            Error handling
            Raises `AssertionError` if the entrypoint does not provide a stream kwarg.

            Ties to other methods
            Replaces `entrypoint.configure_logging_once`.

            Why this exists
            Keeps the test isolated from global logging configuration.
            """

            if "stream" not in kwargs:
                raise AssertionError("entrypoint.configure_logging_once did not receive stream kwarg")
            captured["stream"] = kwargs["stream"]

        with (
            patch.object(entrypoint, "_parse_args", return_value=args),
            patch.object(entrypoint, "get_config", return_value=fake_cfg),
            patch.object(entrypoint, "configure_logging_once", side_effect=_fake_configure_logging_once),
            patch.object(entrypoint, "ShutdownManager", _FakeShutdownManager),
            patch.object(entrypoint, "SECTION_HANDLERS", {}),
        ):
            code = entrypoint.main()

        self.assertEqual(code, 0)
        self.assertIs(captured.get("stream"), sys.stderr)


if __name__ == "__main__":
    unittest.main()
