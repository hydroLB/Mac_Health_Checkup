from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/core/config/models/ui.py"


@dataclass(frozen=True)
class ColorsConfig:
    """
    Summary
    Hold UI color configuration.

    Inputs
    Hex color strings for UI roles.

    Outputs
    Immutable color configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_colors` and used by GUI components for consistent theming.

    Why this exists
    Centralizes color tuning in a single config section.
    """

    bg: str
    fg: str
    ok: str
    warn: str
    bad: str
    section: str
    label: str
    field: str
    banner_good: str
    banner_warn: str
    banner_bad: str


@dataclass(frozen=True)
class FontsConfig:
    """
    Summary
    Hold UI font configuration.

    Inputs
    Font families, sizes, and weights.

    Outputs
    Immutable font configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_fonts` and used by GUI components to style text consistently.

    Why this exists
    Centralizes font tuning in a single config section.
    """

    family_default: str
    family_mono: str
    size_section: int
    size_banner: int
    size_field: int
    size_tooltip: int
    weight_bold: str
    weight_normal: str
    tooltip_bg: str
    tooltip_fg: str


@dataclass(frozen=True)
class UiConfig:
    """
    Summary
    Hold root UI window configuration.

    Inputs
    window_size: Window size string such as \"820x1180\".
    window_title: Window title label.
    color_mode: UI color mode (`light`, `dark`, or `auto`).

    Outputs
    Immutable UI configuration.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Parsed by `parse_ui` and used by the GUI entrypoint to size and title the window.

    Why this exists
    Keeps UI sizing and title tunable without code edits.
    """

    window_size: str
    window_title: str
    color_mode: str
