from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Protocol, Sequence, TypeAlias

from mac_health_checkup.core.utils.errors import format_error

if TYPE_CHECKING:
    import tkinter as tk

    Widget: TypeAlias = tk.Widget
else:
    Widget: TypeAlias = object


MODULE_PATH = "mac_health_checkup/app/gui/sections/types.py"


class SectionHost(Protocol):
    """
    Purpose: Define the interface for section render hosts.
    Ties: Used by GUI and tests to decouple rendering logic.
    Inputs: Implementations provide storage or UI widgets.
    Outputs: Protocol definition only.
    Side effects: None.
    Why: Keeps section logic independent from GUI implementation details.
    """

    def get_widget(self, key: str) -> Optional[Widget]:
        """
        Purpose: Return a widget by key if one exists.
        Ties: Used by sections that check for optional widget support.
        Inputs: key identifies the widget.
        Outputs: Widget object or None.
        Side effects: None.
        Why: Allows sections to render to widgets or fallback to text.
        """
        try:
            raise NotImplementedError("SectionHost.get_widget protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.get_widget", "Protocol guard invoked", exc)
            ) from exc

    def set_field(self, key: str, text: str, fg: Optional[str] = None, tooltip: Optional[str] = None) -> None:
        """
        Purpose: Set a text field value with optional styling and tooltip.
        Ties: Used by sections for summary values.
        Inputs: key identifies field, text is content, fg and tooltip are optional.
        Outputs: None.
        Side effects: Updates UI or storage.
        Why: Standardizes field rendering across sections.
        """
        try:
            raise NotImplementedError("SectionHost.set_field protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.set_field", "Protocol guard invoked", exc)
            ) from exc

    def render_metrics_table(
        self, key: str, rows: Sequence[tuple[str, str, str]], *, columns: int = 2
    ) -> None:
        """
        Purpose: Render a metrics table into the host.
        Ties: Used by battery and fan sections.
        Inputs: key identifies the section, rows are metrics, columns sets layout.
        Outputs: None.
        Side effects: Updates UI or storage.
        Why: Provides a consistent metrics table interface.
        """
        try:
            raise NotImplementedError("SectionHost.render_metrics_table protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.render_metrics_table", "Protocol guard invoked", exc)
            ) from exc

    def render_table(
        self,
        key: str,
        headers: tuple[str, ...],
        rows: Sequence[tuple[str, ...]],
        max_col_chars: tuple[int | None, ...] | None = None,
    ) -> None:
        """
        Purpose: Render a general table into the host.
        Ties: Used by display and devices sections.
        Inputs: key identifies the section, headers and rows define the table.
        Outputs: None.
        Side effects: Updates UI or storage.
        Why: Provides a consistent table interface.
        """
        try:
            raise NotImplementedError("SectionHost.render_table protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.render_table", "Protocol guard invoked", exc)
            ) from exc

    def section_container(self, key: str) -> Optional[Widget]:
        """
        Purpose: Return a section container if one exists.
        Ties: Used by sections that build custom layouts.
        Inputs: key identifies the section.
        Outputs: Container object or None.
        Side effects: None.
        Why: Allows sections to optionally render custom widgets.
        """
        try:
            raise NotImplementedError("SectionHost.section_container protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.section_container", "Protocol guard invoked", exc)
            ) from exc

    def run_on_ui(self, fn: Callable[[], None]) -> None:
        """
        Purpose: Execute a callback on the UI thread.
        Ties: Used by sections for safe UI updates.
        Inputs: fn is a callback.
        Outputs: None.
        Side effects: Executes callback.
        Why: Keeps UI updates thread safe.
        """
        try:
            raise NotImplementedError("SectionHost.run_on_ui protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.run_on_ui", "Protocol guard invoked", exc)
            ) from exc

    def set_machine_hint(self, descriptor: str) -> None:
        """
        Purpose: Store a machine hint derived from the model description.
        Ties: Used by sections that adapt behavior based on machine type.
        Inputs: descriptor is the model string.
        Outputs: None.
        Side effects: Updates host state.
        Why: Provides a shared machine hint across sections.
        """
        try:
            raise NotImplementedError("SectionHost.set_machine_hint protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.set_machine_hint", "Protocol guard invoked", exc)
            ) from exc

    def machine_hint(self) -> str:
        """
        Purpose: Return the current machine hint.
        Ties: Used by sections that tailor tooltips.
        Inputs: None.
        Outputs: Machine hint string.
        Side effects: None.
        Why: Provides a shared machine hint across sections.
        """
        try:
            raise NotImplementedError("SectionHost.machine_hint protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.machine_hint", "Protocol guard invoked", exc)
            ) from exc
