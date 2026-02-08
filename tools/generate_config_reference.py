from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, get_args, get_origin

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from mac_health_checkup.core.config.parsing.root import parse_config  # noqa: E402
from mac_health_checkup.core.utils.errors import format_error  # noqa: E402

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
    normalized = [p for p in parts if p]
    if not normalized:
        return "object"
    return " | ".join(normalized)


def _format_type(annotation: Any, fallback_value: object) -> str:
    if annotation is None:
        return type(fallback_value).__name__
    if isinstance(annotation, str):
        return annotation

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in {list, dict, tuple, set}:
        inner = ", ".join(_format_type(arg, object()) for arg in args) if args else ""
        return f"{origin.__name__}[{inner}]" if inner else origin.__name__

    if origin in {types.UnionType, type(None)} or origin is None:
        if isinstance(annotation, types.UnionType):
            return _format_union([_format_type(arg, object()) for arg in args])
        if origin is types.UnionType:
            return _format_union([_format_type(arg, object()) for arg in args])

    if origin is types.UnionType or origin is None and hasattr(annotation, "__args__") and args:
        return _format_union([_format_type(arg, object()) for arg in args])

    if origin is None and dataclasses.is_dataclass(annotation):
        return annotation.__name__

    if origin is None:
        name = getattr(annotation, "__name__", None)
        return str(name) if isinstance(name, str) else str(annotation)

    inner = ", ".join(_format_type(arg, object()) for arg in args) if args else ""
    origin_name = getattr(origin, "__name__", str(origin))
    return f"{origin_name}[{inner}]" if inner else origin_name


def _format_default(value: object) -> str:
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


def _leaf_settings(prefix: str, obj: object, annotation: Any) -> list[LeafSetting]:
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

    return [
        LeafSetting(
            path=prefix,
            type_text=_format_type(annotation, obj),
            default_text=_format_default(obj),
            notes=notes,
        )
    ]


def _render_markdown(config_obj: object, *, source_path: Path) -> str:
    if not dataclasses.is_dataclass(config_obj):
        raise TypeError("expected dataclass config object")

    lines: list[str] = []
    lines.append("# Configuration reference")
    lines.append("")
    lines.append("Generated from the typed config registry and the repo default config file.")
    lines.append("")
    lines.append("## Source of truth")
    lines.append("")
    lines.append(f"- Default config: `{source_path.as_posix()}`")
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


def _read_json_dict(path: Path) -> dict[str, object]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("config root must be object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate configuration reference markdown.")
    parser.add_argument("--config", default="config/config.json", help="Path to the config JSON file.")
    parser.add_argument("--out", default="docs/config_reference.md", help="Path to write markdown output.")
    parser.add_argument("--check", action="store_true", help="Fail if output differs from --out.")
    args = parser.parse_args(argv)

    try:
        config_path = Path(args.config)
        out_path = Path(args.out)
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

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        return 0
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        print(format_error(MODULE_PATH, "main", "Failed to generate config reference", exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
