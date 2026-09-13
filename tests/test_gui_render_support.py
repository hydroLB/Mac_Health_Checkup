from __future__ import annotations

import tkinter as tk
import unittest
from typing import cast

from mac_health_checkup.app.gui.dashboard import render_support

MODULE_PATH = "tests/test_gui_render_support.py"


class _ScrollbarStub:
    def __init__(self) -> None:
        """
        Summary
        Initialize a scrollbar stub with empty call tracking.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Allocates geometry and configuration tracking collections.

        Error handling
        None.

        Ties to other methods
        Used by `GuiRenderSupportTests`.

        Why this exists
        The support-helper tests need to inspect scrollbar behavior without a real Tk root.
        """
        self.pack_calls: list[dict[str, object]] = []
        self.pack_forget_calls = 0
        self.configure_calls: list[dict[str, object]] = []

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
        Used by `set_horizontal_scrollbar_visibility`.

        Why this exists
        The tests need to confirm geometry behavior without real widget packing.
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
        Used by `set_horizontal_scrollbar_visibility`.

        Why this exists
        The tests need to verify hide/show behavior without real geometry management.
        """
        self.pack_forget_calls += 1

    def configure(self, **kwargs: object) -> None:
        """
        Summary
        Record scrollbar configuration updates.

        Inputs
        **kwargs: Scrollbar configuration options.

        Outputs
        None.

        Side effects
        Appends one configuration record.

        Error handling
        None.

        Ties to other methods
        Used by `style_scrollbar`.

        Why this exists
        The tests need to inspect scrollbar styling without a live Tk widget.
        """
        self.configure_calls.append(dict(kwargs))


class _TextStub:
    def __init__(self) -> None:
        """
        Summary
        Initialize a text-widget stub with empty tracking collections.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Allocates configuration, delete, insert, and tag tracking state.

        Error handling
        None.

        Ties to other methods
        Used by `GuiRenderSupportTests`.

        Why this exists
        The support-helper tests need to observe text operations without a real Tk text widget.
        """
        self.config_calls: list[dict[str, object]] = []
        self.delete_calls: list[tuple[str, str]] = []
        self.insert_calls: list[tuple[str, str, tuple[str, ...]]] = []
        self.tag_configure_calls: dict[str, dict[str, object]] = {}

    def configure(self, **kwargs: object) -> None:
        """
        Summary
        Record one text-widget configuration change.

        Inputs
        **kwargs: Widget configuration options.

        Outputs
        None.

        Side effects
        Appends one configuration record.

        Error handling
        None.

        Ties to other methods
        Used by `clear_text_widget`.

        Why this exists
        The tests need to verify state toggles without a real Tk widget.
        """
        self.config_calls.append(dict(kwargs))

    def delete(self, start: str, end: str) -> None:
        """
        Summary
        Record one text delete request.

        Inputs
        start: Start index.
        end: End index.

        Outputs
        None.

        Side effects
        Appends one delete-call record.

        Error handling
        None.

        Ties to other methods
        Used by `clear_text_widget`.

        Why this exists
        The tests need to confirm that the helper clears stale text before inserting replacement content.
        """
        self.delete_calls.append((start, end))

    def insert(self, index: str, text: str, tags: tuple[str, ...] = ()) -> None:
        """
        Summary
        Record one text insert request.

        Inputs
        index: Insert index.
        text: Inserted text.
        tags: Applied text tags.

        Outputs
        None.

        Side effects
        Appends one insert-call record.

        Error handling
        None.

        Ties to other methods
        Used by `clear_text_widget`.

        Why this exists
        The tests need to inspect fallback message styling without a real text widget.
        """
        self.insert_calls.append((index, text, tags))

    def tag_configure(self, tag: str, **kwargs: object) -> None:
        """
        Summary
        Record one tag configuration update.

        Inputs
        tag: Tag name.
        **kwargs: Tag styling options.

        Outputs
        None.

        Side effects
        Stores the latest configuration for `tag`.

        Error handling
        None.

        Ties to other methods
        Used by `configure_text_tags`.

        Why this exists
        The tests need to verify shared render tag definitions without a Tk text widget.
        """
        self.tag_configure_calls[tag] = dict(kwargs)


class GuiRenderSupportTests(unittest.TestCase):
    def test_status_to_tag_normalizes_shared_render_levels(self) -> None:
        """
        Summary
        Ensure shared status normalization maps supported levels and honors the fallback tag.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Covers `status_to_tag`.

        Why this exists
        Metrics rendering and fallback messaging should not drift onto different tag taxonomies.
        """
        try:
            self.assertEqual(render_support.status_to_tag("ok"), "ok")
            self.assertEqual(render_support.status_to_tag("success"), "ok")
            self.assertEqual(render_support.status_to_tag("warning"), "warn")
            self.assertEqual(render_support.status_to_tag("error"), "bad")
            self.assertEqual(render_support.status_to_tag("loading"), "loading")
            self.assertEqual(render_support.status_to_tag("info"), "info")
            self.assertEqual(render_support.status_to_tag("mystery", default="empty"), "empty")
        except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiRenderSupportTests.test_status_to_tag_normalizes_shared_render_levels failed: {exc}"
            ) from exc

    def test_plan_metrics_render_builds_success_and_empty_feedback(self) -> None:
        """
        Summary
        Ensure metrics render planning returns deterministic inserts and feedback for populated and empty states.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Covers `plan_metrics_render`.

        Why this exists
        The extracted helper should own row formatting so the mixin only performs Tk widget mutation.
        """
        try:
            populated = render_support.plan_metrics_render(
                rows=(("CPU", "42%", "ok"), ("Memory", "12 GB", "warn")),
                empty_metrics_message="No metrics",
                status_to_tag_fn=lambda status: f"tag-{status}",
            )
            empty = render_support.plan_metrics_render(
                rows=(),
                empty_metrics_message="No metrics",
                status_to_tag_fn=lambda status: f"tag-{status}",
            )

            self.assertEqual(
                populated.inserts,
                (
                    render_support.TextInsert("CPU: 42% "),
                    render_support.TextInsert("[ok]\n", ("tag-ok",)),
                    render_support.TextInsert("Memory: 12 GB "),
                    render_support.TextInsert("[warn]\n", ("tag-warn",)),
                ),
            )
            self.assertEqual(populated.feedback_message, "Showing 2 metrics.")
            self.assertEqual(populated.feedback_level, "success")
            self.assertEqual(
                empty.inserts,
                (render_support.TextInsert("No metrics\n", ("empty",)),),
            )
            self.assertEqual(empty.feedback_message, "No data returned for this section.")
            self.assertEqual(empty.feedback_level, "info")
        except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiRenderSupportTests.test_plan_metrics_render_builds_success_and_empty_feedback failed: {exc}"
            ) from exc

    def test_plan_table_render_builds_header_separator_and_empty_state(self) -> None:
        """
        Summary
        Ensure table render planning builds stable header, separator, row, and empty-state inserts.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Covers `plan_table_render`.

        Why this exists
        Table formatting is a pure formatting concern and should stay directly testable outside Tk.
        """
        try:
            populated = render_support.plan_table_render(
                headers=("Name", "Value"),
                rows=(("CPU", "42%"), ("Memory", "12 GB")),
                empty_table_message="No rows",
                separator_min_chars=8,
                separator_max_chars=40,
            )
            empty = render_support.plan_table_render(
                headers=("Name", "Value"),
                rows=(),
                empty_table_message="No rows",
                separator_min_chars=8,
                separator_max_chars=40,
            )

            self.assertEqual(
                populated.inserts,
                (
                    render_support.TextInsert("Name | Value\n", ("header",)),
                    render_support.TextInsert("--------------\n", ("separator",)),
                    render_support.TextInsert("CPU | 42%\n"),
                    render_support.TextInsert("Memory | 12 GB\n"),
                ),
            )
            self.assertEqual(populated.feedback_message, "Showing 2 rows.")
            self.assertEqual(populated.feedback_level, "success")
            self.assertEqual(
                empty.inserts,
                (
                    render_support.TextInsert("Name | Value\n", ("header",)),
                    render_support.TextInsert("------------\n", ("separator",)),
                    render_support.TextInsert("No rows\n", ("empty",)),
                ),
            )
            self.assertEqual(empty.feedback_message, "No data returned for this section.")
            self.assertEqual(empty.feedback_level, "info")
        except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiRenderSupportTests.test_plan_table_render_builds_header_separator_and_empty_state failed: {exc}"
            ) from exc

    def test_set_horizontal_scrollbar_visibility_toggles_geometry(self) -> None:
        """
        Summary
        Ensure helper packs and unpacks the horizontal scrollbar based on visibility.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Records pack and pack-forget calls on the scrollbar stub.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Covers `set_horizontal_scrollbar_visibility`.

        Why this exists
        The extracted helper should preserve the original overflow affordance behavior.
        """
        try:
            scrollbar = _ScrollbarStub()
            render_support.set_horizontal_scrollbar_visibility(
                scrollbar=cast(tk.Scrollbar, scrollbar), visible=True
            )
            render_support.set_horizontal_scrollbar_visibility(
                scrollbar=cast(tk.Scrollbar, scrollbar), visible=False
            )

            self.assertEqual(scrollbar.pack_calls, [{"side": "bottom", "fill": "x"}])
            self.assertEqual(scrollbar.pack_forget_calls, 1)
        except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiRenderSupportTests.test_set_horizontal_scrollbar_visibility_toggles_geometry failed: {exc}"
            ) from exc

    def test_clear_text_widget_preserves_level_tag_mapping(self) -> None:
        """
        Summary
        Ensure clearing a text widget reuses the same fallback tag mapping as the mixin.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Mutates the text stub and records inserted fallback tags.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Covers `clear_text_widget`.

        Why this exists
        The extracted helper must keep stale-detail replacement styling stable.
        """
        try:
            widget = _TextStub()
            render_support.clear_text_widget(
                widget=cast(tk.Text, widget),
                message="Section failed",
                level="error",
            )
            render_support.clear_text_widget(
                widget=cast(tk.Text, widget),
                message="Working",
                level="working",
            )
            render_support.clear_text_widget(
                widget=cast(tk.Text, widget),
                message="No rows",
                level="info",
            )

            tags = [call[2] for call in widget.insert_calls]
            self.assertEqual(tags, [("bad",), ("loading",), ("empty",)])
            self.assertEqual(widget.config_calls[0], {"state": "normal"})
            self.assertEqual(widget.config_calls[-1], {"state": "disabled"})
        except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiRenderSupportTests.test_clear_text_widget_preserves_level_tag_mapping failed: {exc}"
            ) from exc

    def test_configure_text_tags_registers_expected_shared_tags(self) -> None:
        """
        Summary
        Ensure extracted tag configuration still defines the shared render tags.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Records tag configuration calls on the text stub.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Covers `configure_text_tags`.

        Why this exists
        Rendered tables and metric lists depend on these shared tag names.
        """
        try:
            widget = _TextStub()
            render_support.configure_text_tags(
                widget=cast(tk.Text, widget),
                color_fn=lambda token: f"#{token}",
            )

            self.assertEqual(
                set(widget.tag_configure_calls),
                {"header", "separator", "ok", "warn", "bad", "info", "empty", "loading", "unknown"},
            )
            self.assertEqual(
                widget.tag_configure_calls["empty"],
                {"foreground": "#text.empty", "background": "#surface.inset"},
            )
        except (AssertionError, RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiRenderSupportTests.test_configure_text_tags_registers_expected_shared_tags failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
