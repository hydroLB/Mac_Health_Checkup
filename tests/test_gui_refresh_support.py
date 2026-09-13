from __future__ import annotations

import unittest
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

from mac_health_checkup.app.gui.dashboard.queueing import SectionQueue
from mac_health_checkup.app.gui.dashboard.refresh_support import (
    SetFieldOperation,
    _SectionRunner,
    build_refresh_messages,
    build_refresh_status_update,
    queue_refresh_sections,
    resolve_refresh_runtime,
    run_buffered_refresh,
    run_refresh_sections,
    start_refresh_cycle,
)
from mac_health_checkup.app.gui.sections.types import SectionHost

MODULE_PATH = "tests/test_gui_refresh_support.py"


class GuiRefreshSupportTests(unittest.TestCase):
    """
    Summary
    Verify refresh-support helpers keep dashboard refresh orchestration stable.

    Inputs
    None.

    Outputs
    None.

    Side effects
    Exercises queueing and refresh helper behavior with lightweight stubs.

    Error handling
    Raises `AssertionError` with contextual file and method details on failures.

    Ties to other methods
    Covers helper functions used by `refresh_mixin.py`.

    Why this exists
    The new support module should be directly testable so mixin refactors do not rely only on broad GUI tests.
    """

    def test_resolve_refresh_runtime_prefers_app_overrides(self) -> None:
        """
        Summary
        Ensure refresh runtime resolution honors app-module overrides used by tests.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises `AssertionError` with context on failures.

        Ties to other methods
        Exercises `resolve_refresh_runtime`.

        Why this exists
        `DashboardApp` tests patch app-level globals, and the helper must preserve that behavior.
        """
        try:
            host = object()
            app_module = SimpleNamespace(
                SECTION_HANDLERS={"network": object()},
                run_section=lambda host, key: {"host": host, "key": key},
            )

            runtime = resolve_refresh_runtime(app_module)

            self.assertEqual(list(runtime.section_handlers), ["network"])
            self.assertEqual(
                runtime.section_runner(cast(SectionHost, host), "network"), {"host": host, "key": "network"}
            )
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
                f"{MODULE_PATH}:GuiRefreshSupportTests.test_resolve_refresh_runtime_prefers_app_overrides failed: {exc}"
            ) from exc

    def test_queue_and_run_refresh_sections_tracks_loading_success_and_failure(self) -> None:
        """
        Summary
        Ensure queued refresh helpers preserve section order and count failures without aborting the loop.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Enqueues section keys and runs stubbed refresh callbacks.

        Error handling
        Raises `AssertionError` with context on failures.

        Ties to other methods
        Exercises `queue_refresh_sections` and `run_refresh_sections`.

        Why this exists
        The mixin now delegates the section loop to the support module, so loop bookkeeping needs direct tests.
        """
        try:
            queue = SectionQueue()
            feedback_calls: list[tuple[str, str, str]] = []
            success_calls: list[str] = []
            failure_calls: list[tuple[str, str]] = []

            def _set_section_feedback(key: str, message: str, *, level: str) -> None:
                """
                Summary
                Record section feedback calls emitted during refresh setup.

                Inputs
                key: Section key.
                message: Feedback text.
                level: Feedback severity.

                Outputs
                None.

                Side effects
                Appends to `feedback_calls`.

                Error handling
                None.

                Ties to other methods
                Used by `queue_refresh_sections`.

                Why this exists
                The test needs a strict callback stub that preserves the keyword-only `level` contract.
                """
                feedback_calls.append((key, message, level))

            def _run_section(host: SectionHost, key: str) -> object:
                """
                Summary
                Simulate one refresh section run with a deterministic injected failure.

                Inputs
                host: Section host under test.
                key: Section key to run.

                Outputs
                Simple dict payload for successful section runs.

                Side effects
                Raises `RuntimeError` for the `network` section to exercise failure handling.

                Error handling
                Raises `RuntimeError` for the injected failure case.

                Ties to other methods
                Used by `run_refresh_sections`.

                Why this exists
                The support loop should keep running after one recoverable section failure.
                """
                _ = host
                if key == "network":
                    raise RuntimeError("boom")
                return {"key": key}

            section_runner: _SectionRunner = _run_section

            with patch(
                "mac_health_checkup.app.gui.dashboard.queueing.get_config",
                return_value=SimpleNamespace(rate_limits=SimpleNamespace(ui_queue_max_items=10)),
            ):
                queue_refresh_sections(
                    queue,
                    {"network": object(), "cpu": object()},
                    _set_section_feedback,
                    loading_feedback="Refreshing section...",
                )
                failures = run_refresh_sections(
                    queue,
                    cast(SectionHost, object()),
                    section_runner=section_runner,
                    on_section_success=lambda key: success_calls.append(key),
                    on_section_failure=lambda key, exc: failure_calls.append((key, type(exc).__name__)),
                )

            self.assertEqual(
                feedback_calls,
                [
                    ("network", "Refreshing section...", "loading"),
                    ("cpu", "Refreshing section...", "loading"),
                ],
            )
            self.assertEqual(success_calls, ["cpu"])
            self.assertEqual(failure_calls, [("network", "RuntimeError")])
            self.assertEqual(failures, 1)
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
                f"{MODULE_PATH}:GuiRefreshSupportTests.test_queue_and_run_refresh_sections_tracks_loading_success_and_failure failed: {exc}"
            ) from exc

    def test_buffered_refresh_runs_every_section_without_queue_capacity_loss(self) -> None:
        """
        Summary
        Ensure one-cycle buffered refresh executes every ordered section without the bounded UI queue.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Runs injected in-memory section handlers.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `run_buffered_refresh`.

        Why this exists
        Queue saturation must not leave enabled sections stuck in a loading state.
        """
        try:
            executed: list[str] = []

            def _run(host: SectionHost, key: str) -> object:
                """
                Summary
                Record one buffered section execution.

                Inputs
                host: Recording host. key: Section key.

                Outputs
                Empty diagnostics mapping.

                Side effects
                Appends execution and render records.

                Error handling
                None.

                Ties to other methods
                Injected into `run_buffered_refresh`.

                Why this exists
                Makes ordered, lossless execution directly observable.
                """
                executed.append(key)
                host.set_field(key, f"value-{key}")
                return {}

            result = run_buffered_refresh(
                ("one", "two", "three"),
                section_runner=_run,
                machine_hint="mac",
                should_cancel=lambda: False,
            )

            self.assertEqual(executed, ["one", "two", "three"])
            self.assertEqual([section.key for section in result.sections], executed)
            self.assertEqual(result.total_sections, 3)
            self.assertEqual(result.failures, 0)
            self.assertTrue(
                all(
                    len(section.operations) == 1 and isinstance(section.operations[0], SetFieldOperation)
                    for section in result.sections
                )
            )
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
                f"{MODULE_PATH}:GuiRefreshSupportTests.test_buffered_refresh_runs_every_section_without_queue_capacity_loss failed: {exc}"
            ) from exc

    def test_build_refresh_helpers_return_expected_defaults_and_status_levels(self) -> None:
        """
        Summary
        Ensure message fallback and final status formatting remain stable for success and warning outcomes.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Reads the clock to build refresh-cycle metadata.

        Error handling
        Raises `AssertionError` with context on failures.

        Ties to other methods
        Exercises `build_refresh_messages`, `start_refresh_cycle`, and `build_refresh_status_update`.

        Why this exists
        The mixin now relies on helper-returned status bundles to update the dashboard header.
        """
        try:
            messages = build_refresh_messages(None)
            cycle = start_refresh_cycle(total_sections=3)
            warn_status = build_refresh_status_update(cycle, failures=1)
            info_status = build_refresh_status_update(cycle, failures=0)

            self.assertEqual(messages.loading_feedback, "Refreshing section...")
            self.assertEqual(messages.error_feedback, "Section refresh failed. Auto retry is enabled.")
            self.assertEqual(warn_status.level, "warn")
            self.assertIn("2/3 sections OK", warn_status.text)
            self.assertEqual(info_status.level, "info")
            self.assertIn("3/3 sections OK", info_status.text)
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
                f"{MODULE_PATH}:GuiRefreshSupportTests.test_build_refresh_helpers_return_expected_defaults_and_status_levels failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
