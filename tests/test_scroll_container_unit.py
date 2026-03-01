from __future__ import annotations

import tkinter as tk
import unittest
from types import SimpleNamespace
from typing import TYPE_CHECKING, TypeAlias, cast

from mac_health_checkup.app.gui.widgets.scroll_container import ScrollContainer

MODULE_PATH = "tests/test_scroll_container_unit.py"

if TYPE_CHECKING:
    _EventMisc: TypeAlias = tk.Event[tk.Misc]
else:
    _EventMisc = object


class _StubCanvas:
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
        Raises contextual errors from `tests/test_scroll_container_unit.py:__init__` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_scroll_container_unit.py`.

        Why this exists
        Keeps `__init__` explicit, testable, and maintainable.
        """
        self.config_calls: list[dict[str, object]] = []
        self.bind_all_calls: list[str] = []
        self.unbind_all_calls: list[str] = []
        self.scroll_calls: list[tuple[int, str]] = []
        self.moveto_calls: list[float] = []
        self.itemconfigure_calls: list[tuple[object, dict[str, object]]] = []

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
        Raises contextual errors from `tests/test_scroll_container_unit.py:configure` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_scroll_container_unit.py`.

        Why this exists
        Keeps `configure` explicit, testable, and maintainable.
        """
        self.config_calls.append(dict(kwargs))

    def bbox(self, _tag: str) -> tuple[int, int, int, int]:
        """
        Summary
        Execute `bbox` for its module-level responsibility.

        Inputs
        _tag: `str` parameter from the function signature.

        Outputs
        Returns `tuple[int, int, int, int]`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_scroll_container_unit.py:bbox` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_scroll_container_unit.py`.

        Why this exists
        Keeps `bbox` explicit, testable, and maintainable.
        """
        return (0, 0, 10, 10)

    def bind_all(self, event: str, _handler: object) -> None:
        """
        Summary
        Execute `bind_all` for its module-level responsibility.

        Inputs
        event: `str` parameter from the function signature.
        _handler: `object` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_scroll_container_unit.py:bind_all` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_scroll_container_unit.py`.

        Why this exists
        Keeps `bind_all` explicit, testable, and maintainable.
        """
        self.bind_all_calls.append(str(event))

    def unbind_all(self, event: str) -> None:
        """
        Summary
        Execute `unbind_all` for its module-level responsibility.

        Inputs
        event: `str` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_scroll_container_unit.py:unbind_all` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_scroll_container_unit.py`.

        Why this exists
        Keeps `unbind_all` explicit, testable, and maintainable.
        """
        self.unbind_all_calls.append(str(event))

    def yview_scroll(self, steps: int, units: str) -> None:
        """
        Summary
        Execute `yview_scroll` for its module-level responsibility.

        Inputs
        steps: `int` parameter from the function signature.
        units: `str` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_scroll_container_unit.py:yview_scroll` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_scroll_container_unit.py`.

        Why this exists
        Keeps `yview_scroll` explicit, testable, and maintainable.
        """
        self.scroll_calls.append((int(steps), str(units)))

    def yview_moveto(self, value: float) -> None:
        """
        Summary
        Execute `yview_moveto` for its module-level responsibility.

        Inputs
        value: `float` parameter from the function signature.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_scroll_container_unit.py:yview_moveto` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_scroll_container_unit.py`.

        Why this exists
        Keeps `yview_moveto` explicit, testable, and maintainable.
        """
        self.moveto_calls.append(float(value))

    def itemconfigure(self, item: object, **kwargs: object) -> None:
        """
        Summary
        Execute `itemconfigure` for its module-level responsibility.

        Inputs
        item: `object` parameter from the function signature.
        **kwargs: variadic keyword `object` parameters.

        Outputs
        None.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_scroll_container_unit.py:itemconfigure` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_scroll_container_unit.py`.

        Why this exists
        Keeps `itemconfigure` explicit, testable, and maintainable.
        """
        self.itemconfigure_calls.append((item, dict(kwargs)))


class ScrollContainerUnitTests(unittest.TestCase):
    """
    Summary
    Validate scroll container behavior without constructing real Tk widgets.

    Inputs
    None.

    Outputs
    Assertions on canvas calls for scrolling and bindings.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises methods in `mac_health_checkup/app/gui/widgets/scroll_container.py`.

    Why this exists
    The scroll container is core UI infrastructure and should have deterministic behavior under unit tests.
    """

    def _new_instance(self) -> tuple[ScrollContainer, _StubCanvas]:
        """
        Summary
        Execute `_new_instance` for its module-level responsibility.

        Inputs
        None.

        Outputs
        Returns `tuple[ScrollContainer, _StubCanvas]`.

        Side effects
        None beyond this method boundary.

        Error handling
        Raises contextual errors from `tests/test_scroll_container_unit.py:_new_instance` when this method encounters invalid state or runtime failures.

        Ties to other methods
        Used by workflows in `tests/test_scroll_container_unit.py`.

        Why this exists
        Keeps `_new_instance` explicit, testable, and maintainable.
        """
        inst = object.__new__(ScrollContainer)
        canvas = _StubCanvas()
        inst._canvas = cast(tk.Canvas, canvas)
        inst._scroll_divisor = 120
        inst._content_window = 1
        return inst, canvas

    def test_mousewheel_scrolling_and_bindings(self) -> None:
        """
        Summary
        Ensure mousewheel handlers compute steps and install/remove bind_all handlers.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Mutates the stub canvas call lists.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_bind_mousewheel`, `_unbind_mousewheel`, `_on_mousewheel`, `_on_mousewheel_linux`.

        Why this exists
        Scroll behavior must be consistent across platforms and input devices.
        """
        try:
            sc, canvas = self._new_instance()
            sc._bind_mousewheel(cast(_EventMisc, SimpleNamespace()))
            self.assertIn("<MouseWheel>", canvas.bind_all_calls)
            sc._unbind_mousewheel(cast(_EventMisc, SimpleNamespace()))
            self.assertIn("<MouseWheel>", canvas.unbind_all_calls)

            sc._on_mousewheel(cast(_EventMisc, SimpleNamespace(delta=120)))
            sc._on_mousewheel(cast(_EventMisc, SimpleNamespace(delta=-120)))
            self.assertEqual(len(canvas.scroll_calls), 2)

            sc._on_mousewheel_linux(cast(_EventMisc, SimpleNamespace(num=4)))
            sc._on_mousewheel_linux(cast(_EventMisc, SimpleNamespace(num=5)))
            self.assertGreaterEqual(len(canvas.scroll_calls), 4)
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
                f"{MODULE_PATH}:ScrollContainerUnitTests.test_mousewheel_scrolling_and_bindings failed: {exc}"
            ) from exc

    def test_configure_handlers_update_canvas(self) -> None:
        """
        Summary
        Ensure configure handlers update scrollregion and embedded window width.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Records canvas configuration calls.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_on_content_configure`, `_on_canvas_configure`, and `scroll_to_top`.

        Why this exists
        The scroll region and width settings are required for a stable, readable card layout.
        """
        try:
            sc, canvas = self._new_instance()
            sc._on_content_configure(cast(_EventMisc, SimpleNamespace()))
            self.assertTrue(any("scrollregion" in call for call in canvas.config_calls))

            sc._on_canvas_configure(cast(_EventMisc, SimpleNamespace(width=800)))
            self.assertEqual(canvas.itemconfigure_calls[-1][1].get("width"), 800)

            sc.scroll_to_top()
            self.assertEqual(canvas.moveto_calls[-1], 0.0)
            sc.scroll_to_bottom()
            self.assertEqual(canvas.moveto_calls[-1], 1.0)
            sc.scroll_pages(2)
            self.assertEqual(canvas.scroll_calls[-1], (2, "pages"))
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
                f"{MODULE_PATH}:ScrollContainerUnitTests.test_configure_handlers_update_canvas failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
