from __future__ import annotations

import argparse
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


@dataclass(frozen=True)
class Finding:
    path: Path
    line: int
    label: str
    text: str


def _iter_python_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file() and root.suffix == ".py":
            files.append(root)
            continue
        if root.is_dir():
            files.extend(sorted(root.rglob("*.py")))
    return files


def _scan_file(path: Path) -> list[Finding]:
    text = path.read_text(encoding="utf-8")
    findings: list[Finding] = []
    for label in DEPRECATED_DOCSTRING_LABELS:
        pattern = re.compile(rf"^\s*{re.escape(label)}\s*", re.MULTILINE)
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            raw_line = text.splitlines()[line - 1] if line - 1 < len(text.splitlines()) else ""
            findings.append(Finding(path=path, line=line, label=label, text=raw_line.rstrip("\n")))
    return sorted(findings, key=lambda f: (str(f.path), f.line, f.label))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check for deprecated docstring label style.")
    parser.add_argument(
        "roots",
        nargs="*",
        default=["mac_health_checkup"],
        help="Paths to scan (directories or .py files). Defaults to mac_health_checkup.",
    )
    args = parser.parse_args(argv)

    roots = [Path(value) for value in args.roots]
    files = _iter_python_files(roots)
    findings: list[Finding] = []
    for file_path in files:
        findings.extend(_scan_file(file_path))

    if not findings:
        return 0

    print("Deprecated docstring label style detected:", file=sys.stderr)
    for finding in findings:
        print(
            f"- {finding.path}:{finding.line} contains {finding.label} ({finding.text.strip()})",
            file=sys.stderr,
        )
    print(
        "Use the standard heading blocks: Summary / Inputs / Outputs / Side effects / Error handling / "
        "Ties to other methods / Why this exists.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
