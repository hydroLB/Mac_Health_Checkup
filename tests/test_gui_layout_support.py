from __future__ import annotations

import tkinter as tk
import unittest
from collections.abc import Callable
from types import SimpleNamespace
from typing import cast
from unittest import mock

from mac_health_checkup.app.gui.dashboard.layout_support import (
    bind_card_affordances,
    build_section_widgets,
    compute_field_wraplength,
    effective_table_height_for_width,
    resolve_card_border_style,
)
from mac_health_checkup.app.gui.dashboard.ui_helpers import _SectionWidgets, _UiTokens
from mac_health_checkup.app.gui.widgets.controls import InlineStatusBadge
from mac_health_checkup.core.config import Config

MODULE_PATH = "tests/test_gui_layout_support.py"


class _BoundWidget:
    """
    Summary
    Minimal bind-capable widget stub for layout support tests.

    Inputs
    None.

    Outputs
    Stub widget with recorded bind calls.

    Side effects
    Records bind invocations in `bind_calls`.

    Error handling
    None.

    Ties to other methods
    Used by `GuiLayoutSupportTests`.

    Why this exists
    The helper tests need lightweight Tk-like widgets without creating a real Tk root.
    """

    def __init__(self) -> None:
        """
        Summary
        Initialize bind-call tracking for the widget stub.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Allocates the `bind_calls` collection.

        Error handling
        None.

        Ties to other methods
        Used by `bind`.

        Why this exists
        The tests need deterministic inspection of which events were bound to each stub widget.
        """
        self.bind_calls: list[tuple[str, object, str | None]] = []

    def bind(self, sequence: str, handler: object, add: str | None = None) -> None:
        """
        Summary
        Record one bind request.

        Inputs
        sequence: Tk event sequence.
        handler: Bound handler object.
        add: Optional Tk add flag.

        Outputs
        None.

        Side effects
        Appends one tuple to `bind_calls`.

        Error handling
        None.

        Ties to other methods
        Used by `bind_card_affordances`.

        Why this exists
        The tests only need to observe which events were bound and with what add mode.
        """
        self.bind_calls.append((str(sequence), handler, add))


class _PackWidget:
    """
    Summary
    Minimal widget stub that records construction, configure, and pack calls.

    Inputs
    parent: Optional parent widget.
    **kwargs: Constructor options.

    Outputs
    Stub widget with call tracking.

    Side effects
    Stores constructor options and later widget interactions for assertions.

    Error handling
    None.

    Ties to other methods
    Used by `test_build_section_widgets_returns_expected_bundle`.

    Why this exists
    The section-card builder test needs lightweight widget stand-ins without creating a real Tk root.
    """

    def __init__(self, parent: object | None = None, **kwargs: object) -> None:
        """
        Summary
        Initialize the widget stub with empty interaction logs.

        Inputs
        parent: Optional parent object.
        **kwargs: Constructor options to retain for assertions.

        Outputs
        None.

        Side effects
        Allocates `pack_calls` and `configure_calls`.

        Error handling
        None.

        Ties to other methods
        Used by `pack` and `configure`.

        Why this exists
        The test needs to inspect widget assembly details after `build_section_widgets` runs.
        """
        self.parent = parent
        self.kwargs = dict(kwargs)
        self.pack_calls: list[dict[str, object]] = []
        self.configure_calls: list[dict[str, object]] = []

    def pack(self, **kwargs: object) -> None:
        """
        Summary
        Record one widget pack call.

        Inputs
        **kwargs: Geometry options.

        Outputs
        None.

        Side effects
        Appends one pack-call record.

        Error handling
        None.

        Ties to other methods
        Used by `build_section_widgets`.

        Why this exists
        The layout helper test verifies widget placement without a live Tk geometry manager.
        """
        self.pack_calls.append(dict(kwargs))

    def configure(self, **kwargs: object) -> None:
        """
        Summary
        Record one widget configuration call.

        Inputs
        **kwargs: Configuration options.

        Outputs
        None.

        Side effects
        Appends one configuration record.

        Error handling
        None.

        Ties to other methods
        Used by `build_section_widgets`.

        Why this exists
        The test needs to confirm field-label affordances such as `takefocus`.
        """
        self.configure_calls.append(dict(kwargs))


class GuiLayoutSupportTests(unittest.TestCase):
    """
    Summary
    Validate the extracted Tk layout support helpers.

    Inputs
    None.

    Outputs
    Standard unittest assertions.

    Side effects
    Exercises helper functions with lightweight stubs.

    Error handling
    Raises assertion failures with contextual messages.

    Ties to other methods
    Covers `layout_support.py`.

    Why this exists
    The layout seam should have direct tests instead of relying only on higher-level GUI smoke tests.
    """

    def test_build_section_widgets_returns_expected_bundle(self) -> None:
        """
        Summary
        Ensure the extracted section-card builder assembles the expected widgets, defaults, and tooltip wiring.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Records widget construction, pack calls, and tooltip registrations.

        Error handling
        Raises AssertionError with contextual details on failure.

        Ties to other methods
        Exercises `build_section_widgets`.

        Why this exists
        The most coupled extracted layout helper should have direct evidence that it preserves the original card contract.
        """
        try:
            parent = _PackWidget()
            tooltip_calls: list[tuple[object, str]] = []
            label_calls: list[dict[str, object]] = []

            def _new_label(
                *,
                parent: tk.Misc,
                text: str | None = None,
                textvariable: tk.StringVar | None = None,
                bg: str,
                fg: str,
                font_size: int,
                font_weight: str,
                wraplength: int | None = None,
                justify: str = "left",
            ) -> tk.Label:
                """
                Summary
                Record one label-construction request and return a pack-capable stub widget.

                Inputs
                Matches the section label-factory contract.

                Outputs
                Stub label widget.

                Side effects
                Appends one constructor-call record.

                Error handling
                None.

                Ties to other methods
                Passed to `build_section_widgets`.

                Why this exists
                The test needs to inspect how the helper configures title, subtitle, and field labels.
                """
                label_kwargs = {
                    "parent": parent,
                    "text": text,
                    "textvariable": textvariable,
                    "bg": bg,
                    "fg": fg,
                    "font_size": font_size,
                    "font_weight": font_weight,
                    "wraplength": wraplength,
                    "justify": justify,
                }
                label_calls.append(dict(label_kwargs))
                return cast(
                    tk.Label,
                    _PackWidget(parent, **{k: v for k, v in label_kwargs.items() if k != "parent"}),
                )

            cfg = SimpleNamespace(
                gui=SimpleNamespace(section_pady=9, content_wrap=420),
                fonts=SimpleNamespace(
                    size_section=18,
                    size_field=13,
                    size_tooltip=11,
                    weight_bold="bold",
                    weight_normal="normal",
                    family_default="SF Pro Text",
                ),
            )
            ui_tokens = _UiTokens(
                outer_pad_x=20,
                header_pad_top=12,
                header_pad_bottom=10,
                card_inner_pad_x=14,
                card_inner_pad_y=16,
                field_wrap_min_px=180,
                table_separator_min_chars=12,
                table_separator_max_chars=72,
                empty_table_message="No rows",
                empty_metrics_message="No metrics",
            )

            with (
                mock.patch(
                    "mac_health_checkup.app.gui.dashboard.layout_support.tk.Frame",
                    side_effect=lambda parent_arg, **kwargs: _PackWidget(parent_arg, **kwargs),
                ),
                mock.patch(
                    "mac_health_checkup.app.gui.dashboard.layout_support.InlineStatusBadge",
                    side_effect=lambda parent_arg, **kwargs: _PackWidget(parent_arg, **kwargs),
                ),
            ):
                section = build_section_widgets(
                    parent=cast(tk.Frame, parent),
                    key="network",
                    title="Network",
                    subtitle="Connectivity and reachability",
                    cfg=cast(Config, cfg),
                    ui_tokens=ui_tokens,
                    color_fn=lambda token: f"#{token}",
                    new_label_fn=_new_label,
                    set_tooltip_fn=lambda widget, text: tooltip_calls.append((widget, text)),
                )

            section_frame = cast(_PackWidget, section.frame)
            field_widget = cast(_PackWidget, section.field)

            self.assertIs(section_frame.parent, parent)
            self.assertEqual(section_frame.kwargs["bg"], "#surface.card")
            self.assertEqual(section.card, section.frame)
            self.assertIsNotNone(section.feedback)
            self.assertEqual(len(label_calls), 3)
            self.assertEqual(label_calls[0]["text"], "Network")
            self.assertEqual(label_calls[1]["text"], "Connectivity and reachability")
            self.assertEqual(label_calls[2]["text"], "Waiting for section data...")
            self.assertEqual(label_calls[2]["wraplength"], 420)
            self.assertEqual(field_widget.configure_calls, [{"anchor": "w", "takefocus": 1}])
            self.assertEqual(len(tooltip_calls), 3)
            self.assertTrue(all(bool(text.strip()) for _, text in tooltip_calls))
        except (AssertionError, RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiLayoutSupportTests.test_build_section_widgets_returns_expected_bundle failed: {exc}"
            ) from exc

    def test_bind_card_affordances_deduplicates_targets(self) -> None:
        """
        Summary
        Ensure card affordance binding deduplicates shared widgets and restores the normal border state.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Records bind calls and border reset requests.

        Error handling
        Raises AssertionError with contextual details on failure.

        Ties to other methods
        Exercises `bind_card_affordances`.

        Why this exists
        The extracted helper should preserve the dashboard's existing hover and focus binding contract.
        """
        try:
            card = _BoundWidget()
            title = _BoundWidget()
            subtitle = _BoundWidget()
            field = _BoundWidget()
            feedback = _BoundWidget()
            section = _SectionWidgets(
                frame=cast(tk.Frame, card),
                title=cast(tk.Label, title),
                subtitle=cast(tk.Label, subtitle),
                field=cast(tk.Label, field),
                feedback=cast(InlineStatusBadge, feedback),
                card=cast(tk.Frame, card),
            )
            handler_requests: list[tuple[str, str]] = []
            border_requests: list[tuple[str, str]] = []

            def _handler_factory(key: str, mode: str) -> Callable[[tk.Event[tk.Misc]], None]:
                """
                Summary
                Record the requested card-state transition and return a no-op handler.

                Inputs
                key: Section key.
                mode: Requested interaction mode.

                Outputs
                No-op Tk event handler.

                Side effects
                Appends one `(key, mode)` tuple to `handler_requests`.

                Error handling
                None.

                Ties to other methods
                Passed to `bind_card_affordances`.

                Why this exists
                The test needs to verify that the helper asks for the expected hover and focus handlers.
                """
                handler_requests.append((key, mode))
                return lambda _event: None

            bind_card_affordances(
                key="network",
                section=section,
                card_state_handler_fn=_handler_factory,
                set_card_border_fn=lambda key, mode: border_requests.append((key, mode)),
            )

            self.assertEqual(len(card.bind_calls), 4)
            self.assertEqual(len(title.bind_calls), 4)
            self.assertEqual(len(subtitle.bind_calls), 4)
            self.assertEqual(len(field.bind_calls), 4)
            self.assertEqual(len(feedback.bind_calls), 4)
            self.assertEqual(border_requests, [("network", "normal")])
            self.assertEqual(
                handler_requests,
                [
                    ("network", "hover"),
                    ("network", "normal"),
                    ("network", "focus"),
                    ("network", "normal"),
                ]
                * 5,
            )
        except (AssertionError, RuntimeError, TypeError, ValueError, AttributeError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiLayoutSupportTests.test_bind_card_affordances_deduplicates_targets failed: {exc}"
            ) from exc

    def test_resolve_card_border_style_returns_expected_styles(self) -> None:
        """
        Summary
        Ensure interaction states map to the expected border colors and thicknesses.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with contextual details on failure.

        Ties to other methods
        Exercises `resolve_card_border_style`.

        Why this exists
        Focus and hover styling is accessibility-relevant behavior that should stay explicit.
        """
        try:
            self.assertEqual(
                resolve_card_border_style(
                    mode="focus",
                    default_border="#111111",
                    hover_border="#222222",
                    focus_border="#333333",
                ),
                ("#333333", 2),
            )
            self.assertEqual(
                resolve_card_border_style(
                    mode="hover",
                    default_border="#111111",
                    hover_border="#222222",
                    focus_border="#333333",
                ),
                ("#222222", 1),
            )
            self.assertEqual(
                resolve_card_border_style(
                    mode="unexpected",
                    default_border="#111111",
                    hover_border="#222222",
                    focus_border="#333333",
                ),
                ("#111111", 1),
            )
        except (AssertionError, RuntimeError, TypeError, ValueError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiLayoutSupportTests.test_resolve_card_border_style_returns_expected_styles failed: {exc}"
            ) from exc

    def test_responsive_layout_math_clamps_wrap_and_height(self) -> None:
        """
        Summary
        Ensure responsive sizing math clamps wrap length and table height across breakpoints.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with contextual details on failure.

        Ties to other methods
        Exercises `effective_table_height_for_width` and `compute_field_wraplength`.

        Why this exists
        The extracted math should remain easy to review and stable across small and large windows.
        """
        try:
            self.assertEqual(effective_table_height_for_width(width=500, base_height=5, breakpoint=760), 3)
            self.assertEqual(effective_table_height_for_width(width=700, base_height=5, breakpoint=760), 4)
            self.assertEqual(effective_table_height_for_width(width=900, base_height=5, breakpoint=760), 5)

            self.assertEqual(
                compute_field_wraplength(width=320, outer_pad=20, min_wrap=180, max_wrap=760), 208
            )
            self.assertEqual(
                compute_field_wraplength(width=120, outer_pad=20, min_wrap=180, max_wrap=760), 180
            )
            self.assertEqual(
                compute_field_wraplength(width=1600, outer_pad=20, min_wrap=180, max_wrap=760), 760
            )
        except (AssertionError, RuntimeError, TypeError, ValueError) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiLayoutSupportTests.test_responsive_layout_math_clamps_wrap_and_height failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
