from __future__ import annotations

import argparse
import cProfile
import pstats
from pathlib import Path

from mac_health_checkup.app.gui.sections.display.parsing import _parse_raw_display_rows
from mac_health_checkup.core.constants import BENCH_ITERATIONS
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.regex_utils import hz_from_text
from mac_health_checkup.core.utils.usb_tree import _extract_usb_tree_items

MODULE_PATH = "benchmarks/profile.py"
DEFAULT_PROFILE_OUT = Path(__file__).resolve().parent / "profile.pstats"


def _sample_display_text() -> str:
    """
    Purpose: Provide deterministic sample display text for profiling.
    Ties: Used by the display profiling target below.
    Inputs: None.
    Outputs: Raw display text string.
    Side effects: None.
    Why: Keeps profiling deterministic and independent of system_profiler.
    """
    try:
        return (
            "Graphics/Displays:\\n"
            "    Color LCD:\\n"
            "      Resolution: 2560 x 1600\\n"
            "      Mirror: Off\\n"
            "      Connection Type: Internal\\n"
            "      Refresh Rate: 60 Hz\\n"
            "    DELL U2718Q:\\n"
            "      Resolution: 3840 x 2160\\n"
            "      Mirror: Off\\n"
            "      Connection Type: DisplayPort\\n"
            "      Refresh Rate: 60 Hz\\n"
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_sample_display_text", "Failed to build sample display text", exc)
        ) from exc


def _sample_usb_text() -> str:
    """
    Purpose: Provide deterministic sample USB tree text for profiling.
    Ties: Used by the USB profiling target below.
    Inputs: None.
    Outputs: Raw USB tree text string.
    Side effects: None.
    Why: Keeps profiling deterministic and independent of system_profiler.
    """
    try:
        return (
            "    USB:\\n"
            "        USB 3.0 Bus:\\n"
            "            Vendor Name: Apple Inc.\\n"
            "            Magic Trackpad:\\n"
            "                Manufacturer: Apple Inc.\\n"
            "        USB 2.0 Bus:\\n"
            "            USB Keyboard:\\n"
            "                Vendor Name: Logitech\\n"
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_sample_usb_text", "Failed to build sample USB text", exc)
        ) from exc


def _profile_display_parse(iterations: int) -> None:
    """
    Purpose: Profile raw display parsing for hot path visibility.
    Ties: Called by run_profile for display parsing hotspots.
    Inputs: iterations controls the number of repetitions.
    Outputs: None. Runs the parsing loop.
    Side effects: None.
    Why: Captures profiling data on a real display parsing path.
    """
    try:
        text = _sample_display_text()
        for _ in range(iterations):
            _parse_raw_display_rows(text)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_profile_display_parse", "Profiling failed", exc)
        ) from exc


def _profile_usb_parse(iterations: int) -> None:
    """
    Purpose: Profile USB tree parsing for hot path visibility.
    Ties: Called by run_profile for USB parsing hotspots.
    Inputs: iterations controls the number of repetitions.
    Outputs: None. Runs the parsing loop.
    Side effects: None.
    Why: Captures profiling data for USB tree parsing.
    """
    try:
        text = _sample_usb_text()
        for _ in range(iterations):
            _extract_usb_tree_items(text)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_profile_usb_parse", "Profiling failed", exc)) from exc


def _profile_hz_parse(iterations: int) -> None:
    """
    Purpose: Profile refresh rate parsing for hot path visibility.
    Ties: Called by run_profile for regex parsing hotspots.
    Inputs: iterations controls the number of repetitions.
    Outputs: None. Runs the parsing loop.
    Side effects: None.
    Why: Captures profiling data for regex parsing utilities.
    """
    try:
        for _ in range(iterations):
            hz_from_text("Refresh Rate: 60 Hz")
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_profile_hz_parse", "Profiling failed", exc)) from exc


def run_profile(iterations: int) -> cProfile.Profile:
    """
    Purpose: Run profiling across known hot paths and return the profiler.
    Ties: Used by main to collect and output stats.
    Inputs: iterations controls the number of repetitions per target.
    Outputs: cProfile.Profile with collected stats.
    Side effects: Runs profiling instrumentation.
    Why: Centralizes profiling so output stays consistent.
    """
    try:
        profiler = cProfile.Profile()
        profiler.enable()
        _profile_display_parse(iterations)
        _profile_usb_parse(iterations)
        _profile_hz_parse(iterations)
        profiler.disable()
        return profiler
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "run_profile", "Profiling run failed", exc)) from exc


def main() -> int:
    """
    Purpose: CLI entry point for profiling hot paths.
    Ties: Used by Makefile and CI for profiling runs.
    Inputs: None. Uses CLI args for iterations and output path.
    Outputs: Exit code for shell usage.
    Side effects: Writes profiling output and prints stats.
    Why: Provides a repeatable profiling entry point.
    """
    try:
        parser = argparse.ArgumentParser(description="Profile Mac Health Checkup hot paths.")
        parser.add_argument("--iterations", type=int, default=BENCH_ITERATIONS)
        parser.add_argument("--out", type=Path, default=DEFAULT_PROFILE_OUT)
        parser.add_argument("--limit", type=int, default=25)
        args = parser.parse_args()

        profiler = run_profile(args.iterations)
        stats = pstats.Stats(profiler).sort_stats("cumtime")
        stats.dump_stats(str(args.out))
        stats.print_stats(args.limit)
        return 0
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "main", "Profiling CLI failed", exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
