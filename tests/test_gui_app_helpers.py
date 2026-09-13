from __future__ import annotations

import concurrent.futures
import threading
import tkinter as tk
import unittest
from types import SimpleNamespace
from typing import TYPE_CHECKING, TypeAlias, cast
from unittest.mock import patch

from mac_health_checkup.app.gui.app import (
    DashboardApp,
    _refresh_status_message,
    _SectionWidgets,
    _segment_at_char,
    _table_separator_length,
    _UiTokens,
)
from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.app.gui.dashboard.queueing import SectionQueue
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.app.gui.widgets.scroll_container import ScrollContainer
from mac_health_checkup.core.config import Config

MODULE_PATH = "tests/test_gui_app_helpers.py"

if TYPE_CHECKING:
    _EventMisc: TypeAlias = tk.Event[tk.Misc]
else:
    _EventMisc = object


class _StubText:
    def __init__(self, *, index_value: str, lines: dict[str, str]) -> None:
        """
        Summary
        Execute `__init__` for its module-level responsibility.

        Inputs
        index_value: keyword-only `str` parameter.
        lines: keyword-only `dict[str, str]` parameter.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:__init__` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `__init__` explicit, testable, and maintainable.
        """
        self._index_value = index_value
        self._lines = dict(lines)

    def index(self, _spec: str) -> str:
        """
        Summary
        Execute `index` for its module-level responsibility.

        Inputs
        _spec: `str` parameter from the function signature.

        Outputs
        Returns `str`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:index` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `index` explicit, testable, and maintainable.
        """
        return self._index_value

    def get(self, start: str, _end: str) -> str:
        """
        Summary
        Execute `get` for its module-level responsibility.

        Inputs
        start: `str` parameter from the function signature.
        _end: `str` parameter from the function signature.

        Outputs
        Returns `str`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:get` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `get` explicit, testable, and maintainable.
        """
        return self._lines.get(start, "")


class _StubTextBuffer:
    def __init__(self, *, initial_text: str = "") -> None:
        """
        Summary
        Execute `__init__` for its module-level responsibility.

        Inputs
        initial_text: keyword-only `str` parameter with a default.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:__init__` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `__init__` explicit, testable, and maintainable.
        """
        self._content: list[str] = [initial_text] if initial_text else []
        self.state: str = "normal"

    def configure(self, **kwargs: object) -> None:
        """
        Summary
        Execute `configure` for its module-level responsibility.

        Inputs
        **kwargs: variadic keyword `object` parameters.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:configure` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `configure` explicit, testable, and maintainable.
        """
        if "state" in kwargs:
            self.state = str(kwargs["state"])

    def delete(self, _start: str, _end: str) -> None:
        """
        Summary
        Execute `delete` for its module-level responsibility.

        Inputs
        _start: `str` parameter from the function signature.
        _end: `str` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:delete` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `delete` explicit, testable, and maintainable.
        """
        self._content.clear()

    def insert(self, _index: str, text: str, _tags: object = ()) -> None:
        """
        Summary
        Execute `insert` for its module-level responsibility.

        Inputs
        _index: `str` parameter from the function signature.
        text: `str` parameter from the function signature.
        _tags: `object` parameter from the function signature with a default.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:insert` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `insert` explicit, testable, and maintainable.
        """
        self._content.append(str(text))

    def text(self) -> str:
        """
        Summary
        Execute `text` for its module-level responsibility.

        Inputs
        None.

        Outputs
        Returns `str`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:text` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `text` explicit, testable, and maintainable.
        """
        return "".join(self._content)


class _StubSectionQueue:
    def __init__(self) -> None:
        """
        Summary
        Execute `__init__` for its module-level responsibility.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:__init__` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `__init__` explicit, testable, and maintainable.
        """
        self._keys: list[str] = []

    def enqueue(self, key: str) -> bool:
        """
        Summary
        Execute `enqueue` for its module-level responsibility.

        Inputs
        key: `str` parameter from the function signature.

        Outputs
        Returns `bool`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:enqueue` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `enqueue` explicit, testable, and maintainable.
        """
        self._keys.append(str(key))
        return True

    def drain(self) -> list[str]:
        """
        Summary
        Execute `drain` for its module-level responsibility.

        Inputs
        None.

        Outputs
        Returns `list[str]`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:drain` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `drain` explicit, testable, and maintainable.
        """
        out = list(self._keys)
        self._keys.clear()
        return out


class _StubShutdown:
    def __init__(self, *, requested: bool) -> None:
        """
        Summary
        Execute `__init__` for its module-level responsibility.

        Inputs
        requested: keyword-only `bool` parameter.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:__init__` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `__init__` explicit, testable, and maintainable.
        """
        self._requested = bool(requested)

    def shutdown_requested(self) -> bool:
        """
        Summary
        Execute `shutdown_requested` for its module-level responsibility.

        Inputs
        None.

        Outputs
        Returns `bool`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:shutdown_requested` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `shutdown_requested` explicit, testable, and maintainable.
        """
        return self._requested


class _StubScroll:
    def __init__(self) -> None:
        """
        Summary
        Execute `__init__` for its module-level responsibility.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:__init__` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `__init__` explicit, testable, and maintainable.
        """
        self.to_top_calls = 0
        self.to_bottom_calls = 0
        self.page_calls: list[int] = []

    def scroll_to_top(self) -> None:
        """
        Summary
        Execute `scroll_to_top` for its module-level responsibility.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:scroll_to_top` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `scroll_to_top` explicit, testable, and maintainable.
        """
        self.to_top_calls += 1

    def scroll_to_bottom(self) -> None:
        """
        Summary
        Execute `scroll_to_bottom` for its module-level responsibility.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:scroll_to_bottom` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `scroll_to_bottom` explicit, testable, and maintainable.
        """
        self.to_bottom_calls += 1

    def scroll_pages(self, pages: int) -> None:
        """
        Summary
        Execute `scroll_pages` for its module-level responsibility.

        Inputs
        pages: `int` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_gui_app_helpers.py:scroll_pages` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_gui_app_helpers.py`.

        Why this exists
        Keeps `scroll_pages` explicit, testable, and maintainable.
        """
        self.page_calls.append(int(pages))


class GuiAppHelpersTests(unittest.TestCase):
    """
    Summary
    Validate pure helper logic in the Tk dashboard module without creating a real Tk root.

    Inputs
    None.

    Outputs
    Assertions on parsing and tooltip helper results.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises helpers in `mac_health_checkup/app/gui/app.py`.

    Why this exists
    A large portion of GUI behavior is deterministic string parsing and mapping; testing it should not require a display server.
    """

    def test_segment_at_char_maps_columns(self) -> None:
        """
        Summary
        Ensure pipe-delimited segment mapping returns the correct column segment for a char index.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_segment_at_char`.

        Why this exists
        Tooltips depend on deterministic column identification from Text widget cursor offsets.
        """
        try:
            line = "Name | Value | Status"
            self.assertEqual(_segment_at_char(line, 0), "Name")
            self.assertEqual(_segment_at_char(line, 7), "Value")
            self.assertEqual(_segment_at_char(line, 16), "Status")
            self.assertEqual(_segment_at_char(line, 999), "")
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_segment_at_char_maps_columns failed: {exc}"
            ) from exc

    def test_machine_hint_and_status_tag_mapping(self) -> None:
        """
        Summary
        Ensure machine hint and status tag mappings normalize inputs.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `set_machine_hint`, `machine_hint`, and `_status_to_tag`.

        Why this exists
        Multiple sections use machine hints and status tags to pick defaults and colors.
        """
        try:
            app = object.__new__(DashboardApp)
            app._machine_hint = "mac"
            app.set_machine_hint("MacBook Pro")
            self.assertEqual(app.machine_hint(), "pro")
            app.set_machine_hint("MacBook Air")
            self.assertEqual(app.machine_hint(), "air")

            self.assertEqual(app._status_to_tag("ok"), "ok")
            self.assertEqual(app._status_to_tag("Warning"), "warn")
            self.assertEqual(app._status_to_tag("FAIL"), "bad")
            self.assertEqual(app._status_to_tag("n/a"), "unknown")
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_machine_hint_and_status_tag_mapping failed: {exc}"
            ) from exc

    def test_tooltip_helpers_return_help_text(self) -> None:
        """
        Summary
        Ensure metrics and table tooltip helpers return a non-empty string for common cursor positions.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_metrics_tooltip_for_event` and `_table_tooltip_for_event`.

        Why this exists
        Tooltips are a key UX feature and should degrade to section help instead of raising.
        """
        try:
            app = object.__new__(DashboardApp)

            metrics_widget = _StubText(index_value="1.0", lines={"1.0": "RSSI: -50 dBm (warn)"})
            event = SimpleNamespace(x=0, y=0)
            text = app._metrics_tooltip_for_event(
                key="network",
                widget=cast(tk.Text, metrics_widget),
                event=cast(_EventMisc, event),
            )
            self.assertIsInstance(text, str)
            self.assertTrue(bool(text and str(text).strip()))

            table_widget = _StubText(
                index_value="3.7",
                lines={
                    "1.0": "Name | Value\n",
                    "3.0": "Foo | Bar\n",
                },
            )
            text2 = app._table_tooltip_for_event(
                key="devices",
                widget=cast(tk.Text, table_widget),
                event=cast(_EventMisc, event),
            )
            self.assertIsInstance(text2, str)
            self.assertTrue(bool(text2 and str(text2).strip()))
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_tooltip_helpers_return_help_text failed: {exc}"
            ) from exc

    def test_section_container_and_get_widget_are_safe(self) -> None:
        """
        Summary
        Ensure section_container and get_widget return None when a section key is missing and return widgets when present.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `section_container` and `get_widget`.

        Why this exists
        Section renderers and tests call these helpers; missing keys should not raise.
        """
        try:
            app = object.__new__(DashboardApp)
            app._sections = {}
            self.assertIsNone(app.section_container("missing"))
            self.assertIsNone(app.get_widget("missing"))

            frame = object()
            field = object()
            app._sections = {
                "general": _SectionWidgets(
                    frame=cast(tk.Frame, frame),
                    title=cast(tk.Label, object()),
                    subtitle=cast(tk.Label, object()),
                    field=cast(tk.Label, field),
                    table=None,
                    metrics=None,
                )
            }
            self.assertIs(app.section_container("general"), frame)
            self.assertIs(app.get_widget("general"), field)
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_section_container_and_get_widget_are_safe failed: {exc}"
            ) from exc

    def test_table_separator_length_is_bounded_and_content_aware(self) -> None:
        """
        Summary
        Ensure table separator sizing tracks content width while respecting min and max bounds.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_table_separator_length`.

        Why this exists
        The table separator should adapt to content width instead of using a fixed hard-coded length.
        """
        try:
            short = _table_separator_length(("A",), [("x",)], minimum=20, maximum=120)
            self.assertEqual(short, 20)
            long = _table_separator_length(
                ("Name", "Value"),
                [("CPU Package Temperature", "102C"), ("Average", "88C")],
                minimum=20,
                maximum=120,
            )
            self.assertGreaterEqual(long, 20)
            self.assertLessEqual(long, 120)
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_table_separator_length_is_bounded_and_content_aware failed: {exc}"
            ) from exc

    def test_refresh_status_message_formats_success_and_failure(self) -> None:
        """
        Summary
        Ensure refresh status messaging includes section counts and elapsed time.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_refresh_status_message`.

        Why this exists
        Header status text is primary user feedback during periodic refreshes.
        """
        try:
            success = _refresh_status_message(
                refreshed_at="12:00:01", total_sections=5, failures=0, elapsed_ms=212
            )
            self.assertIn("5/5 sections OK", success)
            self.assertIn("212 ms", success)

            failure = _refresh_status_message(
                refreshed_at="12:00:02", total_sections=5, failures=2, elapsed_ms=320
            )
            self.assertIn("3/5 sections OK", failure)
            self.assertIn("2 errors", failure)
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_refresh_status_message_formats_success_and_failure failed: {exc}"
            ) from exc

    def test_schedule_next_refresh_replaces_existing_timer(self) -> None:
        """
        Summary
        Ensure scheduling a refresh twice cancels the previous timer to avoid duplicate pending callbacks.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Mutates timer tracking state on the app instance.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_schedule_next_refresh` and `_cancel_scheduled_refresh`.

        Why this exists
        Manual refresh requests should not create overlapping scheduled timers.
        """
        try:
            app = object.__new__(DashboardApp)
            after_calls: list[tuple[int, object]] = []
            cancel_calls: list[str] = []

            def _after(delay_ms: int, callback: object) -> str:
                """
                Summary
                Execute `_after` for its module-level responsibility.

                Inputs
                delay_ms: `int` parameter from the function signature.
                callback: `object` parameter from the function signature.

                Outputs
                Returns `str`.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_gui_app_helpers.py:_after` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_gui_app_helpers.py`.

                Why this exists
                Keeps `_after` explicit, testable, and maintainable.
                """
                after_calls.append((int(delay_ms), callback))
                return f"timer-{len(after_calls)}"

            def _after_cancel(after_id: str) -> None:
                """
                Summary
                Execute `_after_cancel` for its module-level responsibility.

                Inputs
                after_id: `str` parameter from the function signature.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_gui_app_helpers.py:_after_cancel` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_gui_app_helpers.py`.

                Why this exists
                Keeps `_after_cancel` explicit, testable, and maintainable.
                """
                cancel_calls.append(str(after_id))

            app._refresh_after_id = "stale-timer"
            setattr(app, "after", _after)
            setattr(app, "after_cancel", _after_cancel)

            app._schedule_next_refresh(250)
            app._schedule_next_refresh(400)

            self.assertEqual(cancel_calls, ["stale-timer", "timer-1"])
            self.assertEqual([delay for delay, _callback in after_calls], [250, 400])
            self.assertEqual(app._refresh_after_id, "timer-2")
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_schedule_next_refresh_replaces_existing_timer failed: {exc}"
            ) from exc

    def test_on_refresh_shortcut_cancels_pending_and_schedules_immediate_refresh(self) -> None:
        """
        Summary
        Ensure keyboard refresh shortcuts cancel pending timer state and queue an immediate refresh callback.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Mutates timer tracking state and app callback queues.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_on_refresh_shortcut`.

        Why this exists
        Keyboard refresh should be responsive and should not leave duplicate timers active.
        """
        try:
            app = object.__new__(DashboardApp)
            after_calls: list[tuple[int, object]] = []
            cancel_calls: list[str] = []

            def _refresh() -> None:
                """
                Summary
                Execute `_refresh` for its module-level responsibility.

                Inputs
                None.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_gui_app_helpers.py:_refresh` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_gui_app_helpers.py`.

                Why this exists
                Keeps `_refresh` explicit, testable, and maintainable.
                """
                return

            def _after(delay_ms: int, callback: object) -> str:
                """
                Summary
                Execute `_after` for its module-level responsibility.

                Inputs
                delay_ms: `int` parameter from the function signature.
                callback: `object` parameter from the function signature.

                Outputs
                Returns `str`.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_gui_app_helpers.py:_after` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_gui_app_helpers.py`.

                Why this exists
                Keeps `_after` explicit, testable, and maintainable.
                """
                after_calls.append((int(delay_ms), callback))
                return "immediate-refresh"

            def _after_cancel(after_id: str) -> None:
                """
                Summary
                Execute `_after_cancel` for its module-level responsibility.

                Inputs
                after_id: `str` parameter from the function signature.

                Outputs
                None.

                Side effects
                None beyond this method boundary.

                Error handling
                Raises contextual errors from `tests/test_gui_app_helpers.py:_after_cancel` when this method encounters invalid state or runtime failures.

                Ties to other methods
                Used by workflows in `tests/test_gui_app_helpers.py`.

                Why this exists
                Keeps `_after_cancel` explicit, testable, and maintainable.
                """
                cancel_calls.append(str(after_id))

            app._refresh_after_id = "pending-refresh"
            setattr(app, "_refresh", _refresh)
            setattr(app, "after", _after)
            setattr(app, "after_cancel", _after_cancel)

            result = app._on_refresh_shortcut(cast(_EventMisc, SimpleNamespace()))
            self.assertEqual(result, "break")
            self.assertEqual(cancel_calls, ["pending-refresh"])
            self.assertEqual(after_calls[0][0], 0)
            self.assertEqual(app._refresh_after_id, None)
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_on_refresh_shortcut_cancels_pending_and_schedules_immediate_refresh failed: {exc}"
            ) from exc

    def test_refresh_clears_stale_section_views_on_section_failure(self) -> None:
        """
        Summary
        Ensure refresh failure paths clear stale tables and metrics for failed sections before showing error text.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Triggers refresh error handling logic with stubbed section runner behavior.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_refresh` section-failure path.

        Why this exists
        Stale section detail data is misleading when a section refresh fails.
        """
        try:
            app = object.__new__(DashboardApp)
            app._queue = cast(SectionQueue, _StubSectionQueue())
            app._shutdown = cast(ShutdownManager, _StubShutdown(requested=False))
            app._refresh_after_id = None
            app._refresh_poll_after_id = None
            app._refresh_future = None
            app._refresh_cycle = None
            app._machine_hint = "mac"
            app._cfg = cast(
                Config,
                SimpleNamespace(
                    colors=SimpleNamespace(bad="#ff0000"),
                    gui=SimpleNamespace(auto_refresh_ms=10000),
                ),
            )

            status_calls: list[tuple[str, str]] = []
            clear_calls: list[tuple[str, str]] = []
            field_calls: list[tuple[str, str, str | None, str | None]] = []
            schedule_calls: list[int] = []
            feedback_calls: list[tuple[str, str, str]] = []

            setattr(
                app,
                "_set_status",
                lambda text, level="info": status_calls.append((str(text), str(level))),
            )
            setattr(
                app,
                "_clear_section_data_views",
                lambda key, message="": clear_calls.append((str(key), str(message))),
            )
            setattr(app, "update_idletasks", lambda: None)
            setattr(app, "after", lambda _delay, _callback: "refresh-poll")
            setattr(app, "_set_refresh_controls_busy", lambda _busy: None)
            setattr(
                app,
                "_set_section_feedback",
                lambda key, message, level: feedback_calls.append((str(key), str(message), str(level))),
            )
            setattr(app, "_schedule_next_refresh", lambda delay_ms: schedule_calls.append(int(delay_ms)))
            setattr(
                app,
                "set_field",
                lambda key, text, fg=None, tooltip=None: field_calls.append(
                    (str(key), str(text), cast(str | None, fg), cast(str | None, tooltip))
                ),
            )

            with patch("mac_health_checkup.app.gui.app.SECTION_HANDLERS", {"network": object()}):
                with patch("mac_health_checkup.app.gui.app.run_section", side_effect=RuntimeError("boom")):
                    app._refresh()
                    future = cast(
                        concurrent.futures.Future[object],
                        app.__dict__.get("_refresh_future"),
                    )
                    future.result(timeout=2.0)
                    app._poll_refresh_result()

            self.assertTrue(status_calls)
            self.assertEqual(status_calls[0][1], "loading")
            self.assertTrue(any(level == "warn" for _text, level in status_calls))
            self.assertEqual(len(clear_calls), 1)
            self.assertEqual(clear_calls[0][0], "network")
            self.assertIn("will retry on the next refresh", clear_calls[0][1])
            self.assertEqual(len(field_calls), 1)
            self.assertEqual(field_calls[0][0], "network")
            self.assertIn("Unable to refresh (RuntimeError)", field_calls[0][1])
            self.assertEqual(schedule_calls, [10000])
            app._refresh_executor.shutdown(wait=True)
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_refresh_clears_stale_section_views_on_section_failure failed: {exc}"
            ) from exc

    def test_refresh_collects_off_thread_and_replays_on_tk_thread(self) -> None:
        """
        Summary
        Ensure refresh returns while collection blocks and replays host calls only on the Tk thread.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Starts one bounded background refresh worker.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_refresh`, buffered collection, and `_poll_refresh_result`.

        Why this exists
        Tk must remain responsive and worker threads must never mutate UI state.
        """
        try:
            app = object.__new__(DashboardApp)
            app._shutdown = cast(ShutdownManager, _StubShutdown(requested=False))
            app._cfg = cast(Config, SimpleNamespace(gui=SimpleNamespace(auto_refresh_ms=10000)))
            app._refresh_after_id = None
            app._refresh_poll_after_id = None
            app._refresh_future = None
            app._refresh_cycle = None
            app._machine_hint = "mac"

            entered = threading.Event()
            release = threading.Event()
            main_thread = threading.get_ident()
            ui_threads: list[int] = []
            status_levels: list[str] = []
            busy_states: list[bool] = []

            setattr(app, "after", lambda _delay, _callback: "refresh-poll")
            setattr(app, "_set_next_refresh_hint", lambda delay_ms: None)
            setattr(app, "_schedule_next_refresh", lambda _delay_ms: None)
            setattr(app, "_set_refresh_controls_busy", lambda busy: busy_states.append(bool(busy)))
            setattr(app, "_set_status", lambda _text, level="info": status_levels.append(str(level)))
            setattr(app, "_set_section_feedback", lambda _key, _message, level: None)
            setattr(
                app,
                "set_field",
                lambda _key, _text, _fg=None, _tooltip=None: ui_threads.append(threading.get_ident()),
            )

            def _blocking_section(host: SectionHost, key: str) -> object:
                """
                Summary
                Block worker collection until the test permits completion.

                Inputs
                host: Recording section host. key: Section key.

                Outputs
                Empty diagnostics mapping.

                Side effects
                Coordinates test events and records a field operation.

                Error handling
                Raises AssertionError when the host is the live app.

                Ties to other methods
                Injected into `_refresh` as the section runner.

                Why this exists
                Proves refresh submission is non-blocking and Tk-isolated.
                """
                _ = key
                self.assertIsNot(host, app)
                entered.set()
                release.wait(timeout=2.0)
                host.set_field("network", "Healthy")
                return {}

            with patch("mac_health_checkup.app.gui.app.SECTION_HANDLERS", {"network": object()}):
                with patch("mac_health_checkup.app.gui.app.run_section", side_effect=_blocking_section):
                    app._refresh()
                    self.assertTrue(entered.wait(timeout=1.0))
                    future = cast(
                        concurrent.futures.Future[object],
                        app.__dict__.get("_refresh_future"),
                    )
                    self.assertFalse(future.done())
                    self.assertEqual(ui_threads, [])
                    release.set()
                    future.result(timeout=2.0)
                    app._poll_refresh_result()

            self.assertEqual(ui_threads, [main_thread])
            self.assertEqual(busy_states, [True, False])
            self.assertIn("info", status_levels)
            app._refresh_executor.shutdown(wait=True)
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_refresh_collects_off_thread_and_replays_on_tk_thread failed: {exc}"
            ) from exc

    def test_shutdown_poll_closes_window_after_signal_request(self) -> None:
        """
        Summary
        Ensure shutdown polling closes Tk promptly when lifecycle shutdown is already requested.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Invokes a stubbed window-close callback.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_schedule_shutdown_poll`.

        Why this exists
        SIGINT and SIGTERM update lifecycle state outside Tk's normal window-close path.
        """
        try:
            app = object.__new__(DashboardApp)
            app._shutdown = cast(ShutdownManager, _StubShutdown(requested=True))
            close_calls: list[str] = []
            setattr(app, "_on_close", lambda: close_calls.append("closed"))

            app._schedule_shutdown_poll()

            self.assertEqual(close_calls, ["closed"])
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_shutdown_poll_closes_window_after_signal_request failed: {exc}"
            ) from exc

    def test_render_table_empty_state_for_all_table_sections(self) -> None:
        """
        Summary
        Ensure all table-oriented sections render a consistent empty-state row when no data is available.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Invokes table rendering against multiple section keys.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `render_table`.

        Why this exists
        Empty table behavior must remain uniform across every table-rendering section.
        """
        try:
            app = object.__new__(DashboardApp)
            app._ui_tokens = _UiTokens(
                outer_pad_x=10,
                header_pad_top=12,
                header_pad_bottom=8,
                card_inner_pad_x=14,
                card_inner_pad_y=12,
                field_wrap_min_px=280,
                table_separator_min_chars=28,
                table_separator_max_chars=160,
                empty_table_message="No entries available.",
                empty_metrics_message="No metrics available.",
            )
            app._table_headers = {}
            setattr(app, "_configure_text_tags", lambda _widget: None)
            setattr(app, "_set_card_border", lambda _key, _mode: None)

            table_sections = ("devices", "display", "input", "ports", "processes", "startup")
            app._sections = {}
            widgets: dict[str, _StubTextBuffer] = {}
            for key in table_sections:
                widget = _StubTextBuffer(initial_text="stale-row\n")
                widgets[key] = widget
                app._sections[key] = _SectionWidgets(
                    frame=cast(tk.Frame, object()),
                    title=cast(tk.Label, object()),
                    subtitle=cast(tk.Label, object()),
                    field=cast(tk.Label, object()),
                    table=cast(tk.Text, widget),
                    metrics=None,
                )

            for key in table_sections:
                app.render_table(key, ("ColA", "ColB"), [])
                rendered = widgets[key].text()
                self.assertIn("ColA | ColB", rendered)
                self.assertIn("No entries available.", rendered)
                self.assertNotIn("stale-row", rendered)
                self.assertEqual(widgets[key].state, "disabled")
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_render_table_empty_state_for_all_table_sections failed: {exc}"
            ) from exc

    def test_render_metrics_empty_state_for_all_metrics_sections(self) -> None:
        """
        Summary
        Ensure all metrics-oriented sections render a consistent empty-state row when no metrics exist.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Invokes metrics rendering against multiple section keys.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `render_metrics_table`.

        Why this exists
        Metrics empty-state behavior must remain uniform across every metrics-rendering section.
        """
        try:
            app = object.__new__(DashboardApp)
            app._ui_tokens = _UiTokens(
                outer_pad_x=10,
                header_pad_top=12,
                header_pad_bottom=8,
                card_inner_pad_x=14,
                card_inner_pad_y=12,
                field_wrap_min_px=280,
                table_separator_min_chars=28,
                table_separator_max_chars=160,
                empty_table_message="No entries available.",
                empty_metrics_message="No metrics available.",
            )
            setattr(app, "_configure_text_tags", lambda _widget: None)
            setattr(app, "_set_card_border", lambda _key, _mode: None)

            metrics_sections = (
                "backups",
                "battery",
                "fan",
                "network",
                "performance",
                "power",
                "security",
                "ssd",
                "system",
                "updates",
            )
            app._sections = {}
            widgets: dict[str, _StubTextBuffer] = {}
            for key in metrics_sections:
                widget = _StubTextBuffer(initial_text="stale-metric\n")
                widgets[key] = widget
                app._sections[key] = _SectionWidgets(
                    frame=cast(tk.Frame, object()),
                    title=cast(tk.Label, object()),
                    subtitle=cast(tk.Label, object()),
                    field=cast(tk.Label, object()),
                    table=None,
                    metrics=cast(tk.Text, widget),
                )

            for key in metrics_sections:
                app.render_metrics_table(key, [], columns=2)
                rendered = widgets[key].text()
                self.assertIn("No metrics available.", rendered)
                self.assertNotIn("stale-metric", rendered)
                self.assertEqual(widgets[key].state, "disabled")
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_render_metrics_empty_state_for_all_metrics_sections failed: {exc}"
            ) from exc

    def test_clear_section_data_views_clears_table_and_metrics_content(self) -> None:
        """
        Summary
        Ensure section view clearing overwrites stale table and metrics text with a retry-safe fallback message.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Mutates table and metrics widget buffers.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_clear_section_data_views`.

        Why this exists
        Failed sections should never leave stale detail rows visible.
        """
        try:
            app = object.__new__(DashboardApp)
            table_widget = _StubTextBuffer(initial_text="old-table-data\n")
            metrics_widget = _StubTextBuffer(initial_text="old-metrics-data\n")
            app._sections = {
                "network": _SectionWidgets(
                    frame=cast(tk.Frame, object()),
                    title=cast(tk.Label, object()),
                    subtitle=cast(tk.Label, object()),
                    field=cast(tk.Label, object()),
                    table=cast(tk.Text, table_widget),
                    metrics=cast(tk.Text, metrics_widget),
                )
            }

            app._clear_section_data_views(
                "network",
                message="Data unavailable. The section will retry on the next refresh.",
            )

            self.assertEqual(
                table_widget.text(),
                "Data unavailable. The section will retry on the next refresh.\n",
            )
            self.assertEqual(
                metrics_widget.text(),
                "Data unavailable. The section will retry on the next refresh.\n",
            )
            self.assertEqual(table_widget.state, "disabled")
            self.assertEqual(metrics_widget.state, "disabled")
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_clear_section_data_views_clears_table_and_metrics_content failed: {exc}"
            ) from exc

    def test_keyboard_and_focus_handlers(self) -> None:
        """
        Summary
        Ensure keyboard shortcut binding and focus handlers delegate to the expected callbacks.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Records keyboard bindings and scroll delegation calls.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_bind_keyboard_shortcuts`, `_on_scroll_home`, `_on_scroll_end`,
        `_on_scroll_page_up`, `_on_scroll_page_down`, and `_card_state_handler`.

        Why this exists
        Keyboard and focus behaviors are critical accessibility affordances and must remain deterministic.
        """
        try:
            app = object.__new__(DashboardApp)
            bindings: list[str] = []
            setattr(app, "bind_all", lambda sequence, _handler: bindings.append(str(sequence)))
            app._bind_keyboard_shortcuts()
            expected = {"<F5>", "<KeyPress-r>", "<Home>", "<End>", "<Prior>", "<Next>"}
            self.assertTrue(expected.issubset(set(bindings)))

            app._scroll = cast(ScrollContainer, _StubScroll())
            self.assertEqual(app._on_scroll_home(cast(_EventMisc, SimpleNamespace())), "break")
            self.assertEqual(app._on_scroll_end(cast(_EventMisc, SimpleNamespace())), "break")
            self.assertEqual(app._on_scroll_page_up(cast(_EventMisc, SimpleNamespace())), "break")
            self.assertEqual(app._on_scroll_page_down(cast(_EventMisc, SimpleNamespace())), "break")
            scroll = cast(_StubScroll, app._scroll)
            self.assertEqual(scroll.to_top_calls, 1)
            self.assertEqual(scroll.to_bottom_calls, 1)
            self.assertEqual(scroll.page_calls, [-1, 1])

            border_calls: list[tuple[str, str]] = []
            setattr(
                app,
                "_set_card_border",
                lambda key, mode: border_calls.append((str(key), str(mode))),
            )
            handler = app._card_state_handler(key="network", mode="focus")
            handler(cast(_EventMisc, SimpleNamespace()))
            self.assertEqual(border_calls, [("network", "focus")])
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
                f"{MODULE_PATH}:GuiAppHelpersTests.test_keyboard_and_focus_handlers failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
