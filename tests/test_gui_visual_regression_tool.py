from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

MODULE_PATH = "tests/test_gui_visual_regression_tool.py"
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "tools" / "gui_visual_regression.py"


def _run_visual_tool(args: list[str]) -> subprocess.CompletedProcess[str]:
    """
    Summary
    Execute the visual regression CLI with a deterministic repository-local environment.

    Inputs
    args: CLI arguments passed after the script path.

    Outputs
    Completed subprocess result with stdout and stderr.

    Side effects
    Runs a child Python process and writes files as directed by args.

    Error handling
    Does not raise on non-zero exit; callers assert result.returncode explicitly.

    Ties to other methods
    Used by visual regression workflow tests in this module.

    Why this exists
    End-to-end subprocess coverage validates the same CLI path used in local and CI gates.
    """
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{existing}" if existing else str(REPO_ROOT)
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _read_manifest(path: Path) -> dict[str, object]:
    """
    Summary
    Read a visual regression JSON manifest and assert it decodes to an object.

    Inputs
    path: Manifest file path.

    Outputs
    Decoded manifest dictionary.

    Side effects
    Reads JSON bytes from disk.

    Error handling
    Raises `ValueError` when the JSON root is not an object.

    Ties to other methods
    Used by both tests to validate capture and diff outputs.

    Why this exists
    Keeps manifest parsing and runtime type checks centralized.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{MODULE_PATH}:_read_manifest expected JSON object root")
    return cast(dict[str, object], raw)


def _flip_first_pixel(path: Path) -> None:
    """
    Summary
    Mutate the first pixel byte in a binary PPM image to simulate visual drift.

    Inputs
    path: PPM image path.

    Outputs
    None.

    Side effects
    Rewrites the target image with one changed channel value.

    Error handling
    Raises `ValueError` when the image header is malformed.

    Ties to other methods
    Used by drift detection tests before invoking diff mode.

    Why this exists
    Produces a deterministic single-pixel delta without depending on GUI runtime behavior.
    """
    raw = path.read_bytes()
    first_newline = raw.find(b"\n")
    second_newline = raw.find(b"\n", first_newline + 1)
    third_newline = raw.find(b"\n", second_newline + 1)
    if first_newline < 0 or second_newline < 0 or third_newline < 0:
        raise ValueError(f"{MODULE_PATH}:_flip_first_pixel malformed PPM header in {path}")
    start = third_newline + 1
    if start >= len(raw):
        raise ValueError(f"{MODULE_PATH}:_flip_first_pixel missing pixel payload in {path}")
    mutated = bytearray(raw)
    mutated[start] = (mutated[start] + 31) % 256
    path.write_bytes(bytes(mutated))


def _scene_names(payload: dict[str, object]) -> set[str]:
    """
    Summary
    Extract scene names from a manifest payload.

    Inputs
    payload: Manifest object.

    Outputs
    Set of scene names.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the scene list is missing or not a list.

    Ties to other methods
    Used by scene coverage assertions in capture and diff tests.

    Why this exists
    Keeps manifest shape assertions explicit and reusable.
    """
    scenes_obj = payload.get("scenes")
    if not isinstance(scenes_obj, list):
        raise ValueError(f"{MODULE_PATH}:_scene_names manifest scenes must be a list")
    return {str(item) for item in scenes_obj}


def _as_int(value: object, field_name: str) -> int:
    """
    Summary
    Convert a manifest scalar value into an integer with explicit type validation.

    Inputs
    value: Input scalar from manifest payload.
    field_name: Field label used in error messages.

    Outputs
    Parsed integer value.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the value cannot be converted to an integer.

    Ties to other methods
    Used by test assertions that validate manifest counters.

    Why this exists
    Keeps strict type checking and failure messages clear in tests.
    """
    if not isinstance(value, (int, float, str)):
        raise ValueError(f"{MODULE_PATH}:_as_int field `{field_name}` has unsupported type")
    return int(value)


def _as_float(value: object, field_name: str) -> float:
    """
    Summary
    Convert a manifest scalar value into a float with explicit type validation.

    Inputs
    value: Input scalar from manifest payload.
    field_name: Field label used in error messages.

    Outputs
    Parsed float value.

    Side effects
    None.

    Error handling
    Raises `ValueError` when the value cannot be converted to a float.

    Ties to other methods
    Used by test assertions that validate manifest ratio fields.

    Why this exists
    Avoids weak typing when reading JSON values under strict mypy settings.
    """
    if not isinstance(value, (int, float, str)):
        raise ValueError(f"{MODULE_PATH}:_as_float field `{field_name}` has unsupported type")
    return float(value)


def test_visual_capture_and_diff_have_expected_key_states(tmp_path: Path) -> None:
    """
    Summary
    Verify capture and diff CLI workflows generate deterministic outputs for all key GUI states.

    Inputs
    tmp_path: Temporary directory fixture.

    Outputs
    None.

    Side effects
    Writes capture and diff artifacts to a temp directory.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises CLI `capture` and `diff` modes in `tools/gui_visual_regression.py`.

    Why this exists
    Baseline workflows must remain stable so visual drift checks are trustworthy.
    """
    try:
        before_dir = tmp_path / "before"
        after_dir = tmp_path / "after"
        diff_dir = tmp_path / "diff"

        capture_before = _run_visual_tool(["capture", "--output-dir", str(before_dir)])
        assert capture_before.returncode == 0, capture_before.stderr

        capture_after = _run_visual_tool(["capture", "--output-dir", str(after_dir)])
        assert capture_after.returncode == 0, capture_after.stderr

        diff = _run_visual_tool(
            [
                "diff",
                "--before-dir",
                str(before_dir),
                "--after-dir",
                str(after_dir),
                "--diff-dir",
                str(diff_dir),
                "--fail-on-change",
            ]
        )
        assert diff.returncode == 0, diff.stderr

        manifest = _read_manifest(diff_dir / "manifest.json")
        expected_states = {
            "resize_small",
            "resize_medium",
            "resize_large",
            "focus_first_card",
            "focus_third_card",
            "scroll_vertical_top",
            "scroll_vertical_mid",
            "scroll_horizontal_overflow",
            "refresh_error_injected",
            "refresh_recovered",
        }
        assert _scene_names(manifest) == expected_states
        assert _as_int(manifest.get("changed_scene_count"), "changed_scene_count") == 0
        assert _as_int(manifest.get("changed_pixels"), "changed_pixels") == 0
        assert _as_int(manifest.get("total_pixels"), "total_pixels") > 0
        assert _as_float(manifest.get("changed_ratio"), "changed_ratio") == pytest.approx(0.0, abs=1e-12)
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_visual_capture_and_diff_have_expected_key_states failed: {exc}"
        ) from exc


def test_visual_diff_fails_when_pixel_drift_is_injected(tmp_path: Path) -> None:
    """
    Summary
    Ensure diff mode fails with `--fail-on-change` when even a single pixel changes.

    Inputs
    tmp_path: Temporary directory fixture.

    Outputs
    None.

    Side effects
    Writes and mutates temporary PPM capture files.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises pixel comparison and failure gating in CLI `diff` mode.

    Why this exists
    Visual regression checks must reliably detect and gate unintended UI drift.
    """
    try:
        before_dir = tmp_path / "before"
        after_dir = tmp_path / "after"
        diff_dir = tmp_path / "diff"

        capture_before = _run_visual_tool(["capture", "--output-dir", str(before_dir)])
        assert capture_before.returncode == 0, capture_before.stderr

        capture_after = _run_visual_tool(["capture", "--output-dir", str(after_dir)])
        assert capture_after.returncode == 0, capture_after.stderr

        _flip_first_pixel(after_dir / "resize_small.ppm")

        diff = _run_visual_tool(
            [
                "diff",
                "--before-dir",
                str(before_dir),
                "--after-dir",
                str(after_dir),
                "--diff-dir",
                str(diff_dir),
                "--fail-on-change",
            ]
        )
        assert diff.returncode == 1, diff.stderr

        manifest = _read_manifest(diff_dir / "manifest.json")
        assert _as_int(manifest.get("changed_scene_count"), "changed_scene_count") >= 1
        results_obj = manifest.get("results")
        assert isinstance(results_obj, list)

        resize_small = next(
            (
                item
                for item in results_obj
                if isinstance(item, dict) and str(item.get("scene", "")) == "resize_small"
            ),
            None,
        )
        assert isinstance(resize_small, dict)
        assert _as_int(resize_small.get("changed_pixels"), "resize_small.changed_pixels") > 0
        assert _as_float(resize_small.get("changed_ratio"), "resize_small.changed_ratio") > 0.0
    except Exception as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_visual_diff_fails_when_pixel_drift_is_injected failed: {exc}"
        ) from exc
