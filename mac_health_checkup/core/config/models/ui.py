from __future__ import annotations

from dataclasses import dataclass

MODULE_PATH = "mac_health_checkup/core/config/models/ui.py"


@dataclass(frozen=True)
class ColorsConfig:
    """
    Purpose: Hold UI color configuration.
    Ties: Used by GUI components for consistent theming.
    Inputs: Hex color strings for UI roles.
    Outputs: Immutable color configuration.
    Side effects: None.
    Why: Centralizes color tuning in a single config section.
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
    Purpose: Hold UI font configuration.
    Ties: Used by GUI components to style text consistently.
    Inputs: Font families, sizes, and weights.
    Outputs: Immutable font configuration.
    Side effects: None.
    Why: Centralizes font tuning in a single config section.
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
    Purpose: Hold root UI window configuration.
    Ties: Used by the GUI entrypoint to size the window.
    Inputs: window_size string such as \"820x1180\", window_title label.
    Outputs: Immutable UI configuration.
    Side effects: None.
    Why: Keeps UI sizing and title tunable without code edits.
    """

    window_size: str
    window_title: str
