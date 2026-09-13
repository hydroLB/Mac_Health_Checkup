from __future__ import annotations

from pathlib import Path

import pytest

import tools.audit_repo_hygiene as repo_hygiene
from tools.audit_repo_hygiene import (
    RECOVERY_REQUIRED_PATHS,
    AuditResult,
    build_failure_message,
    find_disallowed_tracked_paths,
    find_missing_recovery_paths,
    find_untracked_shadow_paths,
    run_audit,
)

MODULE_PATH = "tests/test_repo_hygiene.py"


def test_find_disallowed_tracked_paths_rejects_local_secret_and_shadow_artifacts() -> None:
    """
    Summary
    Verify tracked local caches, secret-like files, and Finder-style shadows are rejected by the hygiene policy.

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
    Public repository hygiene depends on blocking local state, credential material, and duplicate shadow paths before
    push time.
    """
    try:
        paths = (
            ".env.example",
            "README.md",
            "README 2.md",
            ".local/tls/agent-key.pem",
            ".codex/environments/environment.toml",
            "swift-ui/.build/debug.yaml",
            "mac_health_checkup/__pycache__/entrypoint.cpython-311.pyc",
        )
        assert find_disallowed_tracked_paths(paths) == (
            ".codex/environments/environment.toml",
            ".local/tls/agent-key.pem",
            "README 2.md",
            "mac_health_checkup/__pycache__/entrypoint.cpython-311.pyc",
            "swift-ui/.build/debug.yaml",
        )
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_find_disallowed_tracked_paths_rejects_local_secret_and_shadow_artifacts failed: {exc}"
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
            ".mac-health-checkup-source",
            "config/config.json",
            "docs/assets/readme/dashboard-preview.svg",
            "mac_health_checkup/resources/__init__.py",
            "mac_health_checkup/resources/default_config.json",
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
    Verify audit failure output includes all blocking categories.

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
            untracked_shadow_paths=("README 2.md",),
        )
        message = build_failure_message(result, staged_only=False)
        assert "swift-ui/.build/.lock" in message
        assert "requirements.txt" in message
        assert "README 2.md" in message
        assert "tracked repository contents" in message
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_build_failure_message_lists_all_violation_groups failed: {exc}"
        ) from exc


def test_find_untracked_shadow_paths_flags_finder_style_duplicates() -> None:
    """
    Summary
    Verify Finder-style shadow copies are reported when they mirror tracked paths.

    Inputs
    None.

    Outputs
    Assertions only.

    Side effects
    None.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `find_untracked_shadow_paths`.

    Why this exists
    Accidental ` 2` duplicates can poison local tests and type checks even though Git does not track them.
    """
    try:
        tracked = (
            "README.md",
            "swift-ui/Sources/MacHealthCheckupApp/AppBootstrap.swift",
            "tests/test_repo_hygiene.py",
        )
        untracked = (
            "README 2.md",
            "swift-ui/Sources 2/MacHealthCheckupApp/AppBootstrap.swift",
            "tests/test_repo_hygiene 2.py",
            "notes/scratch.md",
        )
        assert find_untracked_shadow_paths(tracked, untracked) == (
            "README 2.md",
            "swift-ui/Sources 2/MacHealthCheckupApp/AppBootstrap.swift",
            "tests/test_repo_hygiene 2.py",
        )
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_find_untracked_shadow_paths_flags_finder_style_duplicates failed: {exc}"
        ) from exc


def test_run_audit_staged_only_keeps_repository_checks_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Summary
    Verify a partial staged change does not make repository-wide recovery checks fail.

    Inputs
    monkeypatch: Pytest helper used to provide deterministic Git inventories.

    Outputs
    Assertions only.

    Side effects
    Temporarily replaces Git inventory helpers for this test.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `run_audit` in staged-only mode.

    Why this exists
    Pre-commit must inspect staged additions for disallowed content without treating every unstaged bootstrap file as
    missing or overlooking untracked copies of repository files.
    """
    try:
        repo_root = Path("/tmp/repository")
        inventory_scopes: list[bool] = []
        repository_paths = RECOVERY_REQUIRED_PATHS + (".env",)

        def fake_git_list_tracked_paths(received_root: Path, *, staged_only: bool) -> tuple[str, ...]:
            """
            Summary
            Return deterministic staged or full tracked inventories for the audit.

            Inputs
            received_root: Repository root passed by `run_audit`.
            staged_only: Whether the caller requested the staged inventory.

            Outputs
            Tuple of staged or repository-wide paths.

            Side effects
            Records the requested inventory scope.

            Error handling
            Raises `AssertionError` for an unexpected repository root.

            Ties to other methods
            Replaces `git_list_tracked_paths` in this focused test.

            Why this exists
            The test must distinguish staged policy input from repository-wide recovery input.
            """
            assert received_root == repo_root
            inventory_scopes.append(staged_only)
            return (".env",) if staged_only else repository_paths

        def fake_git_list_untracked_paths(received_root: Path) -> tuple[str, ...]:
            """
            Summary
            Return a deterministic untracked shadow-file inventory for the audit.

            Inputs
            received_root: Repository root passed by `run_audit`.

            Outputs
            Tuple containing one Finder-style shadow path.

            Side effects
            None.

            Error handling
            Raises `AssertionError` for an unexpected repository root.

            Ties to other methods
            Replaces `git_list_untracked_paths` in this focused test.

            Why this exists
            Repository-wide shadow detection must remain active in staged mode.
            """
            assert received_root == repo_root
            return ("README 2.md",)

        monkeypatch.setattr(repo_hygiene, "git_list_tracked_paths", fake_git_list_tracked_paths)
        monkeypatch.setattr(repo_hygiene, "git_list_untracked_paths", fake_git_list_untracked_paths)

        assert run_audit(repo_root, staged_only=True) == AuditResult(
            tracked_disallowed_paths=(".env",),
            missing_recovery_paths=(),
            untracked_shadow_paths=("README 2.md",),
        )
        assert inventory_scopes == [True, False]
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_run_audit_staged_only_keeps_repository_checks_global failed: {exc}"
        ) from exc


def test_run_audit_staged_only_rejects_staged_shadow_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Summary
    Verify the staged-only hook rejects a staged Finder-style copy after Git stops reporting it as untracked.

    Inputs
    monkeypatch: Pytest helper used to provide deterministic staged and full-index inventories.

    Outputs
    Assertion that the staged shadow path is reported as tracked disallowed content.

    Side effects
    Temporarily replaces Git inventory helpers for this test.

    Error handling
    Raises `AssertionError` with module and test context when the staged policy regresses.

    Ties to other methods
    Exercises `run_audit` in the same staged-only mode used by `.githooks/pre-commit`.

    Why this exists
    `git ls-files --others` omits a file as soon as it is staged, so the hook must compare staged candidates against
    the canonical paths in the full index.
    """
    try:
        repo_root = Path("/tmp/repository")
        shadow_path = "tests/test_repo_hygiene 2.py"
        repository_paths = RECOVERY_REQUIRED_PATHS + (
            "tests/test_repo_hygiene.py",
            shadow_path,
        )
        monkeypatch.setattr(
            repo_hygiene,
            "git_list_tracked_paths",
            lambda received_root, *, staged_only: (shadow_path,) if staged_only else repository_paths,
        )
        monkeypatch.setattr(repo_hygiene, "git_list_untracked_paths", lambda received_root: ())

        result = run_audit(repo_root, staged_only=True)

        assert result.tracked_disallowed_paths == (shadow_path,)
        assert result.untracked_shadow_paths == ()
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_run_audit_staged_only_rejects_staged_shadow_path failed: {exc}"
        ) from exc


def test_run_audit_staged_only_reports_required_file_removed_from_index(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Summary
    Verify staged mode still reports a required recovery file removed from the Git index.

    Inputs
    monkeypatch: Pytest helper used to provide deterministic Git inventories.

    Outputs
    Assertions only.

    Side effects
    Temporarily replaces Git inventory helpers for this test.

    Error handling
    Raises `AssertionError` with module and test context when expectations are not met.

    Ties to other methods
    Exercises `run_audit` in staged-only mode.

    Why this exists
    Using the full index for recovery checks must fix partial commits without allowing deletion of a required file.
    """
    try:
        repo_root = Path("/tmp/repository")
        repository_paths = tuple(path for path in RECOVERY_REQUIRED_PATHS if path != "README.md")

        def fake_git_list_tracked_paths(received_root: Path, *, staged_only: bool) -> tuple[str, ...]:
            """
            Summary
            Return a full tracked inventory that omits one required recovery file.

            Inputs
            received_root: Repository root passed by `run_audit`.
            staged_only: Whether the caller requested the staged inventory.

            Outputs
            Empty staged inventory or repository inventory without `README.md`.

            Side effects
            None.

            Error handling
            Raises `AssertionError` for an unexpected repository root.

            Ties to other methods
            Replaces `git_list_tracked_paths` in the required-file deletion test.

            Why this exists
            The regression test must model a required path removed from the Git index.
            """
            assert received_root == repo_root
            return () if staged_only else repository_paths

        def fake_git_list_untracked_paths(received_root: Path) -> tuple[str, ...]:
            """
            Summary
            Return an empty untracked inventory for the required-file deletion case.

            Inputs
            received_root: Repository root passed by `run_audit`.

            Outputs
            Empty tuple.

            Side effects
            None.

            Error handling
            Raises `AssertionError` for an unexpected repository root.

            Ties to other methods
            Replaces `git_list_untracked_paths` in this focused test.

            Why this exists
            Untracked files are irrelevant to the required-path deletion scenario.
            """
            assert received_root == repo_root
            return ()

        monkeypatch.setattr(repo_hygiene, "git_list_tracked_paths", fake_git_list_tracked_paths)
        monkeypatch.setattr(repo_hygiene, "git_list_untracked_paths", fake_git_list_untracked_paths)

        assert run_audit(repo_root, staged_only=True).missing_recovery_paths == ("README.md",)
    except (AssertionError, RuntimeError, ValueError, TypeError) as exc:
        raise AssertionError(
            f"{MODULE_PATH}:test_run_audit_staged_only_reports_required_file_removed_from_index failed: {exc}"
        ) from exc
