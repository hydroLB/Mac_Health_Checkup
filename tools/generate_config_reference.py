from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import sys
import tempfile
import types
from dataclasses import dataclass
from pathlib import Path
from typing import TypeGuard, get_args, get_origin

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mac_health_checkup.core.config import parse_config  # noqa: E402
from mac_health_checkup.core.types import JsonDict, JsonValue  # noqa: E402
from mac_health_checkup.core.utils import format_error  # noqa: E402

MODULE_PATH = "tools/generate_config_reference.py"

SECTION_PARSERS: dict[str, str] = {
    "colors": "mac_health_checkup.core.config.parsing.ui.parse_colors",
    "fonts": "mac_health_checkup.core.config.parsing.ui.parse_fonts",
    "ui": "mac_health_checkup.core.config.parsing.ui.parse_ui",
    "logging": "mac_health_checkup.core.config.parsing.observability.parse_logging",
    "retries": "mac_health_checkup.core.config.parsing.runtime.parse_retries",
    "rate_limits": "mac_health_checkup.core.config.parsing.runtime.parse_rate_limits",
    "io": "mac_health_checkup.core.config.parsing.runtime.parse_io",
    "shutdown": "mac_health_checkup.core.config.parsing.runtime.parse_shutdown",
    "benchmarks": "mac_health_checkup.core.config.parsing.runtime.parse_benchmarks",
    "timeouts": "mac_health_checkup.core.config.parsing.runtime.parse_timeouts",
    "api": "mac_health_checkup.core.config.parsing.features.parse_api",
    "fans": "mac_health_checkup.core.config.parsing.features.parse_fans",
    "network": "mac_health_checkup.core.config.parsing.features.parse_network",
    "thresholds": "mac_health_checkup.core.config.parsing.features.parse_thresholds",
    "gui": "mac_health_checkup.core.config.parsing.features.parse_gui",
    "display_transport": "mac_health_checkup.core.config.parsing.features.parse_display_transport",
}

ENV_OVERRIDES: list[tuple[str, str]] = [
    ("MAC_HEALTH_CHECKUP_CONFIG", "Override the config file path."),
    ("MAC_HEALTH_CHECKUP_CONFIG_MAX_BYTES", "Override the config file size limit in bytes."),
    ("MAC_HEALTH_CHECKUP_API_BIND_HOST", "Override `api.bind_host` at runtime (dev/CI)."),
    ("MAC_HEALTH_CHECKUP_API_PORT", "Override `api.port` at runtime (0-65535; `0` picks a free port)."),
]


@dataclass(frozen=True)
class LeafSetting:
    path: str
    type_text: str
    default_text: str
    notes: str


def _extract_summary(doc: str | None) -> str | None:
    """
    Summary
    Execute `_extract_summary` for its module-level responsibility.

    Inputs
    doc: `str | None` parameter from the function signature.

    Outputs
    Returns `str | None`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tools/generate_config_reference.py:_extract_summary` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/generate_config_reference.py`.

    Why this exists
    Keeps `_extract_summary` explicit, testable, and maintainable.
    """
    if not doc:
        return None
    lines = [line.rstrip() for line in doc.splitlines()]
    try:
        idx = lines.index("Summary")
    except ValueError:
        return None
    out: list[str] = []
    for line in lines[idx + 1 :]:
        if not line.strip():
            break
        out.append(line.strip())
    text = " ".join(out).strip()
    return text or None


def _format_union(parts: list[str]) -> str:
    """
    Summary
    Execute `_format_union` for its module-level responsibility.

    Inputs
    parts: `list[str]` parameter from the function signature.

    Outputs
    Returns `str`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tools/generate_config_reference.py:_format_union` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/generate_config_reference.py`.

    Why this exists
    Keeps `_format_union` explicit, testable, and maintainable.
    """
    normalized = [p for p in parts if p]
    if not normalized:
        return "object"
    return " | ".join(normalized)


def _format_type(annotation: object, fallback_value: object) -> str:
    """
    Summary
    Execute `_format_type` for its module-level responsibility.

    Inputs
    annotation: `object` parameter from the function signature.
    fallback_value: `object` parameter from the function signature.

    Outputs
    Returns `str`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tools/generate_config_reference.py:_format_type` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/generate_config_reference.py`.

    Why this exists
    Keeps `_format_type` explicit, testable, and maintainable.
    """
    if annotation is None:
        return type(fallback_value).__name__
    if isinstance(annotation, str):
        return annotation

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in {list, dict, tuple, set}:
        inner = ", ".join(_format_type(arg, object()) for arg in args) if args else ""
        origin_name = getattr(origin, "__name__", str(origin))
        normalized_origin_name = origin_name if isinstance(origin_name, str) else str(origin_name)
        return f"{normalized_origin_name}[{inner}]" if inner else normalized_origin_name

    if origin in {types.UnionType, type(None)} or origin is None:
        if isinstance(annotation, types.UnionType):
            return _format_union([_format_type(arg, object()) for arg in args])
        if origin is types.UnionType:
            return _format_union([_format_type(arg, object()) for arg in args])

    if origin is types.UnionType or origin is None and hasattr(annotation, "__args__") and args:
        return _format_union([_format_type(arg, object()) for arg in args])

    if origin is None and isinstance(annotation, type) and dataclasses.is_dataclass(annotation):
        return annotation.__name__

    if origin is None:
        name = getattr(annotation, "__name__", None)
        return str(name) if isinstance(name, str) else str(annotation)

    inner = ", ".join(_format_type(arg, object()) for arg in args) if args else ""
    origin_name = getattr(origin, "__name__", str(origin))
    return f"{origin_name}[{inner}]" if inner else origin_name


def _format_default(value: object) -> str:
    """
    Summary
    Execute `_format_default` for its module-level responsibility.

    Inputs
    value: `object` parameter from the function signature.

    Outputs
    Returns `str`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tools/generate_config_reference.py:_format_default` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/generate_config_reference.py`.

    Why this exists
    Keeps `_format_default` explicit, testable, and maintainable.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, (list, tuple)):
        if not value:
            return "[]"
        if len(value) <= 6 and all(
            isinstance(item, (str, int, float, bool)) or item is None for item in value
        ):
            return json.dumps(list(value), ensure_ascii=False)
        return f"list[len={len(value)}]"

    if isinstance(value, dict):
        if not value:
            return "{}"
        if (
            len(value) <= 6
            and all(isinstance(k, str) for k in value.keys())
            and all(isinstance(v, (str, int, float, bool)) or v is None for v in value.values())
        ):
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        return f"dict[len={len(value)}]"

    return json.dumps(str(value), ensure_ascii=False)


def _leaf_settings(prefix: str, obj: object, annotation: object) -> list[LeafSetting]:
    """
    Summary
    Execute `_leaf_settings` for its module-level responsibility.

    Inputs
    prefix: `str` parameter from the function signature.
    obj: `object` parameter from the function signature.
    annotation: `object` parameter from the function signature.

    Outputs
    Returns `list[LeafSetting]`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tools/generate_config_reference.py:_leaf_settings` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/generate_config_reference.py`.

    Why this exists
    Keeps `_leaf_settings` explicit, testable, and maintainable.
    """
    if dataclasses.is_dataclass(obj):
        settings: list[LeafSetting] = []
        type_hints = getattr(obj.__class__, "__annotations__", {})
        for field in dataclasses.fields(obj):
            value = getattr(obj, field.name)
            child_annotation = type_hints.get(field.name)
            child_prefix = f"{prefix}.{field.name}" if prefix else field.name
            settings.extend(_leaf_settings(child_prefix, value, child_annotation))
        return settings

    notes = ""
    if prefix == "api.bind_host":
        notes = "Can be overridden by env var MAC_HEALTH_CHECKUP_API_BIND_HOST."
    elif prefix == "api.port":
        notes = "Can be overridden by env var MAC_HEALTH_CHECKUP_API_PORT."
    elif prefix == "network.capacity_test_enabled":
        notes = "Opt-in; runs macOS networkQuality and sends test traffic to external measurement endpoints."
    elif prefix == "network.capacity_test_cache_ttl":
        notes = "Minimum interval between opt-in outbound capacity tests."

    return [
        LeafSetting(
            path=prefix,
            type_text=_format_type(annotation, obj),
            default_text=_format_default(obj),
            notes=notes,
        )
    ]


def _render_markdown(config_obj: object, *, source_path: Path) -> str:
    """
    Summary
    Execute `_render_markdown` for its module-level responsibility.

    Inputs
    config_obj: `object` parameter from the function signature.
    source_path: keyword-only `Path` parameter.

    Outputs
    Returns `str`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tools/generate_config_reference.py:_render_markdown` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/generate_config_reference.py`.

    Why this exists
    Keeps `_render_markdown` explicit, testable, and maintainable.
    """
    if not dataclasses.is_dataclass(config_obj):
        raise TypeError("expected dataclass config object")

    repo_root = Path(__file__).resolve().parent.parent
    try:
        display_source_path = source_path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        display_source_path = source_path.as_posix()

    lines: list[str] = []
    lines.append("# Configuration reference")
    lines.append("")
    lines.append("Generated from the typed config registry and the repo default config file.")
    lines.append("")
    lines.append("## Source of truth")
    lines.append("")
    lines.append(f"- Default config: `{display_source_path}`")
    lines.append("- Typed registry: `mac_health_checkup/core/config/models/`")
    lines.append("- Parsing and validation: `mac_health_checkup/core/config/parsing/`")
    lines.append("")
    lines.append("## Environment overrides")
    lines.append("")
    for name, desc in ENV_OVERRIDES:
        lines.append(f"- `{name}`: {desc}")
    lines.append("")
    lines.append("## Sections")
    lines.append("")
    lines.append(
        "Each section below lists leaf settings as dotted paths, their types, and the default values from the repo config."
    )
    lines.append("")

    type_hints = getattr(config_obj.__class__, "__annotations__", {})
    for field in dataclasses.fields(config_obj):
        section_name = field.name
        section_obj = getattr(config_obj, section_name)
        doc = inspect.getdoc(section_obj.__class__)
        summary = _extract_summary(doc)
        parser_ref = SECTION_PARSERS.get(section_name, "")

        lines.append(f"### `{section_name}`")
        lines.append("")
        if summary:
            lines.append(summary)
            lines.append("")
        if parser_ref:
            lines.append(f"Validated by `{parser_ref}`.")
            lines.append("")

        section_annotation = type_hints.get(section_name)
        settings = _leaf_settings(section_name, section_obj, section_annotation)
        settings.sort(key=lambda item: item.path)

        lines.append("| Key | Type | Default | Notes |")
        lines.append("|---|---|---:|---|")
        for setting in settings:
            key = f"`{setting.path}`"
            type_text = f"`{setting.type_text}`"
            default_text = f"`{setting.default_text}`"
            notes = setting.notes
            lines.append(f"| {key} | {type_text} | {default_text} | {notes} |")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _is_json_value(value: object) -> TypeGuard[JsonValue]:
    """
    Summary
    Determine whether a value conforms to the project `JsonValue` type.

    Inputs
    value: Candidate JSON value.

    Outputs
    `True` when the value is valid JSON according to project typing, otherwise `False`.

    Side effects
    None.

    Error handling
    Returns `False` for unsupported value types.

    Ties to other methods
    Used by `_is_json_dict` to validate parsed config payloads.

    Why this exists
    Keeps runtime JSON validation aligned with static `JsonValue` typing.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return True
    if isinstance(value, list):
        return all(_is_json_value(item) for item in value)
    if isinstance(value, dict):
        return all(isinstance(key, str) and _is_json_value(item) for key, item in value.items())
    return False


def _is_json_dict(value: object) -> TypeGuard[JsonDict]:
    """
    Summary
    Determine whether a value is a JSON object with string keys.

    Inputs
    value: Candidate JSON object.

    Outputs
    `True` when the value conforms to `JsonDict`, otherwise `False`.

    Side effects
    None.

    Error handling
    Returns `False` for invalid object shapes.

    Ties to other methods
    Used by `_read_json_dict` before invoking typed config parsing.

    Why this exists
    Prevents malformed JSON structures from entering the typed config parser.
    """
    return isinstance(value, dict) and all(
        isinstance(key, str) and _is_json_value(item) for key, item in value.items()
    )


def _read_json_dict(path: Path) -> JsonDict:
    """
    Summary
    Execute `_read_json_dict` for its module-level responsibility.

    Inputs
    path: `Path` parameter from the function signature.

    Outputs
    Returns `JsonDict`.

    Side effects
    None beyond this method boundary.

    Error handling
    Raises contextual errors from `tools/generate_config_reference.py:_read_json_dict` when this method encounters invalid state or runtime failures.

    Ties to other methods
    Used by workflows in `tools/generate_config_reference.py`.

    Why this exists
    Keeps `_read_json_dict` explicit, testable, and maintainable.
    """
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not _is_json_dict(data):
        raise ValueError("config root must be object")
    return data


def _validate_cli_paths(config_path: Path, out_path: Path) -> tuple[Path, Path]:
    """
    Summary
    Validate and normalize config-reference CLI paths.

    Inputs
    config_path: Candidate input config path.
    out_path: Candidate markdown output path.

    Outputs
    Tuple of resolved `(config_path, out_path)` values.

    Side effects
    None.

    Error handling
    Raises contextual errors from `tools/generate_config_reference.py:_validate_cli_paths` when validation fails.

    Ties to other methods
    Used by `main` before reading config and writing output.

    Why this exists
    Failing fast on invalid paths keeps CLI usage predictable and failure messages actionable.
    """
    try:
        resolved_config = config_path.resolve()
        resolved_output = out_path.resolve()
        if not resolved_config.is_file():
            raise FileNotFoundError(f"Missing config file: {resolved_config}")
        if resolved_config.suffix.lower() != ".json":
            raise ValueError(f"Config path must be a .json file: {resolved_config}")
        if resolved_output.suffix.lower() != ".md":
            raise ValueError(f"Output path must be a .md file: {resolved_output}")
        return resolved_config, resolved_output
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_validate_cli_paths",
                "Invalid CLI path arguments",
                exc,
            )
        ) from exc


def _write_text_atomic(path: Path, content: str) -> None:
    """
    Summary
    Atomically write UTF-8 text to a target path.

    Inputs
    path: Destination markdown path.
    content: Markdown payload to write.

    Outputs
    None.

    Side effects
    Creates parent directories and writes files on disk.

    Error handling
    Raises contextual errors from `tools/generate_config_reference.py:_write_text_atomic` when writing fails.

    Ties to other methods
    Used by `main` when updating the generated reference file.

    Why this exists
    Atomic writes prevent partially written docs when interrupted by tooling failures.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as tmp_file:
            tmp_file.write(content)
            tmp_file.write("\n" if not content.endswith("\n") else "")
            tmp_path = Path(tmp_file.name)
        tmp_path.replace(path)
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_write_text_atomic",
                f"Failed to write output file: {path}",
                exc,
            )
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
    Used by workflows in `tools/generate_config_reference.py`.

    Why this exists
    Keeps `main` explicit, testable, and maintainable.
    """
    parser = argparse.ArgumentParser(description="Generate configuration reference markdown.")
    parser.add_argument("--config", default="config/config.json", help="Path to the config JSON file.")
    parser.add_argument("--out", default="docs/config_reference.md", help="Path to write markdown output.")
    parser.add_argument("--check", action="store_true", help="Fail if output differs from --out.")
    args = parser.parse_args(argv)

    try:
        config_path, out_path = _validate_cli_paths(Path(args.config), Path(args.out))
        raw = _read_json_dict(config_path)
        cfg = parse_config(raw)
        content = _render_markdown(cfg, source_path=config_path)

        if args.check:
            if not out_path.is_file():
                print(f"Missing expected generated file: {out_path}", file=sys.stderr)
                return 1
            existing = out_path.read_text(encoding="utf-8")
            if existing != content:
                print(f"Config reference is out of date: {out_path}", file=sys.stderr)
                print("Regenerate by running: python tools/generate_config_reference.py", file=sys.stderr)
                return 1
            return 0

        _write_text_atomic(out_path, content)
        return 0
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(format_error(MODULE_PATH, "main", "Failed to generate config reference", exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
