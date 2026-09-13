from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

MODULE_PATH = "tools/check_detect_secrets_baseline.py"
FindingKey = tuple[str, str, str]


def load_json(path: Path | None) -> dict[str, object]:
    """
    Summary
    Load a detect-secrets JSON document from a file or stdin.

    Inputs
    path: Optional path to read. `None` means read stdin.

    Outputs
    Parsed JSON object.

    Side effects
    Reads from the filesystem or stdin.

    Error handling
    Raises `RuntimeError` with path context when parsing fails.

    Ties to other methods
    Used by `main` before normalizing baseline and current scan findings.

    Why this exists
    Keeping IO separate from comparison logic makes the security gate easier to test and review.
    """
    try:
        raw = path.read_text(encoding="utf-8") if path is not None else sys.stdin.read()
        loaded: object = json.loads(raw)
        if not isinstance(loaded, dict):
            raise TypeError("detect-secrets JSON root must be an object")
        return loaded
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        source = str(path) if path is not None else "stdin"
        raise RuntimeError(f"{MODULE_PATH}:load_json failed for {source}: {exc}") from exc


def finding_keys(document: dict[str, object]) -> set[FindingKey]:
    """
    Summary
    Normalize detect-secrets findings into stable comparison keys.

    Inputs
    document: Parsed detect-secrets JSON object.

    Outputs
    Set of `(filename, type, hashed_secret)` tuples.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` when the findings shape is invalid.

    Ties to other methods
    Used by `find_new_findings` and `main`.

    Why this exists
    Line numbers and generated timestamps can change during refactors; secret identity should drive the gate.
    """
    try:
        results = document.get("results", {})
        if not isinstance(results, dict):
            raise TypeError("detect-secrets results must be an object")
        keys: set[FindingKey] = set()
        for filename, findings in results.items():
            if not isinstance(filename, str) or not isinstance(findings, list):
                raise TypeError("detect-secrets result entries must map filenames to finding lists")
            for finding in findings:
                if not isinstance(finding, dict):
                    raise TypeError("detect-secrets finding must be an object")
                secret_type = finding.get("type")
                hashed_secret = finding.get("hashed_secret")
                if not isinstance(secret_type, str) or not isinstance(hashed_secret, str):
                    raise TypeError("detect-secrets finding is missing type or hashed_secret")
                keys.add((filename, secret_type, hashed_secret))
        return keys
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:finding_keys failed: {exc}") from exc


def find_new_findings(baseline: dict[str, object], current: dict[str, object]) -> tuple[FindingKey, ...]:
    """
    Summary
    Return findings present in the current scan but absent from the committed baseline.

    Inputs
    baseline: Parsed committed baseline JSON.
    current: Parsed current scan JSON.

    Outputs
    Sorted tuple of new finding keys.

    Side effects
    None.

    Error handling
    Raises contextual errors from `finding_keys`.

    Ties to other methods
    Used by `main` to decide the process exit code.

    Why this exists
    The security check should be read-only and should fail only when new secret material appears.
    """
    try:
        return tuple(sorted(finding_keys(current) - finding_keys(baseline)))
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:find_new_findings failed: {exc}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Summary
    Parse command-line arguments for the detect-secrets baseline checker.

    Inputs
    argv: Optional argument list.

    Outputs
    Parsed argparse namespace.

    Side effects
    Reads process arguments when `argv` is `None`.

    Error handling
    Raises `RuntimeError` when argument parsing fails unexpectedly.

    Ties to other methods
    Used by `main`.

    Why this exists
    A small CLI keeps the Makefile readable and avoids shell-specific JSON comparison.
    """
    try:
        parser = argparse.ArgumentParser(
            description="Fail when detect-secrets reports findings outside the baseline."
        )
        parser.add_argument(
            "--baseline", required=True, help="Path to the committed detect-secrets baseline."
        )
        return parser.parse_args(argv)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:parse_args failed: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    """
    Summary
    Compare current detect-secrets scan output against a committed baseline.

    Inputs
    argv: Optional command-line arguments.

    Outputs
    Process exit code.

    Side effects
    Reads the baseline file and current scan JSON from stdin; writes findings to stderr.

    Error handling
    Returns `2` for malformed inputs and `1` when new findings are present.

    Ties to other methods
    Orchestrates `parse_args`, `load_json`, and `find_new_findings`.

    Why this exists
    CI and local checks need a non-mutating secret scan that works in dirty worktrees.
    """
    try:
        args = parse_args(argv)
        new_findings = find_new_findings(load_json(Path(args.baseline)), load_json(None))
        if new_findings:
            print("New detect-secrets findings are not present in the committed baseline:", file=sys.stderr)
            for filename, secret_type, hashed_secret in new_findings:
                print(f"  - {filename}: {secret_type} ({hashed_secret})", file=sys.stderr)
            return 1
        print("detect-secrets scan matched the committed baseline.")
        return 0
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        print(f"{MODULE_PATH}:main failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
