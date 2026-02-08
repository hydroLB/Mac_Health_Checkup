from __future__ import annotations

import json
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, TypeAlias, cast

from mac_health_checkup.app.gui.app import DashboardApp, _SectionWidgets
from mac_health_checkup.app.gui.widgets.scroll_container import ScrollContainer
from mac_health_checkup.core.config.models.root import Config

MODULE_PATH = "tests/test_gui_accessibility.py"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.json"

if TYPE_CHECKING:
    _EventMisc: TypeAlias = tk.Event[tk.Misc]
else:
    _EventMisc = object


def _hex_to_rgb01(value: str) -> tuple[float, float, float]:
    """
    Summary
    Convert a six-digit hex color string into normalized RGB channel values.

    Inputs
    value: Hex color string such as `#58a6ff`.

    Outputs
    Tuple of (r, g, b) channels in [0.0, 1.0].

    Side effects
    None.

    Error handling
    Raises `ValueError` when the color format is invalid.

    Ties to other methods
    Used by `_relative_luminance` and `_contrast_ratio`.

    Why this exists
    Accessibility contrast math requires normalized RGB values.
    """
    text = str(value).strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"Expected 6-digit hex color, got {value!r}")
    red = int(text[0:2], 16) / 255.0
    green = int(text[2:4], 16) / 255.0
    blue = int(text[4:6], 16) / 255.0
    return (red, green, blue)


def _to_linear(channel: float) -> float:
    """
    Summary
    Convert an sRGB channel value to linear RGB space.

    Inputs
    channel: sRGB channel in [0.0, 1.0].

    Outputs
    Linear RGB channel in [0.0, 1.0].

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `_relative_luminance`.

    Why this exists
    WCAG contrast computations require linearized channels.
    """
    return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4


def _relative_luminance(hex_color: str) -> float:
    """
    Summary
    Compute WCAG relative luminance for a hex color.

    Inputs
    hex_color: Hex color string.

    Outputs
    Relative luminance value.

    Side effects
    None.

    Error handling
    Propagates `ValueError` from color parsing.

    Ties to other methods
    Used by `_contrast_ratio`.

    Why this exists
    Luminance is required to compute contrast ratios objectively.
    """
    red, green, blue = _hex_to_rgb01(hex_color)
    return 0.2126 * _to_linear(red) + 0.7152 * _to_linear(green) + 0.0722 * _to_linear(blue)


def _contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """
    Summary
    Compute WCAG contrast ratio between foreground and background colors.

    Inputs
    fg_hex: Foreground color.
    bg_hex: Background color.

    Outputs
    Contrast ratio where higher values indicate stronger contrast.

    Side effects
    None.

    Error handling
    Propagates `ValueError` from color parsing.

    Ties to other methods
    Used by accessibility validation tests.

    Why this exists
    Objective contrast checks prevent future theme regressions.
    """
    lum_fg = _relative_luminance(fg_hex)
    lum_bg = _relative_luminance(bg_hex)
    high, low = (lum_fg, lum_bg) if lum_fg >= lum_bg else (lum_bg, lum_fg)
    return (high + 0.05) / (low + 0.05)


def _record_after_call(store: list[tuple[int, object]], delay_ms: int, callback: object) -> str:
    """
    Summary
    Record a Tk-style scheduled callback invocation and return a deterministic callback id.

    Inputs
    store: Mutable list receiving (delay_ms, callback) tuples.
    delay_ms: Delay in milliseconds.
    callback: Scheduled callback object.

    Outputs
    Deterministic callback id string.

    Side effects
    Appends scheduling metadata to `store`.

    Error handling
    None.

    Ties to other methods
    Used by keyboard operability tests to simulate Tk `after`.

    Why this exists
    Avoids mypy issues from lambda expressions that depend on list append side effects.
    """
    store.append((int(delay_ms), callback))
    return "after-id-1"


class _CardStub:
    def __init__(self) -> None:
        self.configure_calls: list[dict[str, object]] = []

    def configure(self, **kwargs: object) -> None:
        self.configure_calls.append(dict(kwargs))


class _ScrollStub:
    def __init__(self) -> None:
        self.top_calls = 0
        self.bottom_calls = 0
        self.page_calls: list[int] = []

    def scroll_to_top(self) -> None:
        self.top_calls += 1

    def scroll_to_bottom(self) -> None:
        self.bottom_calls += 1

    def scroll_pages(self, pages: int) -> None:
        self.page_calls.append(int(pages))


class GuiAccessibilityTests(unittest.TestCase):
    """
    Summary
    Validate baseline GUI accessibility requirements for contrast, focus visibility, and keyboard operation.

    Inputs
    None.

    Outputs
    Assertions over theme contrast and keyboard/focus behavior.

    Side effects
    Reads config JSON and exercises view-model logic with stubs.

    Error handling
    Raises AssertionError with module and test context on failures.

    Ties to other methods
    Exercises color semantics from `config/config.json` and event handlers in `DashboardApp`.

    Why this exists
    Accessibility regressions should be detected automatically rather than through ad hoc manual checks.
    """

    def test_theme_contrast_pairs_from_config(self) -> None:
        """
        Summary
        Ensure key text and status color pairs meet minimum contrast expectations from config.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Reads `config/config.json`.

        Error handling
        Raises AssertionError with context when a contrast pair drops below threshold.

        Ties to other methods
        Exercises config-driven visual roles used by `DashboardApp`.

        Why this exists
        Contrast should remain accessible as colors evolve.
        """
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            colors = raw["colors"]
            fonts = raw["fonts"]
            gui = raw["gui"]

            text_pairs: list[tuple[str, str, str]] = [
                ("fg_on_bg", colors["fg"], colors["bg"]),
                ("label_on_bg", colors["label"], colors["bg"]),
                ("field_on_card", colors["field"], gui["card_bg"]),
                ("section_on_card", colors["section"], gui["card_bg"]),
                ("label_on_card", colors["label"], gui["card_bg"]),
                ("ok_on_card", colors["ok"], gui["card_bg"]),
                ("warn_on_card", colors["warn"], gui["card_bg"]),
                ("bad_on_card", colors["bad"], gui["card_bg"]),
                ("tooltip_fg_on_bg", fonts["tooltip_fg"], fonts["tooltip_bg"]),
            ]
            for pair_name, foreground, background in text_pairs:
                ratio = _contrast_ratio(foreground, background)
                self.assertGreaterEqual(
                    ratio,
                    4.5,
                    msg=f"{pair_name} contrast dropped below 4.5:1 (actual {ratio:.2f}:1)",
                )

            focus_ratio = _contrast_ratio(colors["section"], gui["card_bg"])
            self.assertGreaterEqual(
                focus_ratio,
                3.0,
                msg=f"Focus indicator contrast dropped below 3.0:1 (actual {focus_ratio:.2f}:1)",
            )
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiAccessibilityTests.test_theme_contrast_pairs_from_config failed: {exc}"
            ) from exc

    def test_focus_visibility_uses_distinct_color_and_thickness(self) -> None:
        """
        Summary
        Ensure focus styling applies a distinct accent color with thicker border than the normal state.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Mutates a card stub via `_set_card_border`.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `DashboardApp._set_card_border`.

        Why this exists
        Keyboard users need a clearly visible focus indicator.
        """
        try:
            app = object.__new__(DashboardApp)
            app._cfg = cast(
                Config,
                SimpleNamespace(
                    gui=SimpleNamespace(card_border="#313d4b"),
                    colors=SimpleNamespace(section="#58a6ff"),
                ),
            )

            card = _CardStub()
            app._sections = {
                "network": _SectionWidgets(
                    frame=cast(tk.Frame, object()),
                    title=cast(tk.Label, object()),
                    subtitle=cast(tk.Label, object()),
                    field=cast(tk.Label, object()),
                    card=cast(tk.Frame, card),
                )
            }

            app._set_card_border("network", "normal")
            app._set_card_border("network", "focus")

            self.assertGreaterEqual(len(card.configure_calls), 2)
            normal_call = card.configure_calls[-2]
            focus_call = card.configure_calls[-1]
            self.assertEqual(normal_call.get("highlightbackground"), "#313d4b")
            self.assertEqual(normal_call.get("highlightthickness"), 1)
            self.assertEqual(focus_call.get("highlightbackground"), "#58a6ff")
            self.assertEqual(focus_call.get("highlightthickness"), 2)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiAccessibilityTests.test_focus_visibility_uses_distinct_color_and_thickness failed: {exc}"
            ) from exc

    def test_keyboard_only_operability_shortcuts_and_scroll_delegation(self) -> None:
        """
        Summary
        Ensure keyboard-only shortcuts are bound and scroll handlers delegate correctly.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Records global key bindings and scroll calls on stubs.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_bind_keyboard_shortcuts`, `_on_scroll_home`, `_on_scroll_end`,
        `_on_scroll_page_up`, `_on_scroll_page_down`, and `_on_refresh_shortcut`.

        Why this exists
        Core dashboard navigation should be fully operable without a mouse.
        """
        try:
            app = object.__new__(DashboardApp)
            bindings: list[str] = []
            setattr(app, "bind_all", lambda sequence, _handler: bindings.append(str(sequence)))

            refresh_after_calls: list[tuple[int, object]] = []
            refresh_cancel_calls: list[str] = []
            setattr(app, "_refresh", lambda: None)
            setattr(
                app,
                "after",
                lambda delay_ms, callback: _record_after_call(refresh_after_calls, int(delay_ms), callback),
            )
            setattr(app, "after_cancel", lambda after_id: refresh_cancel_calls.append(str(after_id)))
            app._refresh_after_id = "pending-id"
            app._scroll = cast(ScrollContainer, _ScrollStub())

            app._bind_keyboard_shortcuts()
            self.assertTrue(
                {"<F5>", "<KeyPress-r>", "<Home>", "<End>", "<Prior>", "<Next>"}.issubset(set(bindings))
            )

            self.assertEqual(app._on_refresh_shortcut(cast(_EventMisc, SimpleNamespace())), "break")
            self.assertEqual(refresh_cancel_calls, ["pending-id"])
            self.assertEqual(refresh_after_calls[0][0], 0)

            self.assertEqual(app._on_scroll_home(cast(_EventMisc, SimpleNamespace())), "break")
            self.assertEqual(app._on_scroll_end(cast(_EventMisc, SimpleNamespace())), "break")
            self.assertEqual(app._on_scroll_page_up(cast(_EventMisc, SimpleNamespace())), "break")
            self.assertEqual(app._on_scroll_page_down(cast(_EventMisc, SimpleNamespace())), "break")
            scroll_stub = cast(_ScrollStub, app._scroll)
            self.assertEqual(scroll_stub.top_calls, 1)
            self.assertEqual(scroll_stub.bottom_calls, 1)
            self.assertEqual(scroll_stub.page_calls, [-1, 1])
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiAccessibilityTests.test_keyboard_only_operability_shortcuts_and_scroll_delegation failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
