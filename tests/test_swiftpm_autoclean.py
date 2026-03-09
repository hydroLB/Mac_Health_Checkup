from __future__ import annotations

import pytest

from run_mac_health_checkup_ui import _should_clean_swiftpm_cache

MODULE_PATH = "tests/test_swiftpm_autoclean.py"


def test_should_clean_swiftpm_cache_triggers_on_known_signatures() -> None:
    """
    Summary
    Validate that stale SwiftPM cache signatures trigger an auto-clean decision.

    Inputs
    None.

    Outputs
    Assertions that `_should_clean_swiftpm_cache` returns True for each known trigger substring.

    Side effects
    None.

    Error handling
    Raises AssertionError with a location-tagged message if the function fails to recognize a known trigger.

    Ties to other methods
    Covers `_should_clean_swiftpm_cache` used by `run_mac_health_checkup_ui._run_make_swift_run_with_retry`.

    Why this exists
    The one-command UI launcher should recover from repo moves without requiring users to manually delete caches.
    """
    try:
        assert _should_clean_swiftpm_cache("PCH was compiled with module cache path '/old'") is True
        assert _should_clean_swiftpm_cache("missing required module 'SwiftShims'") is True
        assert _should_clean_swiftpm_cache("error: 'swift-ui': Invalid manifest (...)") is True
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_should_clean_swiftpm_cache_triggers_on_known_signatures failed: {exc}"
        ) from exc


def test_should_clean_swiftpm_cache_returns_false_for_unrelated_output() -> None:
    """
    Summary
    Ensure unrelated failures do not trigger SwiftPM cache cleanup.

    Inputs
    None.

    Outputs
    Assertion that `_should_clean_swiftpm_cache` returns False for output that does not match known signatures.

    Side effects
    None.

    Error handling
    Raises AssertionError with a location-tagged message if the function incorrectly flags unrelated output.

    Ties to other methods
    Covers `_should_clean_swiftpm_cache` in isolation to keep retry behavior narrow and predictable.

    Why this exists
    Aggressive auto-cleaning would slow normal runs; only known stale-cache failures should trigger the recovery path.
    """
    try:
        assert _should_clean_swiftpm_cache("some other error without cache clues") is False
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_should_clean_swiftpm_cache_returns_false_for_unrelated_output failed: {exc}"
        ) from exc


def test_should_clean_swiftpm_cache_rejects_non_string_input() -> None:
    """
    Summary
    Confirm invalid inputs yield a location-tagged RuntimeError rather than silent coercion.

    Inputs
    None.

    Outputs
    Assertion that `_should_clean_swiftpm_cache` raises RuntimeError for non-string inputs.

    Side effects
    None.

    Error handling
    Raises AssertionError with a location-tagged message if the wrong exception type is raised.

    Ties to other methods
    Exercises `_should_clean_swiftpm_cache` argument validation used by the SwiftUI launcher retry logic.

    Why this exists
    Keeping input validation strict prevents brittle retry behavior when call sites change.
    """
    try:
        with pytest.raises(RuntimeError):
            _should_clean_swiftpm_cache(123)  # type: ignore[arg-type]
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_should_clean_swiftpm_cache_rejects_non_string_input failed: {exc}"
        ) from exc
