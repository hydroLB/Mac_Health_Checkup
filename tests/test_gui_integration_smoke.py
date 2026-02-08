from __future__ import annotations

import tkinter as tk
import unittest
from types import SimpleNamespace
from typing import TYPE_CHECKING, Callable, TypeAlias, cast
from unittest.mock import patch

from mac_health_checkup.app.gui.app import DashboardApp, _SectionWidgets, _UiTokens
from mac_health_checkup.app.gui.dashboard.lifecycle import ShutdownManager
from mac_health_checkup.app.gui.dashboard.queueing import SectionQueue
from mac_health_checkup.core.config.models.root import Config

MODULE_PATH = "tests/test_gui_integration_smoke.py"

if TYPE_CHECKING:
    _EventMisc: TypeAlias = tk.Event[tk.Misc]
else:
    _EventMisc = object


class _EventWidget:
    def __init__(self) -> None:
        self.bindings: dict[str, list[Callable[[tk.Event[tk.Misc]], None]]] = {}

    def bind(
        self,
        event: str,
        handler: Callable[[tk.Event[tk.Misc]], None],
        add: str = "",
    ) -> None:
        _ = add
        self.bindings.setdefault(str(event), []).append(handler)

    def trigger(self, event: str) -> None:
        handlers = list(self.bindings.get(str(event), []))
        for handler in handlers:
            handler(cast(_EventMisc, SimpleNamespace(widget=self)))


class _CardWidget(_EventWidget):
    def __init__(self) -> None:
        super().__init__()
        self.config_calls: list[dict[str, object]] = []

    def configure(self, **kwargs: object) -> None:
        self.config_calls.append(dict(kwargs))


class _FieldWidget(_EventWidget):
    def __init__(self) -> None:
        super().__init__()
        self.wraplength: int | None = None

    def configure(self, **kwargs: object) -> None:
        if "wraplength" in kwargs:
            self.wraplength = int(cast(int, kwargs["wraplength"]))


class _QueueStub:
    def __init__(self) -> None:
        self._keys: list[str] = []

    def enqueue(self, key: str) -> bool:
        self._keys.append(str(key))
        return True

    def drain(self) -> list[str]:
        out = list(self._keys)
        self._keys.clear()
        return out


class _ShutdownStub:
    def __init__(self, *, requested: bool) -> None:
        self._requested = bool(requested)

    def shutdown_requested(self) -> bool:
        return self._requested


class _TkFrameStub:
    instances: list["_TkFrameStub"] = []

    def __init__(self, _parent: object, **kwargs: object) -> None:
        self.kwargs = dict(kwargs)
        self.pack_calls: list[dict[str, object]] = []
        _TkFrameStub.instances.append(self)

    def pack(self, **kwargs: object) -> None:
        self.pack_calls.append(dict(kwargs))


class _TkScrollbarStub:
    instances: list["_TkScrollbarStub"] = []

    def __init__(self, _parent: object, **kwargs: object) -> None:
        self.kwargs = dict(kwargs)
        self.orient = str(kwargs.get("orient", "vertical"))
        self.command: object | None = None
        self.pack_calls: list[dict[str, object]] = []
        _TkScrollbarStub.instances.append(self)

    def pack(self, **kwargs: object) -> None:
        self.pack_calls.append(dict(kwargs))

    def configure(self, **kwargs: object) -> None:
        self.command = kwargs.get("command")

    def set(self, *_args: object) -> None:
        return


class _TkTextStub(_EventWidget):
    instances: list["_TkTextStub"] = []

    def __init__(self, _parent: object, **kwargs: object) -> None:
        super().__init__()
        self.kwargs = dict(kwargs)
        self.config_calls: list[dict[str, object]] = []
        self.pack_calls: list[dict[str, object]] = []
        _TkTextStub.instances.append(self)

    def configure(self, **kwargs: object) -> None:
        self.config_calls.append(dict(kwargs))

    def pack(self, **kwargs: object) -> None:
        self.pack_calls.append(dict(kwargs))

    def yview(self, *_args: object) -> None:
        return

    def xview(self, *_args: object) -> None:
        return


class GuiIntegrationSmokeTests(unittest.TestCase):
    """
    Summary
    Run deterministic smoke-style integration checks across core Tk dashboard interaction flows.

    Inputs
    None.

    Outputs
    Assertions on resize behavior, focus traversal, scrolling wiring, and refresh recovery.

    Side effects
    Patches Tk widget constructors in the dashboard module for headless deterministic execution.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `DashboardApp` integration paths across layout, events, rendering, and refresh lifecycle.

    Why this exists
    GUI smoke checks should validate key user journeys without relying on a live display server.
    """

    def test_resize_smoke_small_medium_large(self) -> None:
        """
        Summary
        Ensure wraplength updates deterministically for small, medium, and large window widths.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Mutates section field wraplength values.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_on_window_configure`.

        Why this exists
        Responsive readability is a core dashboard UX requirement.
        """
        try:
            app = object.__new__(DashboardApp)
            app._cfg = cast(Config, SimpleNamespace(gui=SimpleNamespace(content_wrap=760)))
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
            app._wraplength_px = None

            field_a = _FieldWidget()
            field_b = _FieldWidget()
            app._sections = {
                "a": _SectionWidgets(
                    frame=cast(tk.Frame, object()),
                    title=cast(tk.Label, object()),
                    subtitle=cast(tk.Label, object()),
                    field=cast(tk.Label, field_a),
                ),
                "b": _SectionWidgets(
                    frame=cast(tk.Frame, object()),
                    title=cast(tk.Label, object()),
                    subtitle=cast(tk.Label, object()),
                    field=cast(tk.Label, field_b),
                ),
            }

            setattr(app, "winfo_width", lambda: 320)
            app._on_window_configure(cast(_EventMisc, SimpleNamespace()))
            self.assertEqual(field_a.wraplength, 280)
            self.assertEqual(field_b.wraplength, 280)

            setattr(app, "winfo_width", lambda: 900)
            app._on_window_configure(cast(_EventMisc, SimpleNamespace()))
            self.assertEqual(field_a.wraplength, 760)
            self.assertEqual(field_b.wraplength, 760)

            setattr(app, "winfo_width", lambda: 1400)
            app._on_window_configure(cast(_EventMisc, SimpleNamespace()))
            self.assertEqual(field_a.wraplength, 760)
            self.assertEqual(field_b.wraplength, 760)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiIntegrationSmokeTests.test_resize_smoke_small_medium_large failed: {exc}"
            ) from exc

    def test_focus_traversal_smoke(self) -> None:
        """
        Summary
        Ensure focus and hover traversal handlers update card border state deterministically.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Simulates focus/hover events on section widgets.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_bind_card_affordances` and `_set_card_border`.

        Why this exists
        Keyboard tab traversal and pointer hover states must provide reliable visual affordance.
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

            card = _CardWidget()
            section = _SectionWidgets(
                frame=cast(tk.Frame, _EventWidget()),
                title=cast(tk.Label, _EventWidget()),
                subtitle=cast(tk.Label, _EventWidget()),
                field=cast(tk.Label, _EventWidget()),
                card=cast(tk.Frame, card),
            )
            app._sections = {"network": section}
            app._bind_card_affordances(key="network", section=section)

            cast(_EventWidget, section.field).trigger("<FocusIn>")
            cast(_EventWidget, section.field).trigger("<FocusOut>")
            cast(_EventWidget, section.title).trigger("<Enter>")
            cast(_EventWidget, section.title).trigger("<Leave>")

            focus_calls = [
                call
                for call in card.config_calls
                if call.get("highlightthickness") == 2 and call.get("highlightbackground") == "#58a6ff"
            ]
            normal_calls = [
                call
                for call in card.config_calls
                if call.get("highlightthickness") == 1 and call.get("highlightbackground") == "#313d4b"
            ]
            self.assertTrue(focus_calls)
            self.assertTrue(normal_calls)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiIntegrationSmokeTests.test_focus_traversal_smoke failed: {exc}"
            ) from exc

    def test_scroll_smoke_vertical_and_horizontal_text_widget(self) -> None:
        """
        Summary
        Ensure detail text widgets are wired with both vertical and horizontal scrolling behaviors.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches Tk constructors and records widget wiring behavior.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_create_text_widget`.

        Why this exists
        Wide diagnostic rows must remain accessible without clipping.
        """
        try:
            app = object.__new__(DashboardApp)
            app._cfg = cast(
                Config,
                SimpleNamespace(
                    gui=SimpleNamespace(
                        scrollable_rows={"network": 4}, table_max_visible_rows=3, card_bg="#1a212a"
                    ),
                    colors=SimpleNamespace(field="#e3eaf4"),
                    fonts=SimpleNamespace(family_mono="Consolas", size_field=13),
                ),
            )
            app._sections = {}
            setattr(app, "_set_card_border", lambda _key, _mode: None)

            section = _SectionWidgets(
                frame=cast(tk.Frame, object()),
                title=cast(tk.Label, object()),
                subtitle=cast(tk.Label, object()),
                field=cast(tk.Label, object()),
            )

            _TkFrameStub.instances.clear()
            _TkScrollbarStub.instances.clear()
            _TkTextStub.instances.clear()
            with patch("mac_health_checkup.app.gui.app.tk.Frame", _TkFrameStub):
                with patch("mac_health_checkup.app.gui.app.tk.Scrollbar", _TkScrollbarStub):
                    with patch("mac_health_checkup.app.gui.app.tk.Text", _TkTextStub):
                        widget = app._create_text_widget("network", section, kind="table")

            self.assertIsNotNone(widget)
            self.assertEqual(len(_TkScrollbarStub.instances), 2)
            orientations = {sb.orient for sb in _TkScrollbarStub.instances}
            self.assertEqual(orientations, {"vertical", "horizontal"})
            self.assertEqual(len(_TkTextStub.instances), 1)
            text = _TkTextStub.instances[0]
            self.assertTrue(callable(text.kwargs.get("yscrollcommand")))
            self.assertTrue(callable(text.kwargs.get("xscrollcommand")))

            vertical = next(sb for sb in _TkScrollbarStub.instances if sb.orient == "vertical")
            horizontal = next(sb for sb in _TkScrollbarStub.instances if sb.orient == "horizontal")
            self.assertEqual(vertical.command, text.yview)
            self.assertEqual(horizontal.command, text.xview)
            self.assertTrue(any(call.get("fill") == "both" for call in text.pack_calls))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiIntegrationSmokeTests.test_scroll_smoke_vertical_and_horizontal_text_widget failed: {exc}"
            ) from exc

    def test_refresh_error_injection_and_recovery_smoke(self) -> None:
        """
        Summary
        Ensure refresh loop handles section failure then recovers cleanly on the next cycle.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Runs two refresh cycles with injected failure then success.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_refresh` with patched section runner behavior.

        Why this exists
        Users need resilient feedback and recovery without restarting the app.
        """
        try:
            app = object.__new__(DashboardApp)
            app._queue = cast(SectionQueue, _QueueStub())
            app._shutdown = cast(ShutdownManager, _ShutdownStub(requested=True))
            app._cfg = cast(
                Config,
                SimpleNamespace(
                    colors=SimpleNamespace(bad="#e05d5d"), gui=SimpleNamespace(auto_refresh_ms=10000)
                ),
            )

            state: dict[str, str] = {}
            status_levels: list[str] = []
            clear_calls: list[str] = []
            setattr(app, "update_idletasks", lambda: None)
            setattr(app, "_schedule_next_refresh", lambda _delay_ms: None)
            setattr(app, "_set_status", lambda _text, level="info": status_levels.append(str(level)))
            setattr(app, "_clear_section_data_views", lambda key, message="": clear_calls.append(str(key)))
            setattr(
                app,
                "set_field",
                lambda key, text, fg=None, tooltip=None: state.__setitem__(str(key), str(text)),
            )

            run_count = {"value": 0}

            def _run_section(host: object, key: str) -> object:
                _ = key
                run_count["value"] += 1
                if run_count["value"] == 1:
                    raise RuntimeError("injected failure")
                cast(DashboardApp, host).set_field("network", "Recovered healthy data")
                return {"ok": True}

            with patch("mac_health_checkup.app.gui.app.SECTION_HANDLERS", {"network": object()}):
                with patch("mac_health_checkup.app.gui.app.run_section", side_effect=_run_section):
                    app._refresh()
                    app._refresh()

            self.assertIn("network", state)
            self.assertEqual(state["network"], "Recovered healthy data")
            self.assertEqual(clear_calls, ["network"])
            self.assertIn("warn", status_levels)
            self.assertIn("info", status_levels)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:GuiIntegrationSmokeTests.test_refresh_error_injection_and_recovery_smoke failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
