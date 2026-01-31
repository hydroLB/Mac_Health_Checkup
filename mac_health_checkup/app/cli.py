from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from mac_health_checkup.app.gui.sections.types import SectionHost, Widget
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/cli.py"


@dataclass
class ConsoleHost(SectionHost):
    """
    Purpose: Simple console host for running sections without Tk.
    Ties: Used by CLI entrypoint for non GUI operation.
    Inputs: None. Initializes in memory stores.
    Outputs: None. Holds rendered content.
    Side effects: Stores output in memory.
    Why: Provides a fallback UI for scripts and tests.
    """

    fields: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)
    tables: dict[str, list[tuple[str, ...]]] = field(default_factory=dict)
    headers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    _machine_hint: str = "mac"

    def get_widget(self, key: str) -> Optional[Widget]:
        """
        Purpose: Return no widget for console host.
        Ties: Used by sections that query widget availability.
        Inputs: key is the widget identifier.
        Outputs: None.
        Side effects: None.
        Why: Console host does not use Tk widgets.
        """
        try:
            _ = key
            return None
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.get_widget", "Failed to return widget", exc)
            ) from exc

    def set_field(self, key: str, text: str, fg: Optional[str] = None, tooltip: Optional[str] = None) -> None:
        """
        Purpose: Store a field value for console output.
        Ties: Used by sections for summary fields.
        Inputs: key identifies field, text is content, fg and tooltip ignored.
        Outputs: None.
        Side effects: Updates in memory field values.
        Why: Keeps console output deterministic and inspectable.
        """
        try:
            _ = fg
            _ = tooltip
            self.fields[key] = text
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.set_field", "Failed to set field", exc)
            ) from exc

    def render_metrics_table(
        self, key: str, rows: Sequence[tuple[str, str, str]], *, columns: int = 2
    ) -> None:
        """
        Purpose: Store metrics table rows for console output.
        Ties: Used by metrics sections.
        Inputs: key identifies section, rows are metrics, columns ignored.
        Outputs: None.
        Side effects: Updates in memory metrics.
        Why: Keeps console output deterministic and inspectable.
        """
        try:
            _ = columns
            self.metrics[key] = list(rows)
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.render_metrics_table", "Failed to render metrics", exc)
            ) from exc

    def render_table(
        self,
        key: str,
        headers: tuple[str, ...],
        rows: Sequence[tuple[str, ...]],
        max_col_chars: tuple[int | None, ...] | None = None,
    ) -> None:
        """
        Purpose: Store table headers and rows for console output.
        Ties: Used by display and devices sections.
        Inputs: key identifies section, headers and rows define table, max_col_chars ignored.
        Outputs: None.
        Side effects: Updates in memory tables.
        Why: Keeps console output deterministic and inspectable.
        """
        try:
            _ = max_col_chars
            self.headers[key] = headers
            self.tables[key] = list(rows)
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.render_table", "Failed to render table", exc)
            ) from exc

    def section_container(self, key: str) -> Optional[Widget]:
        """
        Purpose: Return no custom container for console host.
        Ties: Used by sections that may build custom layouts.
        Inputs: key identifies section.
        Outputs: None.
        Side effects: None.
        Why: Console host uses no custom containers.
        """
        try:
            _ = key
            return None
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.section_container", "Failed to return container", exc)
            ) from exc

    def run_on_ui(self, fn: Callable[[], None]) -> None:
        """
        Purpose: Execute a callback immediately.
        Ties: Used by sections to schedule UI updates.
        Inputs: fn is the callback.
        Outputs: None.
        Side effects: Executes the callback.
        Why: Simplifies execution in non GUI contexts.
        """
        try:
            fn()
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.run_on_ui", "Failed to run callback", exc)
            ) from exc

    def set_machine_hint(self, descriptor: str) -> None:
        """
        Purpose: Store a machine hint based on descriptor string.
        Ties: Used by sections to adjust behavior.
        Inputs: descriptor is the model description.
        Outputs: None.
        Side effects: Updates machine hint.
        Why: Provides a basic device type hint for sections.
        """
        try:
            desc = (descriptor or "").lower()
            if "pro" in desc:
                self._machine_hint = "pro"
            elif "air" in desc:
                self._machine_hint = "air"
            else:
                self._machine_hint = "mac"
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.set_machine_hint", "Failed to set machine hint", exc)
            ) from exc

    def machine_hint(self) -> str:
        """
        Purpose: Return the current machine hint.
        Ties: Used by sections that adjust tooltips.
        Inputs: None.
        Outputs: Machine hint string.
        Side effects: None.
        Why: Provides a shared hint across sections.
        """
        try:
            return self._machine_hint
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.machine_hint", "Failed to get machine hint", exc)
            ) from exc
