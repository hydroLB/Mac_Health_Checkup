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
from mac_health_checkup.diagnostics.backups import TimeMachineDiagnostics
from mac_health_checkup.diagnostics.processes import TopProcessesDiagnostics
from mac_health_checkup.diagnostics.security import SecurityPostureDiagnostics
from mac_health_checkup.diagnostics.startup import StartupItemsDiagnostics
from mac_health_checkup.diagnostics.system import SystemPressureDiagnostics
from mac_health_checkup.diagnostics.updates import SoftwareUpdateDiagnostics

MODULE_PATH = "tests/test_smoke_workflow.py"


class StubHost(SectionHost):
    """
    Summary
    Minimal host to exercise section update functions without Tk.

    Inputs
    None. Initializes in-memory stores.

    Outputs
    In-memory storage for fields, metrics, and tables.

    Side effects
    Initializes in-memory collections.

    Error handling
    Constructor and helpers raise `RuntimeError` with module context on unexpected failures.

    Ties to other methods
    Used by `test_smoke_section_updates` to capture rendered output.

    Why this exists
    Enables deterministic section updates without GUI dependencies.
    """

    def __init__(self) -> None:
        """
        Summary
        Initialize storage for rendered content.

        Inputs
        None.

        Outputs
        None. Initializes dictionaries for captured output.

        Side effects
        Initializes in-memory state.

        Error handling
        Raises `RuntimeError` with module context if initialization fails.

        Ties to other methods
        Used by `test_smoke_section_updates`.

        Why this exists
        Keeps test state deterministic and inspectable.
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
        Summary
        Return no widget to force text fallback rendering.

        Inputs
        `key` is the widget identifier.

        Outputs
        `None` to indicate no widget instance.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module context if the method fails.

        Ties to other methods
        Used by section helpers that check for text widgets.

        Why this exists
        Avoids Tk dependencies in tests.
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
        Summary
        Store a simple field value for later assertions.

        Inputs
        `key` is the field name; `text` is the content; `fg` and `tooltip` are ignored.

        Outputs
        None. Updates in-memory field values.

        Side effects
        Updates in-memory fields.

        Error handling
        Raises `RuntimeError` with module context if the method fails.

        Ties to other methods
        Used by section update functions in fallback paths.

        Why this exists
        Captures output without rendering a GUI.
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
        Summary
        Capture metric table rows for assertions.

        Inputs
        `key` is the section key; `rows` are metrics; `columns` is ignored.

        Outputs
        None. Stores the metric rows.

        Side effects
        Updates in-memory metric rows.

        Error handling
        Raises `RuntimeError` with module context if the method fails.

        Ties to other methods
        Used by battery, fan, and performance sections.

        Why this exists
        Records structured output without Tk widgets.
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
        Summary
        Capture table headers and rows for assertions.

        Inputs
        `key` is the section key; `headers` and `rows` define the table; `max_col_chars` is ignored.

        Outputs
        None. Stores the table data.

        Side effects
        Updates in-memory table data.

        Error handling
        Raises `RuntimeError` with module context if the method fails.

        Ties to other methods
        Used by display and devices sections.

        Why this exists
        Enables deterministic checks for tabular output.
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
        Summary
        Return no container to skip Tk rendering paths.

        Inputs
        `key` is the section identifier.

        Outputs
        `None` to indicate no container is available.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module context if the method fails.

        Ties to other methods
        Used by the network section when building custom layouts.

        Why this exists
        Avoids creating Tk widgets in tests.
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
        Summary
        Execute a callback immediately in the test context.

        Inputs
        `fn` is the callback to run.

        Outputs
        None. Executes the callback.

        Side effects
        Executes the callback.

        Error handling
        Raises `RuntimeError` with module context if the callback fails.

        Ties to other methods
        Used by network section rendering.

        Why this exists
        Keeps UI callbacks deterministic in tests.
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
        Summary
        Store a machine hint derived from a descriptor string.

        Inputs
        `descriptor` is the model string.

        Outputs
        None. Updates internal hint state.

        Side effects
        Updates in-memory machine hint.

        Error handling
        Raises `RuntimeError` with module context if the method fails.

        Ties to other methods
        Used by the General section to inform other sections.

        Why this exists
        Allows section logic to follow expected model branches.
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
        Summary
        Return the stored machine hint.

        Inputs
        None.

        Outputs
        The machine hint string.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module context if the method fails.

        Ties to other methods
        Used by battery and SSD sections for tooltips.

        Why this exists
        Mirrors the behavior of the real UI host.
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
    Summary
    Exercise the full refresh workflow with deterministic diagnostics.

    Inputs
    Monkeypatched diagnostics to avoid system calls.

    Outputs
    Assertions on captured host output.

    Side effects
    Mutates diagnostics functions via monkeypatch.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Uses `SECTION_HANDLERS` to mirror the dashboard refresh cycle.

    Why this exists
    Provides an end-to-end smoke test of the main workflow.
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
        monkeypatch.setattr(
            SecurityPostureDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "ok": True,
                    "filevault": {"enabled": True, "status": "on"},
                    "sip": {"enabled": True, "status": "enabled"},
                    "gatekeeper": {"enabled": True, "status": "enabled"},
                    "firewall": {"enabled": True, "status": "on"},
                }
            ),
        )
        monkeypatch.setattr(
            SystemPressureDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "ok": True,
                    "disk": {"free_percent": 25.0, "used_percent": 75.0},
                    "memory": {"free_percent": 55.0},
                }
            ),
        )
        monkeypatch.setattr(
            TopProcessesDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "top_cpu": [
                        {"pid": 1, "cpu_percent": 15.2, "mem_percent": 2.3, "command": "kernel_task"},
                        {"pid": 123, "cpu_percent": 7.1, "mem_percent": 0.8, "command": "WindowServer"},
                    ],
                    "top_mem": [
                        {"pid": 456, "cpu_percent": 0.5, "mem_percent": 9.7, "command": "Google Chrome"},
                        {"pid": 789, "cpu_percent": 1.2, "mem_percent": 6.3, "command": "Slack"},
                    ],
                }
            ),
        )
        monkeypatch.setattr(
            StartupItemsDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "ok": True,
                    "user_agents": ["com.test.user.agent"],
                    "system_agents": ["com.test.system.agent"],
                    "system_daemons": ["com.test.system.daemon"],
                }
            ),
        )
        monkeypatch.setattr(
            TimeMachineDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "ok": True,
                    "latest_backup_age_days": 2.2,
                    "running": False,
                }
            ),
        )
        monkeypatch.setattr(
            SoftwareUpdateDiagnostics,
            "fetch",
            staticmethod(
                lambda: {
                    "ok": True,
                    "updates_available": False,
                    "update_labels": [],
                }
            ),
        )

        def _render_override(host: SectionHost, data: JsonDict, interface: Optional[str]) -> None:
            """
            Summary
            Replace network render with a deterministic field update.

            Inputs
            `host` is the test host; `data` is the diagnostics dict; `interface` is ignored.

            Outputs
            None. Writes a simple field value.

            Side effects
            Updates host fields.

            Error handling
            Raises `RuntimeError` with module context if the override fails.

            Ties to other methods
            Used by `test_smoke_section_updates` to avoid Tk widgets.

            Why this exists
            Keeps the network section deterministic in tests.
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
