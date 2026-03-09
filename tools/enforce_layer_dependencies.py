from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

MODULE_PATH = "tools/enforce_layer_dependencies.py"


@dataclass(frozen=True)
class LayerDefinition:
    """
    Summary
    Represent one configured architectural layer.

    Inputs
    name: Stable layer identifier.
    module_prefixes: Dotted module prefixes assigned to this layer.

    Outputs
    Immutable layer definition.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by `LayerRules` and layer matching helpers.

    Why this exists
    Keeps layer mapping typed and explicit.
    """

    name: str
    module_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class LayerRules:
    """
    Summary
    Hold normalized layer-enforcement configuration.

    Inputs
    scan_roots: Files or directories to scan.
    exclude_paths: Relative path fragments excluded from scans.
    layers: Ordered layer definitions.
    allowed_imports: Allowed target layers per source layer.

    Outputs
    Immutable ruleset.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Returned by `load_layer_rules` and used by violation detection.

    Why this exists
    Provides one validated config object for enforcement logic.
    """

    scan_roots: tuple[str, ...]
    exclude_paths: tuple[str, ...]
    layers: tuple[LayerDefinition, ...]
    allowed_imports: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class LayerViolation:
    """
    Summary
    Represent a single layer-direction violation.

    Inputs
    importer_path: Repository-relative importer file path.
    importer_module: Dotted module name of importer.
    importer_layer: Layer assigned to importer.
    imported_module: Dotted module referenced by import statement.
    imported_layer: Layer assigned to imported module.
    line: Source line number of the violating import.

    Outputs
    Immutable violation record.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Produced by `find_layer_violations` and formatted by `_format_violation`.

    Why this exists
    Keeps violation reporting structured and deterministic.
    """

    importer_path: str
    importer_module: str
    importer_layer: str
    imported_module: str
    imported_layer: str
    line: int


def _read_json_object(path: Path) -> dict[str, object]:
    """
    Summary
    Read and validate a JSON object from disk.

    Inputs
    path: Path to a JSON file.

    Outputs
    Parsed dictionary with string keys.

    Side effects
    Reads file bytes from disk.

    Error handling
    Raises `RuntimeError` with module and method context when reading or validation fails.

    Ties to other methods
    Used by `load_layer_rules`.

    Why this exists
    Keeps config file loading strict and reusable.
    """
    try:
        raw = path.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("rules root must be a JSON object")
        out: dict[str, object] = {}
        for key, value in parsed.items():
            if not isinstance(key, str):
                raise ValueError("rules object keys must be strings")
            out[key] = value
        return out
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_read_json_object failed: {exc}") from exc


def _require_str_list(value: object, *, field_name: str) -> tuple[str, ...]:
    """
    Summary
    Validate and normalize a non-empty list of strings from config.

    Inputs
    value: Candidate config value.
    field_name: Field path used in validation errors.

    Outputs
    Tuple of stripped strings.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when validation fails.

    Ties to other methods
    Used by `load_layer_rules`.

    Why this exists
    Config typing must be deterministic and explicit.
    """
    try:
        if not isinstance(value, list):
            raise ValueError(f"{field_name} must be a list")
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"{field_name} items must be strings")
            stripped = item.strip()
            if not stripped:
                raise ValueError(f"{field_name} items must be non-empty strings")
            items.append(stripped)
        if not items:
            raise ValueError(f"{field_name} must not be empty")
        return tuple(items)
    except (ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_require_str_list failed for {field_name}: {exc}") from exc


def load_layer_rules(path: Path) -> LayerRules:
    """
    Summary
    Load and validate layer-enforcement rules from a JSON config file.

    Inputs
    path: Path to rules JSON.

    Outputs
    `LayerRules` object.

    Side effects
    Reads config from disk.

    Error handling
    Raises `RuntimeError` with module and method context when config parsing or validation fails.

    Ties to other methods
    Used by `main` before violation scanning.

    Why this exists
    Keeps rule configuration versioned and committed in-repo.
    """
    try:
        raw = _read_json_object(path)
        scan_roots = _require_str_list(raw.get("scan_roots"), field_name="scan_roots")
        exclude_paths = _require_str_list(raw.get("exclude_paths"), field_name="exclude_paths")

        raw_layers = raw.get("layers")
        if not isinstance(raw_layers, list) or not raw_layers:
            raise ValueError("layers must be a non-empty list")
        layers: list[LayerDefinition] = []
        for index, item in enumerate(raw_layers):
            if not isinstance(item, dict):
                raise ValueError(f"layers[{index}] must be an object")
            name_obj = item.get("name")
            if not isinstance(name_obj, str) or not name_obj.strip():
                raise ValueError(f"layers[{index}].name must be a non-empty string")
            prefixes = _require_str_list(
                item.get("module_prefixes"),
                field_name=f"layers[{index}].module_prefixes",
            )
            layers.append(LayerDefinition(name=name_obj.strip(), module_prefixes=prefixes))
        layer_names = [layer.name for layer in layers]
        if len(set(layer_names)) != len(layer_names):
            raise ValueError("layer names must be unique")

        raw_allowed = raw.get("allowed_imports")
        if not isinstance(raw_allowed, dict):
            raise ValueError("allowed_imports must be an object")
        allowed_imports: dict[str, tuple[str, ...]] = {}
        for layer in layers:
            allowed = _require_str_list(raw_allowed.get(layer.name), field_name=f"allowed_imports.{layer.name}")
            unknown_targets = [name for name in allowed if name not in layer_names]
            if unknown_targets:
                raise ValueError(
                    f"allowed_imports.{layer.name} contains unknown layers: {', '.join(sorted(unknown_targets))}"
                )
            allowed_imports[layer.name] = allowed

        return LayerRules(
            scan_roots=scan_roots,
            exclude_paths=exclude_paths,
            layers=tuple(layers),
            allowed_imports=allowed_imports,
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:load_layer_rules failed: {exc}") from exc


def _resolve_scan_paths(repo_root: Path, scan_roots: Sequence[str]) -> tuple[Path, ...]:
    """
    Summary
    Resolve configured scan roots against repository root.

    Inputs
    repo_root: Repository root path.
    scan_roots: Relative scan roots from config.

    Outputs
    Tuple of absolute existing file/directory paths.

    Side effects
    Reads filesystem metadata.

    Error handling
    Raises `RuntimeError` with module and method context when configured paths are missing.

    Ties to other methods
    Used by `find_layer_violations`.

    Why this exists
    Prevents silent skips when rule config references invalid paths.
    """
    try:
        resolved: list[Path] = []
        for rel_path in scan_roots:
            path = (repo_root / rel_path).resolve()
            if not path.exists():
                raise FileNotFoundError(f"scan root does not exist: {rel_path}")
            resolved.append(path)
        return tuple(resolved)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_resolve_scan_paths failed: {exc}") from exc


def _should_exclude(path: Path, repo_root: Path, exclude_paths: Sequence[str]) -> bool:
    """
    Summary
    Determine whether a path should be excluded from scanning.

    Inputs
    path: Candidate file path.
    repo_root: Repository root.
    exclude_paths: Relative fragments configured for exclusion.

    Outputs
    True when path should be excluded.

    Side effects
    None.

    Error handling
    Returns `False` on relative-path resolution errors.

    Ties to other methods
    Used by `_iter_python_files`.

    Why this exists
    Keeps scan scope deterministic and avoids environment/build artifacts.
    """
    try:
        rel = path.relative_to(repo_root).as_posix()
        return any(fragment in rel for fragment in exclude_paths)
    except ValueError:
        return False


def _iter_python_files(
    repo_root: Path, scan_paths: Sequence[Path], exclude_paths: Sequence[str]
) -> tuple[Path, ...]:
    """
    Summary
    Collect python files from scan roots with exclusion filtering.

    Inputs
    repo_root: Repository root.
    scan_paths: Resolved scan roots.
    exclude_paths: Excluded path fragments.

    Outputs
    Tuple of absolute python file paths.

    Side effects
    Reads filesystem metadata.

    Error handling
    Raises `RuntimeError` with module and method context when scanning fails.

    Ties to other methods
    Used by `find_layer_violations`.

    Why this exists
    Centralizes path traversal for predictable layer checks.
    """
    try:
        files: set[Path] = set()
        for root in scan_paths:
            if root.is_file():
                if root.suffix == ".py" and not _should_exclude(root, repo_root, exclude_paths):
                    files.add(root)
                continue
            for candidate in root.rglob("*.py"):
                if _should_exclude(candidate, repo_root, exclude_paths):
                    continue
                files.add(candidate.resolve())
        return tuple(sorted(files))
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_iter_python_files failed: {exc}") from exc


def _module_from_path(path: Path, repo_root: Path) -> str:
    """
    Summary
    Convert a python file path into its dotted module path.

    Inputs
    path: Absolute python file path.
    repo_root: Repository root.

    Outputs
    Dotted module path (for example `mac_health_checkup.app.entrypoint`).

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when conversion fails.

    Ties to other methods
    Used by `find_layer_violations`.

    Why this exists
    Layer matching is based on module prefixes, not file-system separators.
    """
    try:
        rel = path.relative_to(repo_root)
        if rel.suffix != ".py":
            raise ValueError(f"expected python file path: {rel}")
        parts = list(rel.with_suffix("").parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            raise ValueError(f"cannot derive module name from path: {rel}")
        return ".".join(parts)
    except (ValueError, TypeError, RuntimeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_module_from_path failed for {path}: {exc}") from exc


def _iter_import_targets(path: Path) -> tuple[tuple[int, str], ...]:
    """
    Summary
    Parse a python file and return absolute import targets.

    Inputs
    path: Absolute python file path.

    Outputs
    Tuple of `(line_number, module_path)` import records.

    Side effects
    Reads and parses source text.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by `find_layer_violations`.

    Why this exists
    AST parsing avoids false positives from comments and string literals.
    """
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        imports: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append((int(node.lineno), alias.name))
            elif isinstance(node, ast.ImportFrom):
                if node.level != 0 or node.module is None:
                    continue
                imports.append((int(node.lineno), node.module))
        return tuple(imports)
    except (OSError, SyntaxError, ValueError, TypeError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_iter_import_targets failed for {path}: {exc}") from exc


def _layer_for_module(module_path: str, layers: Sequence[LayerDefinition]) -> str | None:
    """
    Summary
    Resolve the configured layer name for a module path.

    Inputs
    module_path: Dotted module path.
    layers: Ordered layer definitions.

    Outputs
    Layer name when matched, otherwise `None`.

    Side effects
    None.

    Error handling
    Returns `None` when no prefixes match.

    Ties to other methods
    Used by `find_layer_violations`.

    Why this exists
    Enables prefix-based mapping from imports to architecture layers.
    """
    best_match: tuple[int, str] | None = None
    for layer in layers:
        for prefix in layer.module_prefixes:
            if module_path == prefix or module_path.startswith(prefix + "."):
                score = len(prefix)
                if best_match is None or score > best_match[0]:
                    best_match = (score, layer.name)
    return best_match[1] if best_match is not None else None


def find_layer_violations(repo_root: Path, rules: LayerRules) -> tuple[LayerViolation, ...]:
    """
    Summary
    Scan configured sources and return layer-direction violations.

    Inputs
    repo_root: Repository root path.
    rules: Validated layer rules.

    Outputs
    Tuple of layer violations.

    Side effects
    Reads and parses source files under scan roots.

    Error handling
    Raises `RuntimeError` with module and method context when scanning fails.

    Ties to other methods
    Used by `main`.

    Why this exists
    Enforces domain/app/infra dependency direction as a deterministic CI quality gate.
    """
    try:
        scan_paths = _resolve_scan_paths(repo_root, rules.scan_roots)
        python_files = _iter_python_files(repo_root, scan_paths, rules.exclude_paths)
        violations: list[LayerViolation] = []
        for file_path in python_files:
            importer_module = _module_from_path(file_path, repo_root)
            importer_layer = _layer_for_module(importer_module, rules.layers)
            if importer_layer is None:
                continue
            allowed_targets = set(rules.allowed_imports.get(importer_layer, ()))
            for line, imported_module in _iter_import_targets(file_path):
                imported_layer = _layer_for_module(imported_module, rules.layers)
                if imported_layer is None:
                    continue
                if imported_layer in allowed_targets:
                    continue
                violations.append(
                    LayerViolation(
                        importer_path=file_path.relative_to(repo_root).as_posix(),
                        importer_module=importer_module,
                        importer_layer=importer_layer,
                        imported_module=imported_module,
                        imported_layer=imported_layer,
                        line=line,
                    )
                )
        return tuple(sorted(violations, key=lambda item: (item.importer_path, item.line, item.imported_module)))
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(f"{MODULE_PATH}:find_layer_violations failed: {exc}") from exc


def _format_violation(violation: LayerViolation) -> str:
    """
    Summary
    Render one layer violation as a stable human-readable line.

    Inputs
    violation: Violation record.

    Outputs
    Formatted string with path, line, and layer direction details.

    Side effects
    None.

    Error handling
    Never raises for valid violation objects.

    Ties to other methods
    Used by `main` when printing violation reports.

    Why this exists
    Stable formatting keeps local and CI failures easy to triage.
    """
    return (
        f"{violation.importer_path}:{violation.line} "
        f"({violation.importer_layer} -> {violation.imported_layer}) "
        f"{violation.importer_module} imports {violation.imported_module}"
    )


def main(argv: list[str] | None = None) -> int:
    """
    Summary
    Run layer dependency enforcement using committed rules.

    Inputs
    argv: Optional CLI args.

    Outputs
    Process exit code (`0` no violations, `1` violations found, `2` runtime/config errors).

    Side effects
    Reads config and source files, writes findings to stderr.

    Error handling
    Returns exit code `2` with contextual stderr output when rule loading or scanning fails.

    Ties to other methods
    Entrypoint used by `make layers` and `make check`.

    Why this exists
    CI must fail on domain/app/infra dependency-direction violations.
    """
    try:
        parser = argparse.ArgumentParser(description="Enforce domain/app/infra layer dependency direction.")
        parser.add_argument(
            "--config",
            default="tools/layer_rules.json",
            help="Path to layer rules JSON file.",
        )
        parser.add_argument(
            "--repo-root",
            default=".",
            help="Repository root for resolving scan roots.",
        )
        args = parser.parse_args(argv)

        repo_root = Path(str(args.repo_root)).resolve()
        rules = load_layer_rules((repo_root / str(args.config)).resolve())
        violations = find_layer_violations(repo_root, rules)
        if not violations:
            return 0

        print("Layer dependency violations detected:", file=sys.stderr)
        for violation in violations:
            print(f"- {_format_violation(violation)}", file=sys.stderr)
        return 1
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        print(f"{MODULE_PATH}:main failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
