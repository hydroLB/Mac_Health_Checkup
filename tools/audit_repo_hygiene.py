from __future__ import annotations

import argparse
import fnmatch
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MODULE_PATH = "tools/audit_repo_hygiene.py"

DISALLOWED_TRACKED_PATTERNS: tuple[str, ...] = (
    ".DS_Store",
    ".codex/**",
    ".local/**",
    ".venv/**",
    ".venv-*/**",
    "__pycache__/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pyo",
    "**/*.pyd",
    "coverage.xml",
    "htmlcov/**",
    ".coverage",
    ".coverage.*",
    "swift-ui/.build/**",
    "**/.build/**",
    "DerivedData/**",
    "**/*.log",
    ".env",
    ".env.*",
    "**/*.pem",
    "**/*.key",
    "**/*.crt",
    "**/*.cer",
    "**/*.p12",
    "**/*.pfx",
    "**/*.sqlite",
    "**/*.sqlite3",
    "**/*.db",
    "**/*.db-*",
)
ALLOWED_TRACKED_EXACT_PATHS: tuple[str, ...] = (
    ".env.example",
)
RECOVERY_REQUIRED_PATHS: tuple[str, ...] = (
    ".env.example",
    ".gitignore",
    ".pre-commit-config.yaml",
    ".github/workflows/ci.yml",
    "Makefile",
    "README.md",
    "config/config.json",
    "pyproject.toml",
    "requirements-dev.txt",
    "requirements.txt",
    "start",
)


@dataclass(frozen=True)
class AuditResult:
    """
    Summary
    Capture repository hygiene findings in one immutable value.

    Inputs
    tracked_disallowed_paths: Tracked files that should never live in the public repository.
    missing_recovery_paths: Required bootstrap files missing from version control.

    Outputs
    Immutable audit result.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `run_audit` and formatted by `build_failure_message`.

    Why this exists
    Keeps repo-policy evaluation explicit, typed, and easy to test.
    """

    tracked_disallowed_paths: tuple[str, ...]
    missing_recovery_paths: tuple[str, ...]

    @property
    def has_failures(self) -> bool:
        """
        Summary
        Indicate whether the audit found any blocking issues.

        Inputs
        None.

        Outputs
        `bool` showing whether any policy failed.

        Side effects
        None.

        Error handling
        Returns `False` when both finding groups are empty.

        Ties to other methods
        Used by `main` to decide the process exit code.

        Why this exists
        Gives callers one stable success predicate instead of repeating list checks.
        """
        return bool(self.tracked_disallowed_paths or self.missing_recovery_paths)


def git_list_tracked_paths(repo_root: Path, *, staged_only: bool) -> tuple[str, ...]:
    """
    Summary
    Collect repository paths from Git for audit checks.

    Inputs
    repo_root: Absolute repository root.
    staged_only: Whether to scope the check to staged paths only.

    Outputs
    Tuple of repository-relative POSIX paths.

    Side effects
    Executes `git` in the repository.

    Error handling
    Raises `RuntimeError` with module and method context when Git commands fail or return malformed output.

    Ties to other methods
    Used by `run_audit` to enumerate tracked or staged content.

    Why this exists
    Future push hygiene must reflect actual Git state, not raw filesystem noise.
    """
    try:
        command = (
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"]
            if staged_only
            else ["git", "ls-files"]
        )
        completed = subprocess.run(
            command,
            check=True,
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        paths = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
        return tuple(sorted(set(paths)))
    except (subprocess.SubprocessError, OSError, UnicodeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:git_list_tracked_paths failed: {exc}") from exc


def find_disallowed_tracked_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    """
    Summary
    Return tracked paths that violate the repository cleanliness policy.

    Inputs
    paths: Repository-relative tracked paths.

    Outputs
    Tuple of violating paths.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when pattern evaluation fails unexpectedly.

    Ties to other methods
    Used by `run_audit` after Git enumeration.

    Why this exists
    Public recovery repositories should contain only source, config, and deterministic build inputs.
    """
    try:
        violations: list[str] = []
        for path in paths:
            if path in ALLOWED_TRACKED_EXACT_PATHS:
                continue
            if any(fnmatch.fnmatch(path, pattern) for pattern in DISALLOWED_TRACKED_PATTERNS):
                violations.append(path)
        return tuple(sorted(violations))
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:find_disallowed_tracked_paths failed: {exc}") from exc


def find_missing_recovery_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    """
    Summary
    Return required bootstrap paths missing from version control.

    Inputs
    paths: Repository-relative tracked paths.

    Outputs
    Tuple of missing required paths.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when path validation fails unexpectedly.

    Ties to other methods
    Used by `run_audit` to prove GitHub-only recovery stays viable.

    Why this exists
    A clean public repository is only useful if it still contains the files needed to rebuild quickly.
    """
    try:
        tracked = set(paths)
        missing = [path for path in RECOVERY_REQUIRED_PATHS if path not in tracked]
        return tuple(sorted(missing))
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:find_missing_recovery_paths failed: {exc}") from exc


def run_audit(repo_root: Path, *, staged_only: bool) -> AuditResult:
    """
    Summary
    Execute the repository hygiene audit.

    Inputs
    repo_root: Absolute repository root.
    staged_only: Whether to audit only staged paths.

    Outputs
    `AuditResult` describing policy failures.

    Side effects
    Executes Git commands.

    Error handling
    Raises `RuntimeError` with module and method context when the audit cannot be completed.

    Ties to other methods
    Composes `git_list_tracked_paths`, `find_disallowed_tracked_paths`, and `find_missing_recovery_paths`.

    Why this exists
    Centralizes all future push hygiene rules in one deterministic check.
    """
    try:
        tracked_paths = git_list_tracked_paths(repo_root, staged_only=staged_only)
        return AuditResult(
            tracked_disallowed_paths=find_disallowed_tracked_paths(tracked_paths),
            missing_recovery_paths=find_missing_recovery_paths(tracked_paths),
        )
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:run_audit failed: {exc}") from exc


def build_failure_message(result: AuditResult, *, staged_only: bool) -> str:
    """
    Summary
    Format audit failures into one actionable console message.

    Inputs
    result: Completed audit result.
    staged_only: Whether the audit was scoped to staged files only.

    Outputs
    Human-readable message suitable for stderr.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when message assembly fails unexpectedly.

    Ties to other methods
    Used by `main` when returning a non-zero exit code.

    Why this exists
    Fast recovery depends on terse but actionable policy failures at commit and CI time.
    """
    try:
        scope_label = "staged changes" if staged_only else "tracked repository contents"
        lines = [f"Repository hygiene audit failed for {scope_label}."]
        if result.tracked_disallowed_paths:
            lines.append("Tracked paths that must stay out of the public repo:")
            lines.extend(f"  - {path}" for path in result.tracked_disallowed_paths)
        if result.missing_recovery_paths:
            lines.append("Required recovery/bootstrap files missing from version control:")
            lines.extend(f"  - {path}" for path in result.missing_recovery_paths)
        lines.append("Fix the paths above before pushing.")
        return "\n".join(lines)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:build_failure_message failed: {exc}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Summary
    Parse CLI arguments for repository hygiene auditing.

    Inputs
    argv: Optional CLI argument list.

    Outputs
    Parsed `argparse.Namespace`.

    Side effects
    Reads process arguments.

    Error handling
    Raises `RuntimeError` with module and method context when argument parsing fails unexpectedly.

    Ties to other methods
    Used by `main`.

    Why this exists
    Keeps the audit script usable from CI, Make, and pre-commit with one interface.
    """
    try:
        parser = argparse.ArgumentParser(description="Audit tracked repository content for public-repo hygiene.")
        parser.add_argument(
            "--repo-root",
            default=".",
            help="Path to the repository root. Defaults to the current directory.",
        )
        parser.add_argument(
            "--staged-only",
            action="store_true",
            help="Audit only staged tracked paths. Intended for pre-commit usage.",
        )
        return parser.parse_args(argv)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:parse_args failed: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    """
    Summary
    Run the repository hygiene audit as a CLI entrypoint.

    Inputs
    argv: Optional CLI argument list.

    Outputs
    Process exit code.

    Side effects
    Reads Git state and writes audit output to stdout or stderr.

    Error handling
    Returns `2` after writing a contextual error when the audit cannot run.
    Returns `1` when policy failures are found.

    Ties to other methods
    Orchestrates argument parsing, audit execution, and user-facing output.

    Why this exists
    Production-ready public repos need a single non-optional hygiene gate for every future push.
    """
    try:
        args = parse_args(argv)
        repo_root = Path(args.repo_root).resolve()
        result = run_audit(repo_root, staged_only=bool(args.staged_only))
        if result.has_failures:
            print(build_failure_message(result, staged_only=bool(args.staged_only)), file=sys.stderr)
            return 1
        scope_label = "staged changes" if args.staged_only else "tracked repository contents"
        print(f"Repository hygiene audit passed for {scope_label}.")
        return 0
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        print(f"{MODULE_PATH}:main failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
