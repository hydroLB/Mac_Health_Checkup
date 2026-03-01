from __future__ import annotations

import argparse

import pytest

import mac_health_checkup.app.entrypoint as entrypoint
import run
from mac_health_checkup.core.utils.error_boundary import ErrorBoundary, ErrorCode, map_boundary_exception

MODULE_PATH = "tests/test_error_boundary_model.py"


def test_map_boundary_exception_classifies_config_errors() -> None:
    """
    Summary
    Ensure config-related failures map to the shared `config_invalid` taxonomy code.

    Inputs
    None.

    Outputs
    Assertions on mapped boundary code and exit status.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and method context on failures.

    Ties to other methods
    Exercises `map_boundary_exception` classification logic.

    Why this exists
    Deterministic config failure mapping is required for consistent boundary behavior and CI assertions.
    """
    try:
        mapped = map_boundary_exception(
            RuntimeError("MAC_HEALTH_CHECKUP_CONFIG is set but empty"),
            boundary=ErrorBoundary.CLI,
            default_message="startup failed",
        )
        assert mapped.code is ErrorCode.CONFIG_INVALID
        assert mapped.exit_code == 1
        assert mapped.user_message == "Invalid runtime configuration."
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_map_boundary_exception_classifies_config_errors failed: {exc}"
        ) from exc


def test_map_boundary_exception_classifies_input_errors() -> None:
    """
    Summary
    Ensure input-validation failures map to `input_invalid` with bad-request semantics.

    Inputs
    None.

    Outputs
    Assertions on mapped code and HTTP status.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and method context on failures.

    Ties to other methods
    Exercises `map_boundary_exception` classification logic.

    Why this exists
    API boundaries require stable 400-series mapping for malformed inputs.
    """
    try:
        mapped = map_boundary_exception(
            ValueError("missing section key"),
            boundary=ErrorBoundary.API,
            default_message="request failed",
        )
        assert mapped.code is ErrorCode.INPUT_INVALID
        assert mapped.http_status == 400
        assert mapped.user_message == "Invalid input."
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_map_boundary_exception_classifies_input_errors failed: {exc}"
        ) from exc


def test_run_main_emits_standardized_boundary_error(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure the top-level CLI runner prints standardized code-tagged boundary errors.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    capsys: Pytest capture fixture.

    Outputs
    Assertions on exit code and stderr output.

    Side effects
    Patches `run._parse_args` to force a deterministic boundary failure.

    Error handling
    Raises `AssertionError` with module and method context on failures.

    Ties to other methods
    Exercises `run.main` and `run._emit_boundary_error`.

    Why this exists
    Script boundaries should provide stable error-code prefixes for operators and automated tooling.
    """
    try:
        monkeypatch.setattr(run, "_parse_args", lambda: (_ for _ in ()).throw(RuntimeError("bad config")))
        code = run.main()
        err = capsys.readouterr().err
        assert code == 2
        assert "[cli:config_invalid]" in err
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_run_main_emits_standardized_boundary_error failed: {exc}"
        ) from exc


def test_entrypoint_main_maps_ui_boundary_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    Summary
    Ensure UI-mode entrypoint failures are tagged with UI boundary metadata.

    Inputs
    monkeypatch: Pytest monkeypatch fixture.
    capsys: Pytest capture fixture.

    Outputs
    Assertions on exit code and stderr output.

    Side effects
    Patches argument parsing and config loading to trigger deterministic startup failure.

    Error handling
    Raises `AssertionError` with module and method context on failures.

    Ties to other methods
    Exercises `entrypoint.main` top-level boundary mapping.

    Why this exists
    UI boundary failures should be distinguishable from CLI/API failures in logs and diagnostics.
    """
    try:
        args = argparse.Namespace(
            serve=False,
            cli=False,
            snapshot_json=False,
            snapshot_json_out=None,
            export=None,
            diff_snapshots=None,
        )
        monkeypatch.setattr(entrypoint, "_parse_args", lambda: args)
        monkeypatch.setattr(entrypoint, "get_config", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
        code = entrypoint.main()
        err = capsys.readouterr().err
        assert code == 1
        assert "[ui:internal_error]" in err
    except (
        AssertionError,
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_entrypoint_main_maps_ui_boundary_errors failed: {exc}"
        ) from exc
