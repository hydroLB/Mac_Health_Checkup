from __future__ import annotations

import tkinter as tk
import unittest
from types import SimpleNamespace
from typing import Callable, cast
from unittest.mock import patch

from mac_health_checkup.app.gui.dashboard.render_mixin import _DashboardRenderMixin
from mac_health_checkup.app.gui.dashboard.ui_helpers import _SectionWidgets, _UiTokens
from mac_health_checkup.app.gui.widgets.tooltip import TooltipManager
from mac_health_checkup.core.config import Config

MODULE_PATH = "tests/test_gui_render_mixin.py"


class _RenderHost(_DashboardRenderMixin):
    pass


class _TkFrameStub:
    instances: list["_TkFrameStub"] = []

    def __init__(self, master: object, **kwargs: object) -> None:
        """
        Summary
        Initialize one frame stub and record constructor arguments.

        Inputs
        master: Stub parent widget.
        **kwargs: Frame construction options.

        Outputs
        None.

        Side effects
        Stores constructor state and appends the instance to `instances`.

        Error handling
        None.

        Ties to other methods
        Used by `_make_host` and `test_create_text_widget_wires_scrollbars_and_focus_handlers`.

        Why this exists
        The render helper tests need a lightweight frame replacement that records geometry calls.
        """
        self.master = master
        self.kwargs = dict(kwargs)
        self.pack_calls: list[dict[str, object]] = []
        _TkFrameStub.instances.append(self)

    def pack(self, **kwargs: object) -> None:
        """
        Summary
        Record one frame pack request.

        Inputs
        **kwargs: Geometry manager options.

        Outputs
        None.

        Side effects
        Appends one pack-call record.

        Error handling
        None.

        Ties to other methods
        Used by render helper geometry wiring tests.

        Why this exists
        The tests only need to inspect geometry behavior, not create real Tk containers.
        """
        self.pack_calls.append(dict(kwargs))


class _TkScrollbarStub:
    instances: list["_TkScrollbarStub"] = []

    def __init__(self, master: object, orient: str, **kwargs: object) -> None:
        """
        Summary
        Initialize one scrollbar stub and record constructor arguments.

        Inputs
        master: Stub parent widget.
        orient: Scrollbar orientation.
        **kwargs: Scrollbar construction options.

        Outputs
        None.

        Side effects
        Stores constructor state and appends the instance to `instances`.

        Error handling
        None.

        Ties to other methods
        Used by text-widget creation tests.

        Why this exists
        The tests need to verify scrollbar wiring without a live Tk root.
        """
        self.master = master
        self.orient = orient
        self.kwargs = dict(kwargs)
        self.command: object | None = None
        self.pack_calls: list[dict[str, object]] = []
        self.pack_forget_calls = 0
        self.set_calls: list[tuple[str, str]] = []
        _TkScrollbarStub.instances.append(self)

    def configure(self, **kwargs: object) -> None:
        """
        Summary
        Record scrollbar configuration and capture command callbacks.

        Inputs
        **kwargs: Scrollbar configuration options.

        Outputs
        None.

        Side effects
        Stores the `command` callback when present.

        Error handling
        None.

        Ties to other methods
        Used by `_create_text_widget`.

        Why this exists
        The tests need to assert that scroll commands are wired to the expected text-widget views.
        """
        command = kwargs.get("command")
        if callable(command):
            self.command = command

    def pack(self, **kwargs: object) -> None:
        """
        Summary
        Record one scrollbar pack request.

        Inputs
        **kwargs: Geometry manager options.

        Outputs
        None.

        Side effects
        Appends one pack-call record.

        Error handling
        None.

        Ties to other methods
        Used by render helper geometry tests.

        Why this exists
        The tests need to inspect scrollbar placement without real Tk geometry management.
        """
        self.pack_calls.append(dict(kwargs))

    def pack_forget(self) -> None:
        """
        Summary
        Record one request to hide the scrollbar.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Increments `pack_forget_calls`.

        Error handling
        None.

        Ties to other methods
        Used by horizontal overflow tests.

        Why this exists
        The tests need to confirm that horizontal overflow toggles visibility instead of destroying the widget.
        """
        self.pack_forget_calls += 1

    def set(self, first: str, last: str) -> None:
        """
        Summary
        Record one scrollbar thumb-position update.

        Inputs
        first: Leading normalized scroll fraction.
        last: Trailing normalized scroll fraction.

        Outputs
        None.

        Side effects
        Appends one tuple to `set_calls`.

        Error handling
        None.

        Ties to other methods
        Used by the x-scroll callback tests.

        Why this exists
        The tests need to verify that the helper mirrors text-widget scroll state into the scrollbar.
        """
        self.set_calls.append((first, last))


class _TkTextStub:
    instances: list["_TkTextStub"] = []

    def __init__(self, master: object, **kwargs: object) -> None:
        """
        Summary
        Initialize one text-widget stub and record constructor arguments.

        Inputs
        master: Stub parent widget.
        **kwargs: Text widget construction options.

        Outputs
        None.

        Side effects
        Stores constructor state and appends the instance to `instances`.

        Error handling
        None.

        Ties to other methods
        Used by `_create_text_widget` tests.

        Why this exists
        The tests need a minimal text-widget replacement that records wiring and configuration.
        """
        self.master = master
        self.kwargs = dict(kwargs)
        self.pack_calls: list[dict[str, object]] = []
        self.config_calls: list[dict[str, object]] = []
        self.bind_calls: list[tuple[str, object, str | None]] = []
        _TkTextStub.instances.append(self)

    def configure(self, **kwargs: object) -> None:
        """
        Summary
        Record text-widget configuration updates.

        Inputs
        **kwargs: Widget configuration options.

        Outputs
        None.

        Side effects
        Stores configuration history and updates the stub state map.

        Error handling
        None.

        Ties to other methods
        Used by `_create_text_widget`.

        Why this exists
        The tests need to inspect how the helper configures scrolling and appearance options.
        """
        self.config_calls.append(dict(kwargs))
        self.kwargs.update(kwargs)

    def pack(self, **kwargs: object) -> None:
        """
        Summary
        Record one text-widget pack request.

        Inputs
        **kwargs: Geometry manager options.

        Outputs
        None.

        Side effects
        Appends one pack-call record.

        Error handling
        None.

        Ties to other methods
        Used by text-widget creation tests.

        Why this exists
        The tests need to confirm that the created widget fills the expected container.
        """
        self.pack_calls.append(dict(kwargs))

    def bind(self, sequence: str, callback: object, add: str | None = None) -> None:
        """
        Summary
        Record one text-widget event binding.

        Inputs
        sequence: Tk event sequence.
        callback: Bound callback object.
        add: Optional Tk add flag.

        Outputs
        None.

        Side effects
        Appends one binding record.

        Error handling
        None.

        Ties to other methods
        Used by focus-handler tests.

        Why this exists
        The tests need to verify that focus handlers are still attached after the helper extraction.
        """
        self.bind_calls.append((sequence, callback, add))

    def yview(self, *args: object) -> tuple[object, ...]:
        """
        Summary
        Echo vertical-scroll arguments for command wiring tests.

        Inputs
        *args: Scroll command arguments.

        Outputs
        Tuple of the provided arguments.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used as the recorded vertical scroll command target.

        Why this exists
        The tests need an identity-style method to compare against stored scrollbar callbacks.
        """
        return args

    def xview(self, *args: object) -> tuple[object, ...]:
        """
        Summary
        Echo horizontal-scroll arguments for command wiring tests.

        Inputs
        *args: Scroll command arguments.

        Outputs
        Tuple of the provided arguments.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used as the recorded horizontal scroll command target.

        Why this exists
        The tests need an identity-style method to compare against stored scrollbar callbacks.
        """
        return args


class _StubTextBuffer:
    def __init__(self, initial_text: str = "") -> None:
        """
        Summary
        Initialize an in-memory text buffer stub.

        Inputs
        initial_text: Optional starting text.

        Outputs
        None.

        Side effects
        Seeds the internal chunk list and default state.

        Error handling
        None.

        Ties to other methods
        Used by render-plan application tests.

        Why this exists
        Some tests only need text-buffer semantics, not widget construction.
        """
        self._chunks: list[str] = [initial_text]
        self.state = "disabled"

    def configure(self, *, state: str) -> None:
        """
        Summary
        Record the current buffer state.

        Inputs
        state: Desired text-widget state.

        Outputs
        None.

        Side effects
        Updates `state`.

        Error handling
        None.

        Ties to other methods
        Used by helper-plan application tests.

        Why this exists
        The tests need to verify that text buffers toggle between normal and disabled as expected.
        """
        self.state = state

    def delete(self, start: str, end: str) -> None:
        """
        Summary
        Clear all buffered text.

        Inputs
        start: Ignored start index.
        end: Ignored end index.

        Outputs
        None.

        Side effects
        Empties the internal chunk list.

        Error handling
        None.

        Ties to other methods
        Used by render-plan application tests.

        Why this exists
        The tests only need the semantic effect of delete, not real Tk indexing.
        """
        _ = (start, end)
        self._chunks = []

    def insert(self, index: str, text: str, tags: tuple[str, ...] = ()) -> None:
        """
        Summary
        Append one text chunk to the buffer.

        Inputs
        index: Ignored insertion index.
        text: Text to append.
        tags: Ignored tag tuple.

        Outputs
        None.

        Side effects
        Appends `text` to the internal chunk list.

        Error handling
        None.

        Ties to other methods
        Used by render-plan application tests.

        Why this exists
        The tests only care about final composed text, not Tk insert semantics.
        """
        _ = (index, tags)
        self._chunks.append(text)

    def text(self) -> str:
        """
        Summary
        Return the concatenated buffer contents.

        Inputs
        None.

        Outputs
        Buffer text as one string.

        Side effects
        None.

        Error handling
        None.

        Ties to other methods
        Used by render-plan application tests.

        Why this exists
        The tests need an easy way to assert on the final rendered text.
        """
        return "".join(self._chunks)


class GuiRenderMixinTests(unittest.TestCase):
    def _make_host(self) -> _RenderHost:
        """
        Summary
        Build a minimal render-mixin host with deterministic config and callbacks.

        Inputs
        None.

        Outputs
        `_RenderHost` ready for isolated helper tests.

        Side effects
        Seeds host state used by the render mixin methods.

        Error handling
        None.

        Ties to other methods
        Used by the tests in `GuiRenderMixinTests`.

        Why this exists
        The render seam should be exercised without constructing the full dashboard application.
        """
        host = object.__new__(_RenderHost)
        host._cfg = cast(
            Config,
            SimpleNamespace(
                gui=SimpleNamespace(
                    scrollable_rows={"network": 4},
                    table_max_visible_rows=3,
                    table_row_height=22,
                ),
                fonts=SimpleNamespace(family_mono="Consolas", size_field=13),
            ),
        )
        host._sections = {}
        host._tooltips = cast(TooltipManager, SimpleNamespace(set_dynamic=lambda *args, **kwargs: None))
        host._table_headers = {}
        host._ui_tokens = _UiTokens(
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
        host._table_base_heights = {}
        host._set_card_border = lambda _key, _mode: None
        host._set_section_feedback = lambda _key, _message, level="info": None
        host._card_state_handler = lambda *, key, mode: (lambda _event: None)
        host._color = lambda token: f"#{token}"
        host._effective_table_height = lambda *, key, base_height: base_height + (
            1 if key == "network" else 0
        )
        return host

    def test_create_text_widget_wires_scrollbars_and_focus_handlers(self) -> None:
        """
        Summary
        Ensure the mixin wrapper still builds scrollable text widgets with both scrollbars and focus bindings.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches Tk constructors inside the render helper module.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_create_text_widget`.

        Why this exists
        The extracted support seam must preserve the widget contract used by renderers.
        """
        try:
            host = self._make_host()
            section = _SectionWidgets(
                frame=cast(tk.Frame, object()),
                title=cast(tk.Label, object()),
                subtitle=cast(tk.Label, object()),
                field=cast(tk.Label, object()),
            )

            _TkFrameStub.instances.clear()
            _TkScrollbarStub.instances.clear()
            _TkTextStub.instances.clear()
            with patch("mac_health_checkup.app.gui.dashboard.render_support.tk.Frame", _TkFrameStub):
                with patch(
                    "mac_health_checkup.app.gui.dashboard.render_support.tk.Scrollbar", _TkScrollbarStub
                ):
                    with patch("mac_health_checkup.app.gui.dashboard.render_support.tk.Text", _TkTextStub):
                        widget = host._create_text_widget("network", section, kind="table")

            self.assertIsNotNone(widget)
            self.assertEqual(len(_TkScrollbarStub.instances), 2)
            self.assertEqual({sb.orient for sb in _TkScrollbarStub.instances}, {"vertical", "horizontal"})
            self.assertEqual(len(_TkTextStub.instances), 1)
            text = _TkTextStub.instances[0]
            vertical = next(sb for sb in _TkScrollbarStub.instances if sb.orient == "vertical")
            horizontal = next(sb for sb in _TkScrollbarStub.instances if sb.orient == "horizontal")
            self.assertEqual(vertical.command, text.yview)
            self.assertEqual(horizontal.command, text.xview)
            self.assertTrue(any(call.get("fill") == "both" for call in text.pack_calls))
            self.assertEqual([call[0] for call in text.bind_calls], ["<FocusIn>", "<FocusOut>"])
            self.assertIs(section.table_container, _TkFrameStub.instances[0])
        except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiRenderMixinTests.test_create_text_widget_wires_scrollbars_and_focus_handlers failed: {exc}"
            ) from exc

    def test_create_text_widget_auto_hides_horizontal_scrollbar_without_overflow(self) -> None:
        """
        Summary
        Ensure the extracted helper still only shows the horizontal scrollbar when content overflows.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Drives the xscroll callback on the stub text widget.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_create_text_widget` horizontal overflow behavior.

        Why this exists
        The extraction should not regress the noise-reducing scrollbar affordance.
        """
        try:
            host = self._make_host()
            section = _SectionWidgets(
                frame=cast(tk.Frame, object()),
                title=cast(tk.Label, object()),
                subtitle=cast(tk.Label, object()),
                field=cast(tk.Label, object()),
            )

            _TkFrameStub.instances.clear()
            _TkScrollbarStub.instances.clear()
            _TkTextStub.instances.clear()
            with patch("mac_health_checkup.app.gui.dashboard.render_support.tk.Frame", _TkFrameStub):
                with patch(
                    "mac_health_checkup.app.gui.dashboard.render_support.tk.Scrollbar", _TkScrollbarStub
                ):
                    with patch("mac_health_checkup.app.gui.dashboard.render_support.tk.Text", _TkTextStub):
                        _ = host._create_text_widget("network", section, kind="table")

            text = _TkTextStub.instances[0]
            horizontal = next(sb for sb in _TkScrollbarStub.instances if sb.orient == "horizontal")
            xscroll = text.kwargs.get("xscrollcommand")
            self.assertTrue(callable(xscroll))
            xscroll_callback = cast(Callable[[object, object], object], xscroll)

            _ = xscroll_callback("0.0", "1.0")
            self.assertGreaterEqual(horizontal.pack_forget_calls, 1)
            self.assertEqual(len(horizontal.pack_calls), 0)
            _ = xscroll_callback("0.0", "0.72")
            self.assertEqual(len(horizontal.pack_calls), 1)
            _ = xscroll_callback(0.0, 1.0)
            self.assertGreaterEqual(horizontal.pack_forget_calls, 2)
        except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiRenderMixinTests.test_create_text_widget_auto_hides_horizontal_scrollbar_without_overflow failed: {exc}"
            ) from exc

    def test_render_table_and_metrics_empty_state_clear_stale_content(self) -> None:
        """
        Summary
        Ensure empty-state rendering still clears stale text after the support extraction.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Mutates render stubs for table and metrics sections.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `render_table` and `render_metrics_table`.

        Why this exists
        The coordinator methods should still own stale-data clearing and empty-state messaging.
        """
        try:
            host = self._make_host()
            setattr(host, "_configure_text_tags", lambda _widget: None)

            table_widget = _StubTextBuffer(initial_text="stale-row\n")
            metrics_widget = _StubTextBuffer(initial_text="stale-metric\n")
            host._sections = {
                "devices": _SectionWidgets(
                    frame=cast(tk.Frame, object()),
                    title=cast(tk.Label, object()),
                    subtitle=cast(tk.Label, object()),
                    field=cast(tk.Label, object()),
                    table=cast(tk.Text, table_widget),
                    metrics=None,
                ),
                "network": _SectionWidgets(
                    frame=cast(tk.Frame, object()),
                    title=cast(tk.Label, object()),
                    subtitle=cast(tk.Label, object()),
                    field=cast(tk.Label, object()),
                    table=None,
                    metrics=cast(tk.Text, metrics_widget),
                ),
            }

            host.render_table("devices", ("ColA", "ColB"), [])
            host.render_metrics_table("network", [], columns=2)

            self.assertIn("ColA | ColB", table_widget.text())
            self.assertIn("No entries available.", table_widget.text())
            self.assertNotIn("stale-row", table_widget.text())
            self.assertEqual(table_widget.state, "disabled")
            self.assertIn("No metrics available.", metrics_widget.text())
            self.assertNotIn("stale-metric", metrics_widget.text())
            self.assertEqual(metrics_widget.state, "disabled")
        except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiRenderMixinTests.test_render_table_and_metrics_empty_state_clear_stale_content failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
