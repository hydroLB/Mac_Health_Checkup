from __future__ import annotations

import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from typing import Callable, Dict

from mac_health_checkup.app.gui.sections.display.parsing import _parse_raw_display_rows
from mac_health_checkup.core.constants import BENCH_ITERATIONS, BENCH_MAX_REGRESSION, BENCH_REPEATS
from mac_health_checkup.core.utils.errors import format_error
from mac_health_checkup.core.utils.regex_utils import hz_from_text
from mac_health_checkup.core.utils.usb_tree import _extract_usb_tree_items

MODULE_PATH = "benchmarks/run.py"
DEFAULT_BASELINE = Path(__file__).resolve().parent / "baseline.json"


def _sample_display_text() -> str:
    """
    Purpose: Provide deterministic sample display text for benchmarking.
    Ties: Used by display parsing benchmarks below.
    Inputs: None.
    Outputs: Raw display text string.
    Side effects: None.
    Why: Ensures benchmarks run without touching system_profiler.
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
    Purpose: Provide deterministic sample USB tree text for benchmarking.
    Ties: Used by USB tree parsing benchmarks below.
    Inputs: None.
    Outputs: Raw USB tree text string.
    Side effects: None.
    Why: Ensures benchmarks do not call system_profiler.
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


def _bench_display_parse() -> None:
    """
    Purpose: Benchmark raw display parsing.
    Ties: Used by benchmark registry.
    Inputs: None.
    Outputs: None. Executes parsing once per iteration.
    Side effects: None.
    Why: Measures a known hot path used in the display section.
    """
    try:
        _parse_raw_display_rows(_sample_display_text())
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_bench_display_parse", "Benchmark failed", exc)
        ) from exc


def _bench_usb_parse() -> None:
    """
    Purpose: Benchmark USB tree parsing.
    Ties: Used by benchmark registry.
    Inputs: None.
    Outputs: None. Executes parsing once per iteration.
    Side effects: None.
    Why: Measures device parsing performance for large USB trees.
    """
    try:
        _extract_usb_tree_items(_sample_usb_text())
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_bench_usb_parse", "Benchmark failed", exc)) from exc


def _bench_hz_parse() -> None:
    """
    Purpose: Benchmark refresh rate parsing from strings.
    Ties: Used by benchmark registry.
    Inputs: None.
    Outputs: None. Executes parsing once per iteration.
    Side effects: None.
    Why: Captures a small but frequently used parsing utility.
    """
    try:
        hz_from_text("Refresh Rate: 60 Hz")
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_bench_hz_parse", "Benchmark failed", exc)) from exc


def _run_benchmark(func: Callable[[], None], iterations: int, repeats: int) -> float:
    """
    Purpose: Run a benchmark function and return operations per second.
    Ties: Used by run_benchmarks to measure each target.
    Inputs: func is the benchmark, iterations count per repeat, repeats controls sampling.
    Outputs: Operations per second as a float.
    Side effects: None.
    Why: Provides stable median-based timing for comparisons.
    """
    try:
        timings = []
        for _ in range(repeats):
            start = time.perf_counter()
            for _ in range(iterations):
                func()
            elapsed = time.perf_counter() - start
            timings.append(elapsed)
        median = statistics.median(timings)
        return iterations / median if median > 0 else float("inf")
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_run_benchmark", "Benchmark timing failed", exc)
        ) from exc


def run_benchmarks(iterations: int, repeats: int) -> Dict[str, float]:
    """
    Purpose: Execute all benchmarks and return ops/sec results.
    Ties: Used by the CLI entry point below.
    Inputs: iterations and repeats control timing stability.
    Outputs: Mapping of benchmark name to ops/sec.
    Side effects: None.
    Why: Centralizes benchmark execution for baseline and comparison.
    """
    try:
        registry: Dict[str, Callable[[], None]] = {
            "display_parse": _bench_display_parse,
            "usb_tree_parse": _bench_usb_parse,
            "hz_parse": _bench_hz_parse,
        }
        results: Dict[str, float] = {}
        for name, func in registry.items():
            results[name] = _run_benchmark(func, iterations, repeats)
        return results
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "run_benchmarks", "Benchmark run failed", exc)) from exc


def _baseline_payload(results: Dict[str, float], iterations: int, repeats: int) -> dict:
    """
    Purpose: Build a baseline payload with metadata and results.
    Ties: Used by update_baseline to write baseline JSON.
    Inputs: results contains ops/sec per benchmark, iterations and repeats are run params.
    Outputs: Dict suitable for JSON serialization.
    Side effects: None.
    Why: Captures environment context with benchmark numbers.
    """
    try:
        return {
            "metadata": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "machine": platform.machine(),
                "iterations": iterations,
                "repeats": repeats,
            },
            "benchmarks": {name: {"ops_per_sec": value} for name, value in results.items()},
        }
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_baseline_payload", "Failed to build payload", exc)
        ) from exc


def update_baseline(path: Path, iterations: int, repeats: int) -> Dict[str, float]:
    """
    Purpose: Run benchmarks and write a baseline JSON file.
    Ties: Used by the CLI --update path.
    Inputs: path is where the baseline is written, iterations and repeats control timing.
    Outputs: Results mapping for quick reporting.
    Side effects: Writes baseline JSON to disk.
    Why: Provides a persisted baseline for regression detection.
    """
    try:
        results = run_benchmarks(iterations, repeats)
        payload = _baseline_payload(results, iterations, repeats)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return results
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_baseline", "Failed to update baseline", exc)
        ) from exc


def compare_to_baseline(
    current: Dict[str, float],
    baseline_path: Path,
    max_regression: float,
) -> int:
    """
    Purpose: Compare current benchmark results to a baseline file.
    Ties: Used by CLI when not updating baselines.
    Inputs: current results, baseline_path, max_regression as a decimal fraction.
    Outputs: Exit code: 0 for pass, 1 for regression or errors.
    Side effects: Reads baseline file from disk.
    Why: Enforces performance guardrails in CI and local runs.
    """
    try:
        if not baseline_path.exists():
            print(f"{MODULE_PATH}:compare_to_baseline baseline missing at {baseline_path}")
            return 1
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
        baseline = payload.get("benchmarks", {})
        failures = 0
        for name, current_ops in current.items():
            base_entry = baseline.get(name)
            if not base_entry or "ops_per_sec" not in base_entry:
                print(f"{MODULE_PATH}:compare_to_baseline missing baseline for {name}")
                failures += 1
                continue
            base_ops = float(base_entry["ops_per_sec"])
            threshold = base_ops * (1.0 - max_regression)
            if current_ops < threshold:
                print(
                    f"{MODULE_PATH}:compare_to_baseline regression for {name}: "
                    f"current {current_ops:.2f} ops/sec < {threshold:.2f} ops/sec"
                )
                failures += 1
        return 0 if failures == 0 else 1
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "compare_to_baseline", "Baseline comparison failed", exc)
        ) from exc


def main() -> int:
    """
    Purpose: CLI entry point for running and comparing benchmarks.
    Ties: Called by __main__ for benchmark execution.
    Inputs: None. Uses CLI args.
    Outputs: Exit code for CI usage.
    Side effects: Reads baseline data and writes to stdout.
    Why: Provides a repeatable interface for performance checks.
    """
    try:
        parser = argparse.ArgumentParser(description="Run Mac Health Checkup benchmarks.")
        parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
        parser.add_argument("--update", action="store_true", help="Write a new baseline JSON file.")
        parser.add_argument("--iterations", type=int, default=BENCH_ITERATIONS)
        parser.add_argument("--repeats", type=int, default=BENCH_REPEATS)
        parser.add_argument("--max-regression", type=float, default=BENCH_MAX_REGRESSION)
        args = parser.parse_args()

        results = run_benchmarks(args.iterations, args.repeats)
        if args.update:
            update_baseline(args.baseline, args.iterations, args.repeats)
            return 0
        return compare_to_baseline(results, args.baseline, args.max_regression)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "main", "Benchmark CLI failed", exc)) from exc


if __name__ == "__main__":
    raise SystemExit(main())
