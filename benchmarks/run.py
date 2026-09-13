from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path
from typing import Callable, Dict

from mac_health_checkup.app.gui.sections.display.parsing import _parse_raw_display_rows
from mac_health_checkup.core.constants import BENCH_ITERATIONS, BENCH_MAX_REGRESSION, BENCH_REPEATS
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error, hz_from_text, parse_usb_tree_items

MODULE_PATH = "benchmarks/run.py"
DEFAULT_BASELINE = Path(__file__).resolve().parent / "baseline.json"


def _validate_positive_int(value: int, *, field_name: str) -> int:
    """
    Summary
    Validate that a CLI numeric argument is a positive integer.

    Inputs
    value: Candidate numeric value.
    field_name: Argument name used in error messages.

    Outputs
    Validated positive integer.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_validate_positive_int` when value validation fails.

    Ties to other methods
    Used by benchmark run/update entrypoints before timing loops.

    Why this exists
    Benchmark loops should fail fast on invalid values instead of producing misleading throughput numbers.
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


def _validate_regression_fraction(value: float) -> float:
    """
    Summary
    Validate the allowed benchmark regression fraction.

    Inputs
    value: Candidate max regression decimal fraction.

    Outputs
    Validated decimal fraction in the inclusive range [0.0, 1.0].

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_validate_regression_fraction` when validation fails.

    Ties to other methods
    Used by baseline comparison and CLI argument handling.

    Why this exists
    Regression thresholds outside [0, 1] make pass/fail logic invalid and hard to reason about.
    """
    try:
        normalized = float(value)
        if normalized < 0.0 or normalized > 1.0:
            raise ValueError("max regression must be in [0.0, 1.0]")
        return normalized
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_validate_regression_fraction",
                "Invalid max regression threshold",
                exc,
            )
        ) from exc


def _emit_boundary_error(method: str, message: str, exc: Exception) -> None:
    """
    Summary
    Write a formatted benchmark boundary error to stderr.

    Inputs
    method: Boundary method name associated with the failure.
    message: High-level failure context.
    exc: Captured exception instance.

    Outputs
    None.

    Side effects
    Writes one line to stderr.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_emit_boundary_error` when output formatting fails.

    Ties to other methods
    Used by `main` for script-boundary failures.

    Why this exists
    CI and local runs need concise actionable failures instead of traceback-heavy boundary output.
    """
    try:
        print(format_error(MODULE_PATH, method, message, exc), file=sys.stderr)
    except (RuntimeError, ValueError, TypeError, OSError) as emit_exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_emit_boundary_error",
                "Failed while emitting benchmark boundary error",
                emit_exc,
            )
        ) from emit_exc


def _sample_display_text() -> str:
    """
    Summary
    Provide deterministic sample display text for benchmarking.

    Inputs
    None.

    Outputs
    Raw display text string.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_sample_display_text` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by display parsing benchmarks below.

    Why this exists
    Ensures benchmarks run without touching system_profiler.
    """
    try:
        return (
            "Graphics/Displays:\n"
            "    Color LCD:\n"
            "      Resolution: 2560 x 1600\n"
            "      Mirror: Off\n"
            "      Connection Type: Internal\n"
            "      Refresh Rate: 60 Hz\n"
            "    DELL U2718Q:\n"
            "      Resolution: 3840 x 2160\n"
            "      Mirror: Off\n"
            "      Connection Type: DisplayPort\n"
            "      Refresh Rate: 60 Hz\n"
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_sample_display_text", "Failed to build sample display text", exc)
        ) from exc


def _sample_usb_text() -> str:
    """
    Summary
    Provide deterministic sample USB tree text for benchmarking.

    Inputs
    None.

    Outputs
    Raw USB tree text string.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_sample_usb_text` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by USB tree parsing benchmarks below.

    Why this exists
    Ensures benchmarks do not call system_profiler.
    """
    try:
        return (
            "    USB:\n"
            "        USB 3.0 Bus:\n"
            "            Vendor Name: Apple Inc.\n"
            "            Magic Trackpad:\n"
            "                Manufacturer: Apple Inc.\n"
            "        USB 2.0 Bus:\n"
            "            USB Keyboard:\n"
            "                Vendor Name: Logitech\n"
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_sample_usb_text", "Failed to build sample USB text", exc)
        ) from exc


def _bench_display_parse() -> None:
    """
    Summary
    Benchmark raw display parsing.

    Inputs
    None.

    Outputs
    None. Executes parsing once per iteration.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_bench_display_parse` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by benchmark registry.

    Why this exists
    Measures a known hot path used in the display section.
    """
    try:
        _parse_raw_display_rows(_sample_display_text())
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_bench_display_parse", "Benchmark failed", exc)
        ) from exc


def _bench_usb_parse() -> None:
    """
    Summary
    Benchmark USB tree parsing.

    Inputs
    None.

    Outputs
    None. Executes parsing once per iteration.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_bench_usb_parse` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by benchmark registry.

    Why this exists
    Measures device parsing performance for large USB trees.
    """
    try:
        parse_usb_tree_items(_sample_usb_text())
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_bench_usb_parse", "Benchmark failed", exc)) from exc


def _bench_hz_parse() -> None:
    """
    Summary
    Benchmark refresh rate parsing from strings.

    Inputs
    None.

    Outputs
    None. Executes parsing once per iteration.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_bench_hz_parse` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by benchmark registry.

    Why this exists
    Captures a small but frequently used parsing utility.
    """
    try:
        hz_from_text("Refresh Rate: 60 Hz")
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_bench_hz_parse", "Benchmark failed", exc)) from exc


def _run_benchmark(func: Callable[[], None], iterations: int, repeats: int) -> float:
    """
    Summary
    Run a benchmark function and return operations per second.

    Inputs
    func is the benchmark, iterations count per repeat, repeats controls sampling.

    Outputs
    Operations per second as a float.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_run_benchmark` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by run_benchmarks to measure each target.

    Why this exists
    Uses the best of several sufficiently long process-CPU samples, matching conventional microbenchmark practice.
    CPU time excludes periods when a shared runner deschedules this process, while a real code regression affects
    every sample.
    """
    try:
        normalized_iterations = _validate_positive_int(iterations, field_name="iterations")
        normalized_repeats = _validate_positive_int(repeats, field_name="repeats")
        timings = []
        for _ in range(normalized_repeats):
            start = time.process_time()
            for _ in range(normalized_iterations):
                func()
            elapsed = time.process_time() - start
            timings.append(elapsed)
        best = min(timings)
        return normalized_iterations / best if best > 0 else float("inf")
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_run_benchmark", "Benchmark timing failed", exc)
        ) from exc


def run_benchmarks(iterations: int, repeats: int) -> Dict[str, float]:
    """
    Summary
    Execute all benchmarks and return ops/sec results.

    Inputs
    iterations and repeats control timing stability.

    Outputs
    Mapping of benchmark name to ops/sec.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:run_benchmarks` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by the CLI entry point below.

    Why this exists
    Centralizes benchmark execution for baseline and comparison, interleaving samples so every target sees similar
    host load.
    """
    try:
        normalized_iterations = _validate_positive_int(iterations, field_name="iterations")
        normalized_repeats = _validate_positive_int(repeats, field_name="repeats")
        registry: Dict[str, Callable[[], None]] = {
            "display_parse": _bench_display_parse,
            "usb_tree_parse": _bench_usb_parse,
            "hz_parse": _bench_hz_parse,
        }
        samples: dict[str, list[float]] = {name: [] for name in registry}
        for _ in range(normalized_repeats):
            for name, func in registry.items():
                samples[name].append(_run_benchmark(func, normalized_iterations, 1))
        return {name: max(throughput_samples) for name, throughput_samples in samples.items()}
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "run_benchmarks", "Benchmark run failed", exc)) from exc


def _baseline_payload(results: Dict[str, float], iterations: int, repeats: int) -> JsonDict:
    """
    Summary
    Build a baseline payload with metadata and results.

    Inputs
    results contains ops/sec per benchmark, iterations and repeats are run params.

    Outputs
    Dict suitable for JSON serialization.

    Side effects
    None.

    Error handling
    Raises contextual errors from `benchmarks/run.py:_baseline_payload` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by update_baseline to write baseline JSON.

    Why this exists
    Captures environment context with benchmark numbers.
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
    Summary
    Run benchmarks and write a baseline JSON file.

    Inputs
    path is where the baseline is written, iterations and repeats control timing.

    Outputs
    Results mapping for quick reporting.

    Side effects
    Writes baseline JSON to disk.

    Error handling
    Raises contextual errors from `benchmarks/run.py:update_baseline` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by the CLI --update path.

    Why this exists
    Provides a persisted baseline for regression detection.
    """
    try:
        normalized_iterations = _validate_positive_int(iterations, field_name="iterations")
        normalized_repeats = _validate_positive_int(repeats, field_name="repeats")
        results = run_benchmarks(normalized_iterations, normalized_repeats)
        payload = _baseline_payload(results, normalized_iterations, normalized_repeats)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return results
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "update_baseline", "Failed to update baseline", exc)
        ) from exc


def compare_to_baseline(
    current: Dict[str, float],
    baseline_path: Path,
    max_regression: float,
) -> int:
    """
    Summary
    Compare current benchmark results to a baseline file.

    Inputs
    Current results, baseline path, and max regression as a decimal fraction.

    Outputs
    Exit code: 0 for pass, 1 for regression or errors.

    Side effects
    Reads baseline file from disk.

    Error handling
    Raises contextual errors from `benchmarks/run.py:compare_to_baseline` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by CLI when not updating baselines.

    Why this exists
    Enforces performance guardrails in CI and local runs.
    """
    try:
        _validate_regression_fraction(max_regression)
        if not current:
            raise ValueError("current benchmark results are empty")
        if not baseline_path.exists():
            print(f"{MODULE_PATH}:compare_to_baseline baseline missing at {baseline_path}", file=sys.stderr)
            return 1
        payload_obj = json.loads(baseline_path.read_text(encoding="utf-8"))
        if not isinstance(payload_obj, dict):
            raise ValueError("baseline root must be a JSON object")
        baseline_obj = payload_obj.get("benchmarks", {})
        if not isinstance(baseline_obj, dict):
            raise ValueError("baseline `benchmarks` must be a JSON object")
        baseline = baseline_obj
        failures = 0
        for name, current_ops in sorted(current.items()):
            base_entry = baseline.get(name)
            if not isinstance(base_entry, dict) or "ops_per_sec" not in base_entry:
                print(f"{MODULE_PATH}:compare_to_baseline missing baseline for {name}", file=sys.stderr)
                failures += 1
                continue
            base_ops = float(base_entry["ops_per_sec"])
            threshold = base_ops * (1.0 - max_regression)
            if current_ops < threshold:
                print(
                    f"{MODULE_PATH}:compare_to_baseline regression for {name}: "
                    f"current {current_ops:.2f} ops/sec < {threshold:.2f} ops/sec",
                    file=sys.stderr,
                )
                failures += 1
        return 0 if failures == 0 else 1
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "compare_to_baseline", "Baseline comparison failed", exc)
        ) from exc


def main() -> int:
    """
    Summary
    CLI entry point for running and comparing benchmarks.

    Inputs
    None. Uses CLI args.

    Outputs
    Exit code for CI usage.

    Side effects
    Reads baseline data and writes to stdout.

    Error handling
    Returns exit code `2` after emitting a formatted boundary error for runtime failures.

    Ties to other methods
    Called by __main__ for benchmark execution.

    Why this exists
    Provides a repeatable interface for performance checks.
    """
    try:
        parser = argparse.ArgumentParser(description="Run Mac Health Checkup benchmarks.")
        parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
        parser.add_argument("--update", action="store_true", help="Write a new baseline JSON file.")
        parser.add_argument("--iterations", type=int, default=BENCH_ITERATIONS)
        parser.add_argument("--repeats", type=int, default=BENCH_REPEATS)
        parser.add_argument("--max-regression", type=float, default=BENCH_MAX_REGRESSION)
        args = parser.parse_args()

        normalized_iterations = _validate_positive_int(args.iterations, field_name="iterations")
        normalized_repeats = _validate_positive_int(args.repeats, field_name="repeats")
        normalized_max_regression = _validate_regression_fraction(args.max_regression)
        baseline_path = args.baseline.resolve()

        if args.update:
            updated = update_baseline(baseline_path, normalized_iterations, normalized_repeats)
            print(f"Updated benchmark baseline: {baseline_path}")
            for name, ops_per_sec in sorted(updated.items()):
                print(f"  {name}: {ops_per_sec:.2f} ops/sec")
            return 0
        results = run_benchmarks(normalized_iterations, normalized_repeats)
        for name, ops_per_sec in sorted(results.items()):
            print(f"{name}: {ops_per_sec:.2f} ops/sec")
        return compare_to_baseline(results, baseline_path, normalized_max_regression)
    except (RuntimeError, ValueError, TypeError, AttributeError, OSError, json.JSONDecodeError) as exc:
        _emit_boundary_error("main", "Benchmark CLI failed", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
