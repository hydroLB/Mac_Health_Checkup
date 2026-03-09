from __future__ import annotations

import argparse
import cProfile
import pstats
import sys
from pathlib import Path

from mac_health_checkup.app.gui.sections.display.parsing import _parse_raw_display_rows
from mac_health_checkup.core.constants import BENCH_ITERATIONS
from mac_health_checkup.core.utils import format_error, hz_from_text, parse_usb_tree_items

MODULE_PATH = "benchmarks/profile.py"
DEFAULT_PROFILE_OUT = Path(__file__).resolve().parent / "profile.pstats"


def _validate_positive_int(value: int, *, field_name: str) -> int:
    """
    Summary
    Validate that a profiling numeric argument is a positive integer.

    Inputs
    value: Candidate numeric value.
    field_name: Argument label for contextual errors.

    Outputs
    Validated positive integer.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/profile.py:_validate_positive_int` when validation fails.

    Ties to other methods
    Used by `run_profile` and `main`.

    Why this exists
    Profiling should reject invalid loop counts and output limits before doing work.
    """
    try:
        normalized = int(value)
        if normalized <= 0:
            raise ValueError(f"{field_name} must be > 0")
        return normalized
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_validate_positive_int",
                f"Invalid value for `{field_name}`",
                exc,
            )
        ) from exc


def _emit_boundary_error(method: str, message: str, exc: Exception) -> None:
    """
    Summary
    Write a formatted profiling boundary error to stderr.

    Inputs
    method: Boundary method name associated with the failure.
    message: High-level failure context.
    exc: Captured exception instance.

    Outputs
    None.

    Side effects
    Writes one line to stderr.

    Error handling
    Raises contextual errors from `benchmarks/profile.py:_emit_boundary_error` when output formatting fails.

    Ties to other methods
    Used by `main` for script-boundary failures.

    Why this exists
    Keeps profiling failures explicit in CI and local runs without noisy tracebacks.
    """
    try:
        print(format_error(MODULE_PATH, method, message, exc), file=sys.stderr)
    except (RuntimeError, ValueError, TypeError, OSError) as emit_exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_emit_boundary_error",
                "Failed while emitting profiling boundary error",
                emit_exc,
            )
        ) from emit_exc


def _sample_display_text() -> str:
    """
    Summary
    Provide deterministic sample display text for profiling.

    Inputs
    None.

    Outputs
    Raw display text string.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/profile.py:_sample_display_text` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by the display profiling target below.

    Why this exists
    Keeps profiling deterministic and independent of system_profiler.
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
    Summary
    Provide deterministic sample USB tree text for profiling.

    Inputs
    None.

    Outputs
    Raw USB tree text string.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/profile.py:_sample_usb_text` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by the USB profiling target below.

    Why this exists
    Keeps profiling deterministic and independent of system_profiler.
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
    Summary
    Profile raw display parsing for hot path visibility.

    Inputs
    iterations controls the number of repetitions.

    Outputs
    None. Runs the parsing loop.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/profile.py:_profile_display_parse` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Called by run_profile for display parsing hotspots.

    Why this exists
    Captures profiling data on a real display parsing path.
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
    Summary
    Profile USB tree parsing for hot path visibility.

    Inputs
    iterations controls the number of repetitions.

    Outputs
    None. Runs the parsing loop.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/profile.py:_profile_usb_parse` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Called by run_profile for USB parsing hotspots.

    Why this exists
    Captures profiling data for USB tree parsing.
    """
    try:
        text = _sample_usb_text()
        for _ in range(iterations):
            parse_usb_tree_items(text)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_profile_usb_parse", "Profiling failed", exc)) from exc


def _profile_hz_parse(iterations: int) -> None:
    """
    Summary
    Profile refresh rate parsing for hot path visibility.

    Inputs
    iterations controls the number of repetitions.

    Outputs
    None. Runs the parsing loop.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/profile.py:_profile_hz_parse` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Called by run_profile for regex parsing hotspots.

    Why this exists
    Captures profiling data for regex parsing utilities.
    """
    try:
        for _ in range(iterations):
            hz_from_text("Refresh Rate: 60 Hz")
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_profile_hz_parse", "Profiling failed", exc)) from exc


def run_profile(iterations: int) -> cProfile.Profile:
    """
    Summary
    Run profiling across known hot paths and return the profiler.

    Inputs
    iterations controls the number of repetitions per target.

    Outputs
    cProfile.Profile with collected stats.

    Side effects
    Runs profiling instrumentation.

    Error handling
    Raises contextual errors from `benchmarks/profile.py:run_profile` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by main to collect and output stats.

    Why this exists
    Centralizes profiling so output stays consistent.
    """
    try:
        normalized_iterations = _validate_positive_int(iterations, field_name="iterations")
        profiler = cProfile.Profile()
        profiler.enable()
        _profile_display_parse(normalized_iterations)
        _profile_usb_parse(normalized_iterations)
        _profile_hz_parse(normalized_iterations)
        profiler.disable()
        return profiler
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "run_profile", "Profiling run failed", exc)) from exc


def main() -> int:
    """
    Summary
    CLI entry point for profiling hot paths.

    Inputs
    None. Uses CLI args for iterations and output path.

    Outputs
    Exit code for shell usage.

    Side effects
    Writes profiling output and prints stats.

    Error handling
    Returns exit code `2` after emitting a formatted boundary error for runtime failures.

    Ties to other methods
    Used by Makefile and CI for profiling runs.

    Why this exists
    Provides a repeatable profiling entry point.
    """
    try:
        parser = argparse.ArgumentParser(description="Profile Mac Health Checkup hot paths.")
        parser.add_argument("--iterations", type=int, default=BENCH_ITERATIONS)
        parser.add_argument("--out", type=Path, default=DEFAULT_PROFILE_OUT)
        parser.add_argument("--limit", type=int, default=25)
        args = parser.parse_args()

        normalized_iterations = _validate_positive_int(args.iterations, field_name="iterations")
        normalized_limit = _validate_positive_int(args.limit, field_name="limit")
        output_path = args.out.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        profiler = run_profile(normalized_iterations)
        stats = pstats.Stats(profiler).sort_stats("cumtime")
        stats.dump_stats(str(output_path))
        stats.print_stats(normalized_limit)
        return 0
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        _emit_boundary_error("main", "Profiling CLI failed", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
