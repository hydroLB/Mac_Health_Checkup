from __future__ import annotations

import tkinter as tk
import unittest
from types import SimpleNamespace
from typing import TYPE_CHECKING, TypeAlias, cast
from unittest.mock import patch

from mac_health_checkup.app.gui.widgets.tooltip import TooltipManager, TooltipTheme

MODULE_PATH = "tests/test_tooltip_manager_unit.py"

if TYPE_CHECKING:
    _EventMisc: TypeAlias = tk.Event[tk.Misc]
else:
    _EventMisc = object


class _StubRoot:
    def __init__(self) -> None:
        self.after_calls: list[tuple[int, object]] = []
        self.after_cancel_calls: list[str] = []
        self._next_id = 0

    def after(self, delay_ms: int, fn: object) -> str:
        self._next_id += 1
        after_id = str(self._next_id)
        self.after_calls.append((int(delay_ms), fn))
        return after_id

    def after_cancel(self, after_id: str) -> None:
        self.after_cancel_calls.append(str(after_id))


class _StubWidget:
    def __init__(self) -> None:
        self.bindings: list[tuple[str, object, str]] = []

    def bind(self, event: str, handler: object, add: str = "") -> None:
        self.bindings.append((str(event), handler, str(add)))


class _StubToplevel:
    def __init__(self, _root: object) -> None:
        self.configured: dict[str, object] = {}
        self.geometry_values: list[str] = []
        self.visible = False

    def withdraw(self) -> None:
        self.visible = False

    def overrideredirect(self, _value: bool) -> None:
        return

    def attributes(self, _key: str, _value: object) -> None:
        return

    def configure(self, **kwargs: object) -> None:
        self.configured.update(kwargs)

    def geometry(self, value: str) -> None:
        self.geometry_values.append(str(value))

    def deiconify(self) -> None:
        self.visible = True

    def destroy(self) -> None:
        self.visible = False


class _StubLabel:
    def __init__(self, _parent: object, **_kwargs: object) -> None:
        self.text: str = ""

    def configure(self, *, text: str) -> None:
        self.text = str(text)

    def pack(self) -> None:
        return


class TooltipManagerUnitTests(unittest.TestCase):
    """
    Summary
    Validate tooltip manager behavior without creating real Tk windows.

    Inputs
    None.

    Outputs
    Assertions on event bindings, scheduling, and tooltip lifecycle.

    Side effects
    Patches tkinter widget constructors in the tooltip module.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `mac_health_checkup/app/gui/widgets/tooltip.py`.

    Why this exists
    Tooltips are user-facing polish; this logic should remain deterministic and should not depend on a GUI display in tests.
    """

    def test_set_static_binds_once_and_shows_tip(self) -> None:
        """
        Summary
        Ensure static tooltips bind events once and create a tooltip window on hover.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches tk.Toplevel and tk.Label.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `set_static`, `_bind_once`, and `_show`.

        Why this exists
        Static tooltips are the common path for labels and buttons; regressions should be caught without Tk.
        """
        try:
            root = _StubRoot()
            theme = TooltipTheme(bg="#000", fg="#fff", font_family="Helvetica", font_size=10)
            widget = _StubWidget()
            mgr = TooltipManager(root=cast(tk.Tk, root), theme=theme, delay_ms=0)
            mgr.set_static(cast(tk.Widget, widget), " hello ")

            event = SimpleNamespace(widget=widget, x_root=10, y_root=20)
            with patch("mac_health_checkup.app.gui.widgets.tooltip.tk.Toplevel", _StubToplevel):
                with patch("mac_health_checkup.app.gui.widgets.tooltip.tk.Label", _StubLabel):
                    mgr._on_enter(cast(_EventMisc, event))
                    self.assertIsNotNone(mgr._tip)
                    self.assertIsNotNone(mgr._label)
                    if mgr._label is not None:
                        label = cast(_StubLabel, mgr._label)
                        self.assertEqual(label.text, "hello")
            self.assertTrue(any(b[0] == "<Enter>" for b in widget.bindings))
            self.assertTrue(any(b[0] == "<Motion>" for b in widget.bindings))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:TooltipManagerUnitTests.test_set_static_binds_once_and_shows_tip failed: {exc}"
            ) from exc

    def test_schedule_show_uses_after_and_cancel(self) -> None:
        """
        Summary
        Ensure scheduling uses root.after and cancels prior schedules when rescheduled.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_schedule_show` and `_cancel_scheduled`.

        Why this exists
        Rapid cursor motion should not queue multiple tooltip callbacks.
        """
        try:
            root = _StubRoot()
            theme = TooltipTheme(bg="#000", fg="#fff", font_family="Helvetica", font_size=10)
            widget = _StubWidget()
            mgr = TooltipManager(root=cast(tk.Tk, root), theme=theme, delay_ms=400)
            mgr.set_static(cast(tk.Widget, widget), "x")
            event = SimpleNamespace(widget=widget, x_root=0, y_root=0)
            mgr._schedule_show(cast(_EventMisc, event))
            self.assertEqual(len(root.after_calls), 1)
            mgr._schedule_show(cast(_EventMisc, event))
            self.assertEqual(len(root.after_cancel_calls), 1)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:TooltipManagerUnitTests.test_schedule_show_uses_after_and_cancel failed: {exc}"
            ) from exc

    def test_hide_destroys_tip_and_clears_state(self) -> None:
        """
        Summary
        Ensure hide cancels scheduled callbacks and destroys the tooltip window.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates a stub tip window via patched constructors.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `hide`, `_cancel_scheduled`, and `_destroy_tip`.

        Why this exists
        Tooltips must not linger after leaving a widget, and should release UI resources deterministically.
        """
        try:
            root = _StubRoot()
            theme = TooltipTheme(bg="#000", fg="#fff", font_family="Helvetica", font_size=10)
            widget = _StubWidget()
            mgr = TooltipManager(root=cast(tk.Tk, root), theme=theme, delay_ms=0)
            mgr.set_static(cast(tk.Widget, widget), "x")
            event = SimpleNamespace(widget=widget, x_root=0, y_root=0)
            with patch("mac_health_checkup.app.gui.widgets.tooltip.tk.Toplevel", _StubToplevel):
                with patch("mac_health_checkup.app.gui.widgets.tooltip.tk.Label", _StubLabel):
                    mgr._show(cast(_EventMisc, event))
                    self.assertIsNotNone(mgr._tip)
                    mgr.hide()
                    self.assertIsNone(mgr._tip)
                    self.assertIsNone(mgr._label)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:TooltipManagerUnitTests.test_hide_destroys_tip_and_clears_state failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
