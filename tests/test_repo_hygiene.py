from __future__ import annotations

from tools.audit_repo_hygiene import (
    AuditResult,
    build_failure_message,
    find_disallowed_tracked_paths,
    find_missing_recovery_paths,
)

MODULE_PATH = "tests/test_repo_hygiene.py"


def test_find_disallowed_tracked_paths_rejects_local_and_secret_artifacts() -> None:
    """
    Summary
    Verify tracked local caches and secret-like files are rejected by the hygiene policy.

    Inputs
    None.

    Outputs
    Assertions only.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `find_disallowed_tracked_paths`.

    Why this exists
    Public repository hygiene depends on blocking local state and credential material before push time.
    """
    try:
        paths = (
            ".env.example",
            ".local/tls/agent-key.pem",
            ".codex/environments/environment.toml",
            "swift-ui/.build/debug.yaml",
            "mac_health_checkup/__pycache__/entrypoint.cpython-311.pyc",
        )
        assert find_disallowed_tracked_paths(paths) == (
            ".codex/environments/environment.toml",
            ".local/tls/agent-key.pem",
            "mac_health_checkup/__pycache__/entrypoint.cpython-311.pyc",
            "swift-ui/.build/debug.yaml",
        )
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_find_disallowed_tracked_paths_rejects_local_and_secret_artifacts failed: {exc}"
        ) from exc


def test_find_missing_recovery_paths_requires_bootstrap_contract() -> None:
    """
    Summary
    Verify missing recovery files are reported explicitly.

    Inputs
    None.

    Outputs
    Assertions only.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `find_missing_recovery_paths`.

    Why this exists
    Quick GitHub-only recovery requires deterministic bootstrap artifacts to stay tracked.
    """
    try:
        paths = (
            ".env.example",
            ".gitignore",
            ".pre-commit-config.yaml",
            ".github/workflows/ci.yml",
            "Makefile",
            "README.md",
        )
        assert find_missing_recovery_paths(paths) == (
            "config/config.json",
            "pyproject.toml",
            "requirements-dev.txt",
            "requirements.txt",
            "start",
        )
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_find_missing_recovery_paths_requires_bootstrap_contract failed: {exc}"
        ) from exc


def test_build_failure_message_lists_all_violation_groups() -> None:
    """
    Summary
    Verify audit failure output includes both blocking categories.

    Inputs
    None.

    Outputs
    Assertions on rendered failure text.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `build_failure_message`.

    Why this exists
    Push-time failures must be immediately actionable so cleanup stays fast and consistent.
    """
    try:
        result = AuditResult(
            tracked_disallowed_paths=("swift-ui/.build/.lock",),
            missing_recovery_paths=("requirements.txt",),
        )
        message = build_failure_message(result, staged_only=False)
        assert "swift-ui/.build/.lock" in message
        assert "requirements.txt" in message
        assert "tracked repository contents" in message
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_build_failure_message_lists_all_violation_groups failed: {exc}"
        ) from exc
