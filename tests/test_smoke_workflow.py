from __future__ import annotations

from typing import Callable, Optional, Sequence

import pytest

from mac_health_checkup.app.gui.dashboard.sections import SECTION_HANDLERS
from mac_health_checkup.app.gui.sections import network as network_section
from mac_health_checkup.app.gui.sections.types import SectionHost, Widget
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.diagnostics import (
    BatteryDiagnostics,
    BatteryTempDiagnostics,
    DeviceScanner,
    DisplayDiagnostics,
    DisplayTransportDiagnostics,
    FanDiagnostics,
    GeneralDiagnostics,
    InputDiagnostics,
    NetworkQualityDiagnostics,
    PortsDiagnostics,
    PowerAdapterDiagnostics,
    PowerResidencyDiagnostics,
    SSDDiagnostics,
    ThermalDiagnostics,
    USBPowerDiagnostics,
)

MODULE_PATH = "tests/test_smoke_workflow.py"


class StubHost(SectionHost):
    """
    Purpose: Minimal host to exercise section update functions without Tk.
    Ties: Used by the smoke workflow test to capture rendered output.
    Inputs: None. Initializes in-memory stores.
    Outputs: None. Provides in-memory storage for fields and tables.
    Side effects: Initializes in-memory collections.
    Why: Enables deterministic section updates without GUI dependencies.
    """

    def __init__(self) -> None:
        """
        Purpose: Initialize storage for rendered content.
        Ties: Used by test_smoke_section_updates.
        Inputs: None.
        Outputs: None. Sets initial dictionaries.
        Side effects: Initializes in-memory state.
        Why: Keeps test state deterministic and inspectable.
        """
        try:
            self.fields: dict[str, str] = {}
            self.metrics: dict[str, list[tuple[str, str, str]]] = {}
            self.tables: dict[str, list[tuple[str, ...]]] = {}
            self.headers: dict[str, tuple[str, ...]] = {}
            self._machine_hint: str = "mac"
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
            raise RuntimeError(f"{MODULE_PATH}:StubHost.__init__ failed: {exc}") from exc

    def get_widget(self, key: str) -> Optional[Widget]:
        """
        Purpose: Return no widget to force text fallback rendering.
        Ties: Used by section helpers that check for text widgets.
        Inputs: key is the widget identifier.
        Outputs: None to indicate no widget instance.
        Side effects: None.
        Why: Avoids Tk dependencies in tests.
        """
        try:
            return None
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
            raise RuntimeError(f"{MODULE_PATH}:StubHost.get_widget failed: {exc}") from exc

    def set_field(self, key: str, text: str, fg: Optional[str] = None, tooltip: Optional[str] = None) -> None:
        """
        Purpose: Store a simple field value for later assertions.
        Ties: Used by section update functions in fallback paths.
        Inputs: key is the field name, text is the content, fg and tooltip are ignored.
        Outputs: None. Updates in-memory field values.
        Side effects: Updates in-memory fields.
        Why: Captures output without rendering a GUI.
        """
        try:
            _ = fg
            _ = tooltip
            self.fields[key] = text
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
            raise RuntimeError(f"{MODULE_PATH}:StubHost.set_field failed: {exc}") from exc

    def render_metrics_table(
        self,
        key: str,
        rows: Sequence[tuple[str, str, str]],
        *,
        columns: int = 2,
    ) -> None:
        """
        Purpose: Capture metric table rows for assertions.
        Ties: Used by battery, fan, and performance sections.
        Inputs: key is the section key, rows are metrics, columns is ignored.
        Outputs: None. Stores the metric rows.
        Side effects: Updates in-memory metric rows.
        Why: Records structured output without Tk widgets.
        """
        try:
            _ = columns
            self.metrics[key] = list(rows)
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
            raise RuntimeError(f"{MODULE_PATH}:StubHost.render_metrics_table failed: {exc}") from exc

    def render_table(
        self,
        key: str,
        headers: tuple[str, ...],
        rows: Sequence[tuple[str, ...]],
        max_col_chars: tuple[int | None, ...] | None = None,
    ) -> None:
        """
        Purpose: Capture table headers and rows for assertions.
        Ties: Used by display and devices sections.
        Inputs: key is the section key, headers and rows define the table, max_col_chars is ignored.
        Outputs: None. Stores the table data.
        Side effects: Updates in-memory table data.
        Why: Enables deterministic checks for tabular output.
        """
        try:
            _ = max_col_chars
            self.headers[key] = headers
            self.tables[key] = list(rows)
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
            raise RuntimeError(f"{MODULE_PATH}:StubHost.render_table failed: {exc}") from exc

    def section_container(self, key: str) -> Optional[Widget]:
        """
        Purpose: Return no container to skip Tk rendering paths.
        Ties: Used by the network section when building custom layouts.
        Inputs: key is the section identifier.
        Outputs: None to indicate no container is available.
        Side effects: None.
        Why: Avoids creating Tk widgets in tests.
        """
        try:
            _ = key
            return None
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
            raise RuntimeError(f"{MODULE_PATH}:StubHost.section_container failed: {exc}") from exc

    def run_on_ui(self, fn: Callable[[], None]) -> None:
        """
        Purpose: Execute a callback immediately in the test context.
        Ties: Used by network section rendering.
        Inputs: fn is the callback to run.
        Outputs: None. Executes the callback.
        Side effects: Executes the callback.
        Why: Keeps UI callbacks deterministic in tests.
        """
        try:
            fn()
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
            raise RuntimeError(f"{MODULE_PATH}:StubHost.run_on_ui failed: {exc}") from exc

    def set_machine_hint(self, descriptor: str) -> None:
        """
        Purpose: Store a machine hint derived from a descriptor string.
        Ties: Used by the General section to inform other sections.
        Inputs: descriptor is the model string.
        Outputs: None. Updates internal hint state.
        Side effects: Updates in-memory machine hint.
        Why: Allows section logic to follow expected model branches.
        """
        try:
            desc = (descriptor or "").lower()
            if "pro" in desc:
                self._machine_hint = "pro"
            elif "air" in desc:
                self._machine_hint = "air"
            else:
                self._machine_hint = "mac"
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
            raise RuntimeError(f"{MODULE_PATH}:StubHost.set_machine_hint failed: {exc}") from exc

    def machine_hint(self) -> str:
        """
        Purpose: Return the stored machine hint.
        Ties: Used by battery and SSD sections for tooltips.
        Inputs: None.
        Outputs: The machine hint string.
        Side effects: None.
        Why: Mirrors the behavior of the real UI host.
        """
        try:
            return self._machine_hint
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
            raise RuntimeError(f"{MODULE_PATH}:StubHost.machine_hint failed: {exc}") from exc


def test_smoke_section_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Purpose: Exercise the full refresh workflow with deterministic diagnostics.
    Ties: Uses SECTION_HANDLERS to mirror the dashboard refresh cycle.
    Inputs: Monkeypatched diagnostics to avoid system calls.
    Outputs: Assertions on captured host output.
    Side effects: Mutates diagnostics functions via monkeypatch.
    Why: Provides an end to end smoke test of the main workflow.
    """
    try:
        monkeypatch.setattr(
            GeneralDiagnostics,
            "fetch",
            staticmethod(
                lambda: {"model": "MacBook Pro", "chip": "M2 Pro", "os": "14.5", "serial": "C02TEST"}
            ),
        )
        monkeypatch.setattr(
            ThermalDiagnostics,
            "fetch",
            staticmethod(lambda: {"state": "nominal", "raw": "ok"}),
        )
        monkeypatch.setattr(
            PowerResidencyDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "cpu_w": 4.2,
                    "gpu_w": 2.1,
                    "ane_w": 0.3,
                    "cpu_mhz": 1200,
                    "gpu_mhz": 800,
                    "cpu_resid_pct": 10,
                    "gpu_resid_pct": 5,
                    "raw": "ok",
                }
            ),
        )
        monkeypatch.setattr(
            PowerAdapterDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "adapter_w": 96,
                    "battery_w_live": 42,
                    "adapter_ma": 4800,
                    "adapter_v": 20,
                    "is_charging": True,
                    "raw": "ok",
                }
            ),
        )
        monkeypatch.setattr(
            BatteryTempDiagnostics,
            "fetch",
            staticmethod(lambda: {"temp_c": 35.0, "temp_f": 95.0, "raw": "ok"}),
        )
        monkeypatch.setattr(
            USBPowerDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "hubs": [
                        {
                            "headroom_ma": 500,
                            "name": "USB Hub",
                            "available_ma": 900,
                            "devices": [{"name": "Keyboard", "req_ma": 100}],
                        }
                    ],
                    "raw": "ok",
                }
            ),
        )
        monkeypatch.setattr(
            BatteryDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "percent_health": 92,
                    "full_capacity": 4700,
                    "design_capacity": 5100,
                    "cycle_count": 120,
                    "temperature_c": 32.0,
                    "voltage_mv": 12000,
                    "raw": "ok",
                }
            ),
        )
        monkeypatch.setattr(
            SSDDiagnostics,
            "fetch",
            staticmethod(
                lambda **_kwargs: {
                    "percent_left": 88,
                    "data_read": 0.12,
                    "data_written": 0.064,
                    "power_cycles": 35,
                    "temperature_c": 30,
                    "firmware": "TEST",
                    "power_on_hours": 200,
                    "unsafe_shutdowns": 1,
                    "media_errors": 0,
                    "raw": "ok",
                }
            ),
        )
        monkeypatch.setattr(
            FanDiagnostics,
            "fetch",
            staticmethod(lambda: {"fans": [{"name": "Fan 1", "rpm": 2000, "status": "OK"}], "raw": "ok"}),
        )
        monkeypatch.setattr(
            DisplayDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "raw": (
                        "Graphics/Displays:\\n"
                        "    Color LCD:\\n"
                        "      Resolution: 2560 x 1600\\n"
                        "      Mirror: Off\\n"
                        "      Connection Type: Internal\\n"
                        "      Refresh Rate: 60 Hz\\n"
                    )
                }
            ),
        )
        monkeypatch.setattr(
            DisplayTransportDiagnostics,
            "fetch",
            staticmethod(lambda _base: {"displays": ["Internal"], "raw": "ok"}),
        )
        monkeypatch.setattr(
            NetworkQualityDiagnostics,
            "fetch",
            staticmethod(
                lambda **_kwargs: {"down_mbps": 120, "up_mbps": 20, "rpm": 2000, "interface": "en0"}
            ),
        )
        monkeypatch.setattr(
            DeviceScanner,
            "scan_by_bus",
            staticmethod(
                lambda: {"usb": ["USB Keyboard"], "bluetooth": [], "thunderbolt": [], "network": []}
            ),
        )
        monkeypatch.setattr(
            PortsDiagnostics,
            "fetch",
            staticmethod(lambda: {"devices": ["USB-C"]}),
        )
        monkeypatch.setattr(
            InputDiagnostics,
            "fetch",
            staticmethod(lambda: {"details": ["USB Keyboard"]}),
        )

        def _render_override(host: SectionHost, data: JsonDict, interface: Optional[str]) -> None:
            """
            Purpose: Replace network render with a deterministic field update.
            Ties: Used by test_smoke_section_updates to avoid Tk widgets.
            Inputs: host is the test host, data is the diagnostics dict, interface is ignored.
            Outputs: None. Writes a simple field value.
            Side effects: Updates host fields.
            Why: Keeps the network section deterministic in tests.
            """
            try:
                _ = data
                _ = interface
                host.set_field("network", "ok")
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
                raise RuntimeError(f"{MODULE_PATH}:_render_override failed: {exc}") from exc

        monkeypatch.setattr(network_section, "_render", _render_override)

        host = StubHost()
        for key, handler in SECTION_HANDLERS.items():
            result = handler(host)
            assert isinstance(result, dict), f"{MODULE_PATH}:handler {key} did not return dict"

        assert "general" in host.fields
        assert "power" in host.metrics or "power" in host.fields
        assert "display" in host.tables or "display" in host.fields
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
        raise AssertionError(f"{MODULE_PATH}:test_smoke_section_updates failed: {exc}") from exc
