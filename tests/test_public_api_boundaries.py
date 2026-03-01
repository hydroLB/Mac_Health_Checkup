from __future__ import annotations

import ast
from pathlib import Path

MODULE_PATH = "tests/test_public_api_boundaries.py"

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS: tuple[Path, ...] = (
    REPO_ROOT / "mac_health_checkup",
    REPO_ROOT / "benchmarks",
    REPO_ROOT / "tools",
    REPO_ROOT / "run.py",
    REPO_ROOT / "run_mac_health_checkup.py",
    REPO_ROOT / "run_mac_health_checkup_ui.py",
)


def _iter_python_files() -> list[Path]:
    """
    Summary
    Return production Python files covered by boundary checks.

    Inputs
    None.

    Outputs
    Sorted list of absolute Python file paths.

    Side effects
    Reads filesystem metadata.

    Error handling
    Raises `RuntimeError` with module and method context when scanning fails unexpectedly.

    Ties to other methods
    Used by boundary assertions in this module.

    Why this exists
    Keeps boundary checks deterministic and scoped to production code.
    """
    try:
        files: list[Path] = []
        for root in SCAN_ROOTS:
            if root.is_file():
                files.append(root.resolve())
                continue
            files.extend(sorted(path.resolve() for path in root.rglob("*.py")))
        return sorted(set(files))
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_iter_python_files failed: {exc}") from exc


def _iter_import_modules(path: Path) -> list[tuple[int, str]]:
    """
    Summary
    Parse a file and extract imported module targets with line numbers.

    Inputs
    path: Python source file path.

    Outputs
    List of `(line_number, module_path)` import records.

    Side effects
    Reads source text from disk.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by boundary assertions for backend, config, and utils imports.

    Why this exists
    AST-based parsing avoids false positives from comments or strings.
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        modules: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append((int(node.lineno), alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.level != 0 or not node.module:
                    continue
                modules.append((int(node.lineno), node.module))
        return modules
    except (RuntimeError, ValueError, TypeError, OSError, SyntaxError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_iter_import_modules failed for {path}: {exc}") from exc


def _matches_prefix(module: str, prefix: str) -> bool:
    """
    Summary
    Determine whether an imported module matches a blocked prefix.

    Inputs
    module: Imported module path.
    prefix: Blocked prefix path.

    Outputs
    True when the module equals or is nested under the prefix.

    Side effects
    None.

    Error handling
    Returns false for invalid inputs.

    Ties to other methods
    Used by boundary assertions to classify imports.

    Why this exists
    Keeps prefix matching centralized and consistent.
    """
    try:
        if not module or not prefix:
            return False
        return module == prefix or module.startswith(prefix + ".")
    except (RuntimeError, ValueError, TypeError, AttributeError):
        return False


def _is_within_owner(path: Path, owner_dir: str) -> bool:
    """
    Summary
    Determine whether a file is inside an owning package directory.

    Inputs
    path: Absolute file path.
    owner_dir: Owner directory relative to repository root.

    Outputs
    True when the file is under the owner directory.

    Side effects
    None.

    Error handling
    Returns false for path resolution errors.

    Ties to other methods
    Used by boundary assertions to allow package-internal imports.

    Why this exists
    Boundary rules should apply to cross-package imports, not package-local implementation details.
    """
    try:
        rel = path.relative_to(REPO_ROOT).as_posix()
        normalized = owner_dir.strip("/")
        return rel == normalized or rel.startswith(normalized + "/")
    except (RuntimeError, ValueError):
        return False


def test_backend_imports_use_public_surfaces() -> None:
    """
    Summary
    Ensure code outside backend package does not import backend implementation modules directly.

    Inputs
    None.

    Outputs
    Assertions only.

    Side effects
    Parses repository Python files.

    Error handling
    Raises `AssertionError` with actionable violations.

    Ties to other methods
    Enforces documented boundaries in `docs/public-api-boundaries.md`.

    Why this exists
    Backend internals should remain refactor-safe behind package exports.
    """
    try:
        blocked_prefixes = (
            "mac_health_checkup.app.backend.snapshot",
            "mac_health_checkup.app.backend.server",
            "mac_health_checkup.app.backend.one_click",
            "mac_health_checkup.app.backend.tls",
            "mac_health_checkup.app.backend.http",
            "mac_health_checkup.app.backend.security.auth",
            "mac_health_checkup.app.backend.security.throttling",
            "mac_health_checkup.app.backend.security.validation",
        )
        violations: list[str] = []
        for path in _iter_python_files():
            if _is_within_owner(path, "mac_health_checkup/app/backend"):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            for line, module in _iter_import_modules(path):
                if any(_matches_prefix(module, prefix) for prefix in blocked_prefixes):
                    violations.append(f"{rel}:{line} imports `{module}`")
        assert not violations, "Use `mac_health_checkup.app.backend` public exports:\n" + "\n".join(
            violations
        )
    except (AssertionError, RuntimeError, ValueError, TypeError, OSError) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_backend_imports_use_public_surfaces failed: {exc}") from exc


def test_config_imports_use_public_surfaces() -> None:
    """
    Summary
    Ensure code outside config package uses the config public surface.

    Inputs
    None.

    Outputs
    Assertions only.

    Side effects
    Parses repository Python files.

    Error handling
    Raises `AssertionError` with actionable violations.

    Ties to other methods
    Enforces documented boundaries in `docs/public-api-boundaries.md`.

    Why this exists
    Typed config internals should be hidden behind `mac_health_checkup.core.config`.
    """
    try:
        blocked_prefixes = (
            "mac_health_checkup.core.config.models",
            "mac_health_checkup.core.config.parsing",
            "mac_health_checkup.core.config.validation",
            "mac_health_checkup.core.config.public",
            "mac_health_checkup.core.config.io",
            "mac_health_checkup.core.config.lookup",
        )
        violations: list[str] = []
        for path in _iter_python_files():
            if _is_within_owner(path, "mac_health_checkup/core/config"):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            for line, module in _iter_import_modules(path):
                if any(_matches_prefix(module, prefix) for prefix in blocked_prefixes):
                    violations.append(f"{rel}:{line} imports `{module}`")
        assert not violations, "Use `mac_health_checkup.core.config` public exports:\n" + "\n".join(
            violations
        )
    except (AssertionError, RuntimeError, ValueError, TypeError, OSError) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_config_imports_use_public_surfaces failed: {exc}") from exc


def test_utils_imports_use_public_surfaces() -> None:
    """
    Summary
    Ensure code outside owning layers does not import core utils implementation modules directly.

    Inputs
    None.

    Outputs
    Assertions only.

    Side effects
    Parses repository Python files.

    Error handling
    Raises `AssertionError` with actionable violations.

    Ties to other methods
    Enforces documented boundaries in `docs/public-api-boundaries.md`.

    Why this exists
    Utility internals should remain refactor-safe behind `mac_health_checkup.core.utils`.
    """
    try:
        blocked_prefixes = (
            "mac_health_checkup.core.utils.errors",
            "mac_health_checkup.core.utils.data",
            "mac_health_checkup.core.utils.health",
            "mac_health_checkup.core.utils.loggers",
            "mac_health_checkup.core.utils.qr",
            "mac_health_checkup.core.utils.regex_utils",
            "mac_health_checkup.core.utils.shell",
            "mac_health_checkup.core.utils.text",
            "mac_health_checkup.core.utils.usb_tree",
        )
        owner_exceptions = (
            "mac_health_checkup/core/utils",
            "mac_health_checkup/core/config",
            "mac_health_checkup/core/constants",
        )
        violations: list[str] = []
        for path in _iter_python_files():
            if any(_is_within_owner(path, owner) for owner in owner_exceptions):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            for line, module in _iter_import_modules(path):
                if any(_matches_prefix(module, prefix) for prefix in blocked_prefixes):
                    violations.append(f"{rel}:{line} imports `{module}`")
        assert not violations, "Use `mac_health_checkup.core.utils` public exports:\n" + "\n".join(violations)
    except (AssertionError, RuntimeError, ValueError, TypeError, OSError) as exc:
        raise AssertionError(f"{MODULE_PATH}:test_utils_imports_use_public_surfaces failed: {exc}") from exc
