from __future__ import annotations

from mac_health_checkup.core.config.models.ui import ColorsConfig, FontsConfig, UiConfig
from mac_health_checkup.core.config.parsing.base import get_section
from mac_health_checkup.core.config.validation.primitives import require_int, require_str
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/parsing/ui.py"


def parse_colors(raw: JsonDict) -> ColorsConfig:
    """
    Summary
    Parse the `colors` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `ColorsConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when the section is missing or contains invalid values.

    Ties to other methods
    Used by `parse_config` to populate the typed `Config` registry.

    Why this exists
    Keeps theming knobs validated and easy to evolve without touching UI code.
    """
    try:
        section = get_section(raw, "colors")
        return ColorsConfig(
            bg=require_str(section.get("bg")),
            fg=require_str(section.get("fg")),
            ok=require_str(section.get("ok")),
            warn=require_str(section.get("warn")),
            bad=require_str(section.get("bad")),
            section=require_str(section.get("section")),
            label=require_str(section.get("label")),
            field=require_str(section.get("field")),
            banner_good=require_str(section.get("banner_good")),
            banner_warn=require_str(section.get("banner_warn")),
            banner_bad=require_str(section.get("banner_bad")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "parse_colors", "Failed to parse colors", exc)) from exc


def parse_fonts(raw: JsonDict) -> FontsConfig:
    """
    Summary
    Parse the `fonts` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `FontsConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by `parse_config`.

    Why this exists
    Centralizes font tuning while keeping values type-checked and validated.
    """
    try:
        section = get_section(raw, "fonts")
        return FontsConfig(
            family_default=require_str(section.get("family_default")),
            family_mono=require_str(section.get("family_mono")),
            size_section=require_int(8, 48)(section.get("size_section")),
            size_banner=require_int(8, 48)(section.get("size_banner")),
            size_field=require_int(8, 48)(section.get("size_field")),
            size_tooltip=require_int(6, 30)(section.get("size_tooltip")),
            weight_bold=require_str(section.get("weight_bold")),
            weight_normal=require_str(section.get("weight_normal")),
            tooltip_bg=require_str(section.get("tooltip_bg")),
            tooltip_fg=require_str(section.get("tooltip_fg")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "parse_fonts", "Failed to parse fonts", exc)) from exc


def parse_ui(raw: JsonDict) -> UiConfig:
    """
    Summary
    Parse the `ui` config section.

    Inputs
    raw: Raw config dict.

    Outputs
    `UiConfig` instance.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by `parse_config`.

    Why this exists
    Keeps window sizing and title tunable while enforcing valid string values.
    """
    try:
        section = get_section(raw, "ui")
        return UiConfig(
            window_size=require_str(section.get("window_size")),
            window_title=require_str(section.get("window_title")),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "parse_ui", "Failed to parse ui", exc)) from exc
