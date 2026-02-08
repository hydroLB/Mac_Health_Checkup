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
    Summary
    Define the interface for section render hosts.

    Inputs
    Implementations provide storage or UI widgets.

    Outputs
    Protocol definition only.

    Side effects
    None.

    Error handling
    Protocol methods include guard implementations that raise `NotImplementedError` when invoked directly.

    Ties to other methods
    Used by GUI and tests to decouple rendering logic.

    Why this exists
    Keeps section logic independent from GUI implementation details.
    """

    def get_widget(self, key: str) -> Optional[Widget]:
        """
        Summary
        Return a widget by key if one exists.

        Inputs
        key: Widget identifier.

        Outputs
        Widget object or None.

        Side effects
        None.

        Error handling
        Raises `NotImplementedError` when invoked on the protocol guard implementation.

        Ties to other methods
        Used by sections that check for optional widget support.

        Why this exists
        Allows sections to render to widgets or fall back to text.
        """
        try:
            raise NotImplementedError("SectionHost.get_widget protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.get_widget", "Protocol guard invoked", exc)
            ) from exc

    def set_field(self, key: str, text: str, fg: Optional[str] = None, tooltip: Optional[str] = None) -> None:
        """
        Summary
        Set a text field value with optional styling and tooltip.

        Inputs
        key: Field identifier.
        text: Content.
        fg: Optional foreground color.
        tooltip: Optional tooltip text.

        Outputs
        None.

        Side effects
        Updates UI or storage.

        Error handling
        Raises `NotImplementedError` when invoked on the protocol guard implementation.

        Ties to other methods
        Used by sections for summary values.

        Why this exists
        Standardizes field rendering across sections.
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
        Summary
        Render a metrics table into the host.

        Inputs
        key: Section key.
        rows: Metrics rows.
        columns: Column count.

        Outputs
        None.

        Side effects
        Updates UI or storage.

        Error handling
        Raises `NotImplementedError` when invoked on the protocol guard implementation.

        Ties to other methods
        Used by battery and fan sections.

        Why this exists
        Provides a consistent metrics table interface.
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
        Summary
        Render a general table into the host.

        Inputs
        key: Section key.
        headers: Column headers.
        rows: Table rows.
        max_col_chars: Optional per-column truncation limits.

        Outputs
        None.

        Side effects
        Updates UI or storage.

        Error handling
        Raises `NotImplementedError` when invoked on the protocol guard implementation.

        Ties to other methods
        Used by display and devices sections.

        Why this exists
        Provides a consistent table interface.
        """
        try:
            raise NotImplementedError("SectionHost.render_table protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.render_table", "Protocol guard invoked", exc)
            ) from exc

    def section_container(self, key: str) -> Optional[Widget]:
        """
        Summary
        Return a section container if one exists.

        Inputs
        key: Section key.

        Outputs
        Container object or None.

        Side effects
        None.

        Error handling
        Raises `NotImplementedError` when invoked on the protocol guard implementation.

        Ties to other methods
        Used by sections that build custom layouts.

        Why this exists
        Allows sections to optionally render custom widgets.
        """
        try:
            raise NotImplementedError("SectionHost.section_container protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.section_container", "Protocol guard invoked", exc)
            ) from exc

    def run_on_ui(self, fn: Callable[[], None]) -> None:
        """
        Summary
        Execute a callback on the UI thread.

        Inputs
        fn: Callback.

        Outputs
        None.

        Side effects
        Executes callback.

        Error handling
        Raises `NotImplementedError` when invoked on the protocol guard implementation.

        Ties to other methods
        Used by sections for safe UI updates.

        Why this exists
        Keeps UI updates thread safe.
        """
        try:
            raise NotImplementedError("SectionHost.run_on_ui protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.run_on_ui", "Protocol guard invoked", exc)
            ) from exc

    def set_machine_hint(self, descriptor: str) -> None:
        """
        Summary
        Store a machine hint derived from the model description.

        Inputs
        descriptor: Model string.

        Outputs
        None.

        Side effects
        Updates host state.

        Error handling
        Raises `NotImplementedError` when invoked on the protocol guard implementation.

        Ties to other methods
        Used by sections that adapt behavior based on machine type.

        Why this exists
        Provides a shared machine hint across sections.
        """
        try:
            raise NotImplementedError("SectionHost.set_machine_hint protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.set_machine_hint", "Protocol guard invoked", exc)
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
        Raises `NotImplementedError` when invoked on the protocol guard implementation.

        Ties to other methods
        Used by sections that tailor tooltips.

        Why this exists
        Provides a shared machine hint across sections.
        """
        try:
            raise NotImplementedError("SectionHost.machine_hint protocol guard")
        except NotImplementedError as exc:
            raise NotImplementedError(
                format_error(MODULE_PATH, "SectionHost.machine_hint", "Protocol guard invoked", exc)
            ) from exc
