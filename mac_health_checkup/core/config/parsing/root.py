from __future__ import annotations

from mac_health_checkup.core.config.models.root import Config
from mac_health_checkup.core.config.parsing.features import (
    parse_api,
    parse_display_transport,
    parse_fans,
    parse_gui,
    parse_thresholds,
)
from mac_health_checkup.core.config.parsing.observability import parse_logging
from mac_health_checkup.core.config.parsing.runtime import (
    parse_benchmarks,
    parse_io,
    parse_rate_limits,
    parse_retries,
    parse_shutdown,
    parse_timeouts,
)
from mac_health_checkup.core.config.parsing.ui import parse_colors, parse_fonts, parse_ui
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/core/config/parsing/root.py"


def parse_config(raw: JsonDict) -> Config:
    """
    Summary
    Parse raw JSON config into the typed `Config` registry.

    Inputs
    raw: Raw config dict decoded from JSON.

    Outputs
    `Config` instance with validated values.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Called by `get_config` after `load_raw_config` has returned a JSON dict.

    Why this exists
    Provides a single authoritative config translation layer between untyped JSON and strongly typed runtime use.
    """
    try:
        colors = parse_colors(raw)
        fonts = parse_fonts(raw)
        ui = parse_ui(raw)
        logging_conf = parse_logging(raw)
        retries = parse_retries(raw)
        rate_limits = parse_rate_limits(raw)
        io_conf = parse_io(raw)
        shutdown = parse_shutdown(raw)
        benchmarks = parse_benchmarks(raw)
        timeouts = parse_timeouts(raw)
        api = parse_api(raw)
        fans = parse_fans(raw)
        thresholds = parse_thresholds(raw)
        gui = parse_gui(raw)
        display_transport = parse_display_transport(raw)
        return Config(
            colors=colors,
            fonts=fonts,
            ui=ui,
            logging=logging_conf,
            retries=retries,
            rate_limits=rate_limits,
            io=io_conf,
            shutdown=shutdown,
            benchmarks=benchmarks,
            timeouts=timeouts,
            api=api,
            fans=fans,
            thresholds=thresholds,
            gui=gui,
            display_transport=display_transport,
        )
    except (TypeError, ValueError, KeyError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "parse_config", "Failed to parse config", exc)) from exc
