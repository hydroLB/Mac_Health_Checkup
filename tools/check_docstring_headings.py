from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path

DEPRECATED_DOCSTRING_LABELS: tuple[str, ...] = (
    "Purpose:",
    "Ties:",
    "Inputs:",
    "Outputs:",
    "Side effects:",
    "Why:",
)
REQUIRED_DOCSTRING_HEADINGS: tuple[str, ...] = (
    "Summary",
    "Inputs",
    "Outputs",
    "Side effects",
    "Error handling",
    "Ties to other methods",
    "Why this exists",
)
MODULE_PATH = "tools/check_docstring_headings.py"


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    kind: str
    text: str


def _iter_python_files(roots: list[Path]) -> list[Path]:
    """
    Summary
    Execute `_iter_python_files` for its module-level responsibility.

    Inputs
    roots: `list[Path]` parameter from the function signature.

    Outputs
    Returns `list[Path]`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tools/check_docstring_headings.py:_iter_python_files` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/check_docstring_headings.py`.

    Why this exists
    Keeps `_iter_python_files` explicit, testable, and maintainable.
    """
    try:
        files: list[Path] = []
        for root in roots:
            if not root.exists():
                raise FileNotFoundError(f"Path does not exist: {root}")
            if root.is_file() and root.suffix == ".py":
                files.append(root)
                continue
            if root.is_dir():
                files.extend(sorted(root.rglob("*.py")))
        unique_files = sorted(set(files))
        return unique_files
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            f"{MODULE_PATH}:_iter_python_files failed: {exc}"
        ) from exc


def _scan_file(path: Path) -> list[Finding]:
    """
    Summary
    Execute `_scan_file` for its module-level responsibility.

    Inputs
    path: `Path` parameter from the function signature.

    Outputs
    Returns `list[Finding]`.

    Side effects
    None beyond this method boundary.

    Error handling
    Returns a `read_error` finding when file IO or parsing prep fails.

    Ties to other methods
    Used by workflows in `tools/check_docstring_headings.py`.

    Why this exists
    Keeps `_scan_file` explicit, testable, and maintainable.
    """
    try:
        text = path.read_text(encoding="utf-8")
        findings: list[Finding] = []
        findings.extend(_scan_deprecated_labels(path, text))
        findings.extend(_scan_function_docstrings(path, text))
        return sorted(findings, key=lambda f: (str(f.path), f.line, f.kind))
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        return [
            Finding(
                path=path,
                line=1,
                kind="read_error",
                text=f"{MODULE_PATH}:_scan_file failed: {exc}",
            )
        ]


def _scan_deprecated_labels(path: Path, text: str) -> list[Finding]:
    """
    Summary
    Find deprecated docstring label formats in a file.

    Inputs
    path: `Path` parameter from the function signature.
    text: `str` parameter from the function signature.

    Outputs
    Returns `list[Finding]`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tools/check_docstring_headings.py:_scan_deprecated_labels` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/check_docstring_headings.py`.

    Why this exists
    Keeps `_scan_deprecated_labels` explicit, testable, and maintainable.
    """
    try:
        findings: list[Finding] = []
        lines = text.splitlines()
        for label in DEPRECATED_DOCSTRING_LABELS:
            pattern = re.compile(rf"^\s*{re.escape(label)}\s*", re.MULTILINE)
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                raw_line = lines[line - 1] if line - 1 < len(lines) else ""
                findings.append(
                    Finding(path=path, line=line, kind="deprecated_label", text=f"{label} ({raw_line.strip()})")
                )
        return findings
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            f"{MODULE_PATH}:_scan_deprecated_labels failed for {path}: {exc}"
        ) from exc


def _scan_function_docstrings(path: Path, text: str) -> list[Finding]:
    """
    Summary
    Validate that every function docstring includes required headings in order.

    Inputs
    path: `Path` parameter from the function signature.
    text: `str` parameter from the function signature.

    Outputs
    Returns `list[Finding]`.

    Side effects
    Parses source text into an AST.

    Error handling
    Raises contextual errors from `tools/check_docstring_headings.py:_scan_function_docstrings` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/check_docstring_headings.py`.

    Why this exists
    Keeps `_scan_function_docstrings` explicit, testable, and maintainable.
    """
    try:
        findings: list[Finding] = []
        try:
            module = ast.parse(text)
        except SyntaxError as exc:
            line = exc.lineno if isinstance(exc.lineno, int) else 1
            return [
                Finding(
                    path=path,
                    line=line,
                    kind="syntax_error",
                    text=f"{MODULE_PATH}:_scan_function_docstrings could not parse file: {exc}",
                )
            ]
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            doc = ast.get_docstring(node)
            if not doc:
                findings.append(
                    Finding(
                        path=path,
                        line=int(node.lineno),
                        kind="missing_docstring",
                        text=f"Function `{node.name}` is missing a docstring.",
                    )
                )
                continue
            doc_lines = [line.rstrip() for line in doc.splitlines()]
            positions: list[int] = []
            missing_heading: str | None = None
            for heading in REQUIRED_DOCSTRING_HEADINGS:
                try:
                    positions.append(doc_lines.index(heading))
                except ValueError:
                    missing_heading = heading
                    break
            if missing_heading is not None:
                findings.append(
                    Finding(
                        path=path,
                        line=int(node.lineno),
                        kind="missing_heading",
                        text=f"Function `{node.name}` is missing heading `{missing_heading}`.",
                    )
                )
                continue
            if positions != sorted(positions):
                findings.append(
                    Finding(
                        path=path,
                        line=int(node.lineno),
                        kind="heading_order",
                        text=f"Function `{node.name}` has headings out of order.",
                    )
                )
        return findings
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            f"{MODULE_PATH}:_scan_function_docstrings failed for {path}: {exc}"
        ) from exc


def main(argv: list[str] | None = None) -> int:
    """
    Summary
    Execute `main` for its module-level responsibility.

    Inputs
    argv: `list[str] | None` parameter from the function signature with a default.

    Outputs
    Returns `int`.

    Side effects
    None beyond this method boundary.

    Error handling
    Returns exit code `2` with a contextual stderr message when runtime failures occur.

    Ties to other methods
    Used by workflows in `tools/check_docstring_headings.py`.

    Why this exists
    Keeps `main` explicit, testable, and maintainable.
    """
    try:
        parser = argparse.ArgumentParser(description="Check for deprecated docstring label style.")
        parser.add_argument(
            "roots",
            nargs="*",
            default=[
                "mac_health_checkup",
                "tests",
                "tools",
                "benchmarks",
                "run.py",
                "run_mac_health_checkup.py",
                "run_mac_health_checkup_ui.py",
            ],
            help="Paths to scan (directories or .py files). Defaults to full Python codebase roots.",
        )
        args = parser.parse_args(argv)

        roots = [Path(value) for value in args.roots]
        files = _iter_python_files(roots)
        findings: list[Finding] = []
        for file_path in files:
            findings.extend(_scan_file(file_path))

        if not findings:
            return 0

        print("Docstring standards violations detected:", file=sys.stderr)
        for finding in findings:
            print(
                f"- {finding.path}:{finding.line} [{finding.kind}] {finding.text.strip()}",
                file=sys.stderr,
            )
        print(
            "Use the standard heading blocks: Summary / Inputs / Outputs / Side effects / Error handling / "
            "Ties to other methods / Why this exists.",
            file=sys.stderr,
        )
        return 1
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        print(f"{MODULE_PATH}:main failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
