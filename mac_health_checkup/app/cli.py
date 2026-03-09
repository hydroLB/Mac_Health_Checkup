from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from mac_health_checkup.app.gui.sections.types import SectionHost, Widget
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error

MODULE_PATH = "mac_health_checkup/app/cli.py"


@dataclass
class ConsoleHost(SectionHost):
    """
    Summary
    Simple console host for running sections without Tk.

    Inputs
    None. Initializes in-memory stores.

    Outputs
    None. Holds rendered content for CLI output.

    Side effects
    Stores output in memory.

    Error handling
    Methods raise `RuntimeError` with module and method context when unexpected failures occur.

    Ties to other methods
    Used by the CLI entrypoint for non-GUI operation.

    Why this exists
    Provides a fallback UI for scripts and tests.
    """

    fields: dict[str, str] = field(default_factory=dict)
    metrics: dict[str, list[tuple[str, str, str]]] = field(default_factory=dict)
    tables: dict[str, list[tuple[str, ...]]] = field(default_factory=dict)
    headers: dict[str, tuple[str, ...]] = field(default_factory=dict)
    diagnostics: dict[str, JsonDict] = field(default_factory=dict)
    _machine_hint: str = "mac"

    def get_widget(self, key: str) -> Optional[Widget]:
        """
        Summary
        Return no widget for console host.

        Inputs
        key: Widget identifier.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when unexpected failures occur.

        Ties to other methods
        Used by sections that query widget availability.

        Why this exists
        Console host does not use Tk widgets.
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
        Summary
        Store a field value for console output.

        Inputs
        key: Field key.
        text: Field content.
        fg: Ignored for console host.
        tooltip: Ignored for console host.

        Outputs
        None.

        Side effects
        Updates in-memory field values.

        Error handling
        Raises `RuntimeError` with module and method context when unexpected failures occur.

        Ties to other methods
        Used by sections for summary fields.

        Why this exists
        Keeps console output deterministic and inspectable.
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
        Summary
        Store metrics table rows for console output.

        Inputs
        key: Section key.
        rows: Metrics rows.
        columns: Ignored for console host.

        Outputs
        None.

        Side effects
        Updates in-memory metrics.

        Error handling
        Raises `RuntimeError` with module and method context when unexpected failures occur.

        Ties to other methods
        Used by metrics sections.

        Why this exists
        Keeps console output deterministic and inspectable.
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
        Summary
        Store table headers and rows for console output.

        Inputs
        key: Section key.
        headers: Column headers.
        rows: Table rows.
        max_col_chars: Ignored for console host.

        Outputs
        None.

        Side effects
        Updates in-memory tables.

        Error handling
        Raises `RuntimeError` with module and method context when unexpected failures occur.

        Ties to other methods
        Used by display and devices sections.

        Why this exists
        Keeps console output deterministic and inspectable.
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
        Summary
        Return no custom container for console host.

        Inputs
        key: Section key.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when unexpected failures occur.

        Ties to other methods
        Used by sections that may build custom layouts.

        Why this exists
        Console host uses no custom containers.
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
        Summary
        Execute a callback immediately.

        Inputs
        fn: Callback.

        Outputs
        None.

        Side effects
        Executes the callback.

        Error handling
        Raises `RuntimeError` with module and method context when callback execution fails unexpectedly.

        Ties to other methods
        Used by sections to schedule UI updates.

        Why this exists
        Simplifies execution in non-GUI contexts.
        """
        try:
            fn()
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.run_on_ui", "Failed to run callback", exc)
            ) from exc

    def set_machine_hint(self, descriptor: str) -> None:
        """
        Summary
        Store a machine hint based on descriptor string.

        Inputs
        descriptor: Model description string.

        Outputs
        None.

        Side effects
        Updates machine hint state.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by sections to adjust behavior.

        Why this exists
        Provides a basic device type hint for sections.
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
        Summary
        Return the current machine hint.

        Inputs
        None.

        Outputs
        Machine hint string.

        Side effects
        None.

        Error handling
        Raises `RuntimeError` with module and method context when accessing state fails unexpectedly.

        Ties to other methods
        Used by sections that adjust tooltips.

        Why this exists
        Provides a shared hint across sections.
        """
        try:
            return self._machine_hint
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "ConsoleHost.machine_hint", "Failed to get machine hint", exc)
            ) from exc
