from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from mac_health_checkup.core.utils import format_error

MODULE_PATH = "tools/gui_visual_regression.py"
_DIMMED_PIXEL_TABLE = bytes(int(channel * 0.45) for channel in range(256))


@dataclass(frozen=True)
class RgbColor:
    """
    Summary
    Hold an RGB color tuple using 8-bit channels.

    Inputs
    red: Red channel in [0, 255].
    green: Green channel in [0, 255].
    blue: Blue channel in [0, 255].

    Outputs
    Immutable RGB color value.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by rendering and diff helpers.

    Why this exists
    Keeps color handling typed and explicit across the renderer.
    """

    red: int
    green: int
    blue: int


@dataclass(frozen=True)
class ThemeColors:
    """
    Summary
    Hold the subset of GUI colors used by visual baseline rendering.

    Inputs
    bg: Window background color.
    fg: Primary foreground color.
    section: Accent color.
    label: Secondary text color.
    field: Body text color.
    ok: Success status color.
    warn: Warning status color.
    bad: Error status color.
    card_bg: Card background color.
    card_border: Card border color.

    Outputs
    Immutable theme color set.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Loaded from config and consumed by scene rendering.

    Why this exists
    Keeps the visual baseline aligned with the app theme source of truth.
    """

    bg: RgbColor
    fg: RgbColor
    section: RgbColor
    label: RgbColor
    field: RgbColor
    ok: RgbColor
    warn: RgbColor
    bad: RgbColor
    card_bg: RgbColor
    card_border: RgbColor


@dataclass(frozen=True)
class SceneDefinition:
    """
    Summary
    Describe a deterministic GUI state to render as a visual baseline scene.

    Inputs
    name: Stable scene identifier.
    width: Canvas width in pixels.
    height: Canvas height in pixels.
    status_level: Header status role (loading, info, warn).
    focus_card: Optional card index rendered in keyboard focus state.
    scroll_y: Vertical content scroll offset in pixels.
    horizontal_scroll_px: Horizontal scroll thumb offset in pixels for overflow table states.
    show_error: Whether to render a section error state.
    show_empty: Whether to render empty table/metrics placeholders.

    Outputs
    Immutable scene definition.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by capture and diff workflows.

    Why this exists
    Visual regression checks need stable, named states that map to UX-critical flows.
    """

    name: str
    width: int
    height: int
    status_level: str
    focus_card: int | None
    scroll_y: int
    horizontal_scroll_px: int
    show_error: bool
    show_empty: bool


class PpmImage:
    """
    Summary
    Provide a tiny no-dependency pixel buffer and PPM encoder/decoder.

    Inputs
    width: Image width in pixels.
    height: Image height in pixels.
    bg: Background color.

    Outputs
    Mutable in-memory image buffer.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context for invalid sizes or IO failures.

    Ties to other methods
    Used by rendering, writing captures, and computing diff images.

    Why this exists
    Keeps visual regression tooling dependency-free while still producing image artifacts.
    """

    def __init__(self, width: int, height: int, bg: RgbColor) -> None:
        """
        Summary
        Initialize the image buffer with a solid background color.

        Inputs
        width: Width in pixels.
        height: Height in pixels.
        bg: Background color.

        Outputs
        None.

        Side effects
        Allocates an internal byte buffer.

        Error handling
        Raises `RuntimeError` with module and method context when size validation fails.

        Ties to other methods
        Constructed by scene rendering and diff creation.

        Why this exists
        Rendering requires a mutable buffer to draw deterministic shapes.
        """
        try:
            if width <= 0 or height <= 0:
                raise ValueError("width and height must be positive")
            self.width = int(width)
            self.height = int(height)
            self._data = bytearray(self.width * self.height * 3)
            self.fill_rect(0, 0, self.width, self.height, bg)
        except (RuntimeError, ValueError, TypeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "PpmImage.__init__", "Failed to initialize image", exc)
            ) from exc

    def fill_rect(self, x: int, y: int, w: int, h: int, color: RgbColor) -> None:
        """
        Summary
        Draw a filled rectangle clipped to image bounds.

        Inputs
        x: Left position.
        y: Top position.
        w: Width in pixels.
        h: Height in pixels.
        color: Fill color.

        Outputs
        None.

        Side effects
        Mutates the image pixel buffer.

        Error handling
        Raises `RuntimeError` with module and method context when drawing fails.

        Ties to other methods
        Used by all scene drawing primitives.

        Why this exists
        Simple block primitives are enough for deterministic layout regression snapshots.
        """
        try:
            if w <= 0 or h <= 0:
                return
            raw_x = int(x)
            raw_y = int(y)
            x0 = max(0, raw_x)
            y0 = max(0, raw_y)
            x1 = min(self.width, raw_x + int(w))
            y1 = min(self.height, raw_y + int(h))
            if x0 >= x1 or y0 >= y1:
                return
            r = max(0, min(255, int(color.red)))
            g = max(0, min(255, int(color.green)))
            b = max(0, min(255, int(color.blue)))
            row = bytes((r, g, b)) * (x1 - x0)
            row_bytes = self.width * 3
            for yy in range(y0, y1):
                start = (yy * row_bytes) + (x0 * 3)
                self._data[start : start + len(row)] = row
        except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "PpmImage.fill_rect", "Failed to draw rectangle", exc)
            ) from exc

    def write(self, path: Path) -> None:
        """
        Summary
        Serialize the image as binary PPM (P6).

        Inputs
        path: Destination file path.

        Outputs
        None.

        Side effects
        Writes bytes to disk and creates parent directories as needed.

        Error handling
        Raises `RuntimeError` with module and method context when file writing fails.

        Ties to other methods
        Used by capture and diff workflows.

        Why this exists
        PPM output avoids external imaging dependencies.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            header = f"P6\n{self.width} {self.height}\n255\n".encode("ascii")
            path.write_bytes(header + bytes(self._data))
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "PpmImage.write", f"Failed to write {path}", exc)
            ) from exc

    @classmethod
    def read(cls, path: Path) -> "PpmImage":
        """
        Summary
        Load a binary PPM (P6) image from disk.

        Inputs
        path: Source PPM path.

        Outputs
        `PpmImage` instance containing loaded pixels.

        Side effects
        Reads bytes from disk.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails.

        Ties to other methods
        Used by diff computation.

        Why this exists
        Visual diffs need to compare captured before/after image bytes deterministically.
        """
        try:
            raw = path.read_bytes()
            if not raw.startswith(b"P6\n"):
                raise ValueError(f"Unsupported PPM header in {path}")
            parts = raw.split(b"\n", 3)
            if len(parts) < 4:
                raise ValueError(f"Malformed PPM file {path}")
            size_line = parts[1].decode("ascii").strip()
            max_line = parts[2].decode("ascii").strip()
            if max_line != "255":
                raise ValueError(f"Unsupported max channel value {max_line} in {path}")
            width_str, height_str = size_line.split(" ", 1)
            width = int(width_str)
            height = int(height_str)
            pixel_data = parts[3]
            expected = width * height * 3
            if len(pixel_data) != expected:
                raise ValueError(f"Expected {expected} bytes, found {len(pixel_data)} in {path}")
            image = cls(width, height, RgbColor(0, 0, 0))
            image._data[:] = pixel_data
            return image
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "PpmImage.read", f"Failed to read {path}", exc)
            ) from exc


def _hex_to_rgb(value: str) -> RgbColor:
    """
    Summary
    Parse a hex color string into RGB channels.

    Inputs
    value: Hex string such as `#58a6ff`.

    Outputs
    Parsed `RgbColor`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails.

    Ties to other methods
    Used by config and scene rendering helpers.

    Why this exists
    Config stores color values as hex strings.
    """
    try:
        text = str(value).strip().lstrip("#")
        if len(text) != 6:
            raise ValueError(f"Expected 6-digit hex color, got {value!r}")
        return RgbColor(
            int(text[0:2], 16),
            int(text[2:4], 16),
            int(text[4:6], 16),
        )
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_hex_to_rgb", "Failed to parse hex color", exc)
        ) from exc


def _mix(a: RgbColor, b: RgbColor, ratio: float) -> RgbColor:
    """
    Summary
    Mix two RGB colors by a fixed ratio.

    Inputs
    a: First color.
    b: Second color.
    ratio: Mix amount in [0.0, 1.0].

    Outputs
    Mixed `RgbColor`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when math fails.

    Ties to other methods
    Used to derive muted visual bars from theme tokens.

    Why this exists
    The renderer uses a small consistent set of derived shades.
    """
    try:
        r = max(0.0, min(1.0, float(ratio)))
        inv = 1.0 - r
        return RgbColor(
            int((a.red * inv) + (b.red * r)),
            int((a.green * inv) + (b.green * r)),
            int((a.blue * inv) + (b.blue * r)),
        )
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_mix", "Failed to mix colors", exc)) from exc


def _load_theme(config_path: Path) -> ThemeColors:
    """
    Summary
    Load theme colors from the project config file.

    Inputs
    config_path: Path to `config/config.json`.

    Outputs
    Parsed `ThemeColors`.

    Side effects
    Reads JSON file from disk.

    Error handling
    Raises `RuntimeError` with module and method context when config loading fails.

    Ties to other methods
    Used by capture and diff workflows.

    Why this exists
    Visual baseline scenes should track the live configured theme.
    """
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        colors = raw["colors"]
        gui = raw["gui"]
        return ThemeColors(
            bg=_hex_to_rgb(colors["bg"]),
            fg=_hex_to_rgb(colors["fg"]),
            section=_hex_to_rgb(colors["section"]),
            label=_hex_to_rgb(colors["label"]),
            field=_hex_to_rgb(colors["field"]),
            ok=_hex_to_rgb(colors["ok"]),
            warn=_hex_to_rgb(colors["warn"]),
            bad=_hex_to_rgb(colors["bad"]),
            card_bg=_hex_to_rgb(gui["card_bg"]),
            card_border=_hex_to_rgb(gui["card_border"]),
        )
    except (RuntimeError, ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_load_theme", "Failed to load theme", exc)) from exc


def _key_scenes() -> list[SceneDefinition]:
    """
    Summary
    Return the canonical set of key GUI states for visual regression tracking.

    Inputs
    None.

    Outputs
    Ordered scene list.

    Side effects
    None.

    Error handling
    None.

    Ties to other methods
    Used by capture workflow.

    Why this exists
    Key states map directly to resize, keyboard, scrolling, and refresh error/recovery flows.
    """
    return [
        SceneDefinition("resize_small", 760, 860, "info", None, 0, 0, False, False),
        SceneDefinition("resize_medium", 980, 860, "info", None, 0, 0, False, False),
        SceneDefinition("resize_large", 1220, 860, "info", None, 0, 0, False, False),
        SceneDefinition("focus_first_card", 980, 860, "info", 0, 0, 0, False, False),
        SceneDefinition("focus_third_card", 980, 860, "info", 2, 0, 0, False, False),
        SceneDefinition("scroll_vertical_top", 980, 860, "info", None, 0, 0, False, False),
        SceneDefinition("scroll_vertical_mid", 980, 860, "info", None, 180, 0, False, False),
        SceneDefinition("scroll_horizontal_overflow", 980, 860, "info", None, 0, 120, False, False),
        SceneDefinition("refresh_error_injected", 980, 860, "warn", None, 0, 0, True, True),
        SceneDefinition("refresh_recovered", 980, 860, "info", None, 0, 0, False, False),
    ]


def _status_color(level: str, theme: ThemeColors) -> RgbColor:
    """
    Summary
    Map a status level to the corresponding theme color.

    Inputs
    level: Status level text.
    theme: Theme colors.

    Outputs
    Status color.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when mapping fails.

    Ties to other methods
    Used by scene rendering.

    Why this exists
    Header status color is a key visual signal in refresh lifecycle states.
    """
    try:
        normalized = (level or "").strip().lower()
        if normalized == "loading":
            return theme.section
        if normalized == "warn":
            return theme.warn
        if normalized == "error":
            return theme.bad
        return theme.label
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_status_color", "Failed to map status color", exc)
        ) from exc


def _draw_bar(image: PpmImage, x: int, y: int, w: int, h: int, color: RgbColor) -> None:
    """
    Summary
    Draw a single soft rectangular text-bar primitive.

    Inputs
    image: Target image.
    x: Left coordinate.
    y: Top coordinate.
    w: Width.
    h: Height.
    color: Fill color.

    Outputs
    None.

    Side effects
    Mutates the image buffer.

    Error handling
    Raises `RuntimeError` with module and method context when drawing fails.

    Ties to other methods
    Used by `_render_scene` for all pseudo-text content.

    Why this exists
    Deterministic bars represent content blocks without depending on fonts.
    """
    try:
        image.fill_rect(x, y, w, h, color)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_draw_bar", "Failed to draw bar", exc)) from exc


def _render_scene(scene: SceneDefinition, theme: ThemeColors) -> PpmImage:
    """
    Summary
    Render one deterministic visual baseline scene into a PPM image.

    Inputs
    scene: Scene definition.
    theme: Theme colors.

    Outputs
    Rendered `PpmImage`.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails.

    Ties to other methods
    Used by capture workflow.

    Why this exists
    Visual regression requires stable scene rendering independent of runtime GUI availability.
    """
    try:
        image = PpmImage(scene.width, scene.height, theme.bg)

        header_h = 80
        outer_pad_x = 18
        image.fill_rect(0, 0, scene.width, header_h, _mix(theme.bg, theme.fg, 0.03))
        _draw_bar(image, outer_pad_x, 20, 300, 18, theme.fg)
        _draw_bar(image, outer_pad_x, 48, 420, 10, _status_color(scene.status_level, theme))
        image.fill_rect(outer_pad_x, header_h - 1, scene.width - (outer_pad_x * 2), 1, theme.card_border)

        viewport_x = outer_pad_x
        viewport_y = header_h + 12
        viewport_w = scene.width - (outer_pad_x * 2)
        viewport_h = scene.height - viewport_y - 12

        card_h = 120
        card_gap = 12
        card_count = 8
        total_content_h = (card_count * card_h) + ((card_count - 1) * card_gap)
        y_offset = max(0, scene.scroll_y)

        title_color = _mix(theme.section, theme.fg, 0.15)
        subtitle_color = _mix(theme.label, theme.fg, 0.12)
        field_color = _mix(theme.field, theme.fg, 0.08)

        for index in range(card_count):
            top = viewport_y + (index * (card_h + card_gap)) - y_offset
            if top > (viewport_y + viewport_h) or (top + card_h) < viewport_y:
                continue
            border_color = theme.card_border
            border_thickness = 1
            if scene.focus_card is not None and index == scene.focus_card:
                border_color = theme.section
                border_thickness = 2

            image.fill_rect(viewport_x, top, viewport_w, card_h, border_color)
            image.fill_rect(
                viewport_x + border_thickness,
                top + border_thickness,
                viewport_w - (border_thickness * 2),
                card_h - (border_thickness * 2),
                theme.card_bg,
            )

            inner_x = viewport_x + 14
            inner_y = top + 14
            _draw_bar(image, inner_x, inner_y, 170, 10, title_color)
            _draw_bar(image, inner_x, inner_y + 18, 220, 8, subtitle_color)

            if scene.show_error and index == 2:
                _draw_bar(image, inner_x, inner_y + 38, 320, 9, theme.bad)
            elif scene.show_empty and index in {3, 4}:
                _draw_bar(image, inner_x, inner_y + 38, 160, 8, subtitle_color)
            else:
                _draw_bar(image, inner_x, inner_y + 38, 360, 9, field_color)

            if index in {4, 5}:
                table_x = inner_x
                table_y = inner_y + 56
                table_w = viewport_w - 44
                table_h = 40
                image.fill_rect(table_x, table_y, table_w, table_h, _mix(theme.card_bg, theme.field, 0.06))
                _draw_bar(image, table_x + 8, table_y + 8, min(table_w - 16, 420), 6, subtitle_color)
                _draw_bar(image, table_x + 8, table_y + 20, min(table_w - 16, 520), 6, field_color)
                if scene.horizontal_scroll_px > 0 and index == 5:
                    track_y = table_y + table_h - 8
                    image.fill_rect(
                        table_x + 6, track_y, table_w - 12, 4, _mix(theme.card_border, theme.bg, 0.4)
                    )
                    thumb_w = max(40, int((table_w - 12) * 0.35))
                    thumb_x = table_x + 6 + min(scene.horizontal_scroll_px, max(0, (table_w - 12) - thumb_w))
                    image.fill_rect(thumb_x, track_y, thumb_w, 4, theme.section)

        track_x = viewport_x + viewport_w - 8
        image.fill_rect(track_x, viewport_y, 4, viewport_h, _mix(theme.card_border, theme.bg, 0.45))
        if total_content_h > viewport_h:
            thumb_h = max(24, int(viewport_h * (viewport_h / total_content_h)))
            max_scroll = max(1, total_content_h - viewport_h)
            scroll_ratio = min(1.0, y_offset / max_scroll)
            thumb_y = viewport_y + int((viewport_h - thumb_h) * scroll_ratio)
        else:
            thumb_h = viewport_h
            thumb_y = viewport_y
        image.fill_rect(track_x, thumb_y, 4, thumb_h, theme.section)

        return image
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_render_scene", "Failed to render scene", exc)) from exc


def _capture_scenes(output_dir: Path, theme: ThemeColors) -> list[Path]:
    """
    Summary
    Render all key scenes and write them as PPM files to the output directory.

    Inputs
    output_dir: Directory receiving rendered scene files.
    theme: Theme colors.

    Outputs
    List of written image paths.

    Side effects
    Creates output directories and writes image files.

    Error handling
    Raises `RuntimeError` with module and method context when capture fails.

    Ties to other methods
    Called by CLI capture mode.

    Why this exists
    Baseline and candidate captures must be generated using the same deterministic scene set.
    """
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for scene in _key_scenes():
            image = _render_scene(scene, theme)
            path = output_dir / f"{scene.name}.ppm"
            image.write(path)
            written.append(path)
        return written
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_capture_scenes", "Failed to capture scenes", exc)
        ) from exc


def _iter_common_scene_names(before_dir: Path, after_dir: Path) -> list[str]:
    """
    Summary
    Return sorted scene names that exist in both capture directories.

    Inputs
    before_dir: Before-capture directory.
    after_dir: After-capture directory.

    Outputs
    Sorted shared scene names without file extension.

    Side effects
    Reads directory listings.

    Error handling
    Raises `RuntimeError` with module and method context when listing fails.

    Ties to other methods
    Used by diff workflow.

    Why this exists
    Visual diff should only compare scene pairs that exist in both runs.
    """
    try:
        before = {path.stem for path in before_dir.glob("*.ppm")}
        after = {path.stem for path in after_dir.glob("*.ppm")}
        return sorted(before.intersection(after))
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_iter_common_scene_names", "Failed to list scene names", exc)
        ) from exc


def _diff_pair(before_path: Path, after_path: Path, out_path: Path) -> dict[str, float | int | str]:
    """
    Summary
    Compute a pixel-level diff image and statistics for one before/after scene pair.

    Inputs
    before_path: Before scene image path.
    after_path: After scene image path.
    out_path: Diff image output path.

    Outputs
    Dict containing changed pixel count and changed ratio.

    Side effects
    Writes a diff image to disk.

    Error handling
    Raises `RuntimeError` with module and method context when diffing fails.

    Ties to other methods
    Used by `_diff_scenes`.

    Why this exists
    Pixel stats provide an objective signal for unintended visual drift.
    """
    try:
        before = PpmImage.read(before_path)
        after = PpmImage.read(after_path)
        if before.width != after.width or before.height != after.height:
            raise ValueError(
                f"Scene size mismatch {before_path.name}: {before.width}x{before.height} vs {after.width}x{after.height}"
            )

        diff = PpmImage(before.width, before.height, RgbColor(0, 0, 0))
        diff._data[:] = after._data.translate(_DIMMED_PIXEL_TABLE)
        changed = 0
        total = before.width * before.height
        changed_pixel = b"\xff\x00\xb4"

        before_data = before._data
        after_data = after._data
        diff_data = diff._data
        for index in range(0, len(before_data), 3):
            if (
                before_data[index] != after_data[index]
                or before_data[index + 1] != after_data[index + 1]
                or before_data[index + 2] != after_data[index + 2]
            ):
                changed += 1
                diff_data[index : index + 3] = changed_pixel

        diff.write(out_path)
        ratio = (changed / total) if total else 0.0
        return {
            "scene": before_path.stem,
            "changed_pixels": int(changed),
            "total_pixels": int(total),
            "changed_ratio": float(ratio),
        }
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_diff_pair", "Failed to diff scene pair", exc)) from exc


def _diff_scenes(before_dir: Path, after_dir: Path, diff_dir: Path) -> list[dict[str, float | int | str]]:
    """
    Summary
    Compute diff images and stats for all shared scenes.

    Inputs
    before_dir: Before capture directory.
    after_dir: After capture directory.
    diff_dir: Output directory for diff images.

    Outputs
    List of per-scene diff stats.

    Side effects
    Reads scene captures and writes diff images.

    Error handling
    Raises `RuntimeError` with module and method context when diffing fails.

    Ties to other methods
    Used by CLI diff mode.

    Why this exists
    Visual regression requires consistent comparison across all key states.
    """
    try:
        diff_dir.mkdir(parents=True, exist_ok=True)
        scenes = _iter_common_scene_names(before_dir, after_dir)
        if not scenes:
            raise ValueError("No shared .ppm scenes were found between before/after directories")
        results: list[dict[str, float | int | str]] = []
        for scene in scenes:
            result = _diff_pair(
                before_dir / f"{scene}.ppm",
                after_dir / f"{scene}.ppm",
                diff_dir / f"{scene}.ppm",
            )
            results.append(result)
        return results
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_diff_scenes", "Failed to diff scenes", exc)) from exc


def _write_manifest(path: Path, *, mode: str, scenes: Sequence[str], extra: dict[str, object]) -> None:
    """
    Summary
    Write a JSON manifest summarizing capture or diff output.

    Inputs
    path: Manifest path.
    mode: Workflow mode label.
    scenes: Scene names.
    extra: Additional summary payload.

    Outputs
    None.

    Side effects
    Writes a JSON file to disk.

    Error handling
    Raises `RuntimeError` with module and method context when writing fails.

    Ties to other methods
    Used by both capture and diff workflows.

    Why this exists
    CI jobs and reviewers need machine-readable summary output.
    """
    try:
        payload = {
            "mode": str(mode),
            "scenes": list(scenes),
            **dict(extra),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_write_manifest", "Failed to write manifest", exc)
        ) from exc


def _parse_args() -> argparse.Namespace:
    """
    Summary
    Parse CLI arguments for visual baseline capture and diff workflows.

    Inputs
    None.

    Outputs
    Parsed argparse namespace.

    Side effects
    Reads process argv.

    Error handling
    Raises `RuntimeError` with module and method context when argument parsing fails.

    Ties to other methods
    Used by `main`.

    Why this exists
    Keeps visual baseline operations explicit and scriptable for CI and local workflows.
    """
    try:
        parser = argparse.ArgumentParser(
            description="Capture deterministic GUI baseline scenes and compute visual diffs."
        )
        parser.add_argument("mode", choices=("capture", "diff"), help="Workflow mode.")
        parser.add_argument("--config", default="config/config.json", help="Path to config JSON.")
        parser.add_argument("--output-dir", help="Output directory for capture mode.")
        parser.add_argument("--before-dir", help="Before capture directory for diff mode.")
        parser.add_argument("--after-dir", help="After capture directory for diff mode.")
        parser.add_argument("--diff-dir", help="Diff output directory for diff mode.")
        parser.add_argument("--manifest", help="Optional explicit manifest path.")
        parser.add_argument(
            "--fail-on-change",
            action="store_true",
            help="Exit 1 in diff mode when any scene has changed pixels.",
        )
        return parser.parse_args()
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_parse_args", "Failed to parse args", exc)) from exc


def _resolve_existing_directory(path_text: str, *, arg_name: str) -> Path:
    """
    Summary
    Resolve and validate a required existing directory argument.

    Inputs
    path_text: Raw directory argument value.
    arg_name: CLI flag name for contextual errors.

    Outputs
    Resolved directory path.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when validation fails.

    Ties to other methods
    Used by `main` for diff mode input directories.

    Why this exists
    Diff mode should fail fast with clear guidance when required input directories are invalid.
    """
    try:
        resolved = Path(path_text).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"{arg_name} does not exist: {resolved}")
        if not resolved.is_dir():
            raise ValueError(f"{arg_name} must be a directory: {resolved}")
        return resolved
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_resolve_existing_directory",
                f"Invalid value for `{arg_name}`",
                exc,
            )
        ) from exc


def _resolve_output_directory(path_text: str, *, arg_name: str) -> Path:
    """
    Summary
    Resolve and validate an output directory argument.

    Inputs
    path_text: Raw directory argument value.
    arg_name: CLI flag name for contextual errors.

    Outputs
    Resolved directory path.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when validation fails.

    Ties to other methods
    Used by `main` for capture and diff output directories.

    Why this exists
    Output targets must be validated before expensive rendering and diff workflows begin.
    """
    try:
        resolved = Path(path_text).resolve()
        if resolved.exists() and not resolved.is_dir():
            raise ValueError(f"{arg_name} must be a directory path: {resolved}")
        return resolved
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_resolve_output_directory",
                f"Invalid value for `{arg_name}`",
                exc,
            )
        ) from exc


def _emit_boundary_error(method: str, message: str, exc: Exception) -> None:
    """
    Summary
    Write a formatted visual-regression boundary error to stderr.

    Inputs
    method: Boundary method name associated with the failure.
    message: High-level failure context.
    exc: Captured exception instance.

    Outputs
    None.

    Side effects
    Writes one line to stderr.

    Error handling
    Raises `RuntimeError` with module and method context when output formatting fails.

    Ties to other methods
    Used by `main` for CLI boundary failures.

    Why this exists
    CI and local runs need concise boundary failures without traceback noise for operational errors.
    """
    try:
        print(format_error(MODULE_PATH, method, message, exc), file=sys.stderr)
    except (RuntimeError, ValueError, TypeError, OSError) as emit_exc:
        raise RuntimeError(
            format_error(
                MODULE_PATH,
                "_emit_boundary_error",
                "Failed while emitting visual regression boundary error",
                emit_exc,
            )
        ) from emit_exc


def main() -> int:
    """
    Summary
    Run capture or diff workflows for deterministic GUI visual regression checks.

    Inputs
    None.

    Outputs
    Process exit code.

    Side effects
    Reads config, writes scene images, writes diff images, and writes JSON manifests.

    Error handling
    Returns exit code `2` after emitting a formatted boundary error for runtime failures.

    Ties to other methods
    Orchestrates all helper functions in this module.

    Why this exists
    Provides a single command entrypoint for generating and comparing visual baselines.
    """
    try:
        args = _parse_args()
        config_path = Path(str(args.config)).resolve()
        if not config_path.is_file():
            raise FileNotFoundError(f"Config file does not exist: {config_path}")
        theme = _load_theme(config_path)

        if args.mode == "capture":
            if not args.output_dir:
                raise ValueError("--output-dir is required for capture mode")
            output_dir = _resolve_output_directory(str(args.output_dir), arg_name="--output-dir")
            captures = _capture_scenes(output_dir, theme)
            scene_names = [path.stem for path in captures]
            manifest_path = (
                Path(str(args.manifest)).resolve() if args.manifest else output_dir / "manifest.json"
            )
            _write_manifest(
                manifest_path,
                mode="capture",
                scenes=scene_names,
                extra={"output_dir": str(output_dir), "image_count": len(scene_names)},
            )
            print(f"Captured {len(scene_names)} scenes into {output_dir}")
            print(f"Manifest: {manifest_path}")
            return 0

        if not args.before_dir or not args.after_dir:
            raise ValueError("--before-dir and --after-dir are required for diff mode")
        before_dir = _resolve_existing_directory(str(args.before_dir), arg_name="--before-dir")
        after_dir = _resolve_existing_directory(str(args.after_dir), arg_name="--after-dir")
        diff_dir = (
            _resolve_output_directory(str(args.diff_dir), arg_name="--diff-dir")
            if args.diff_dir
            else after_dir / "diff"
        )

        results = _diff_scenes(before_dir, after_dir, diff_dir)
        changed_scenes = [item for item in results if int(item["changed_pixels"]) > 0]
        total_changed = sum(int(item["changed_pixels"]) for item in results)
        total_pixels = sum(int(item["total_pixels"]) for item in results)
        ratio = (total_changed / total_pixels) if total_pixels else 0.0

        manifest_path = Path(str(args.manifest)).resolve() if args.manifest else diff_dir / "manifest.json"
        _write_manifest(
            manifest_path,
            mode="diff",
            scenes=[str(item["scene"]) for item in results],
            extra={
                "before_dir": str(before_dir),
                "after_dir": str(after_dir),
                "diff_dir": str(diff_dir),
                "changed_scene_count": len(changed_scenes),
                "changed_pixels": total_changed,
                "total_pixels": total_pixels,
                "changed_ratio": ratio,
                "results": results,
            },
        )

        print(
            "Diff complete: "
            f"{len(results)} scenes, {len(changed_scenes)} changed, "
            f"{total_changed}/{total_pixels} pixels changed ({ratio:.6f})"
        )
        print(f"Manifest: {manifest_path}")
        if args.fail_on_change and changed_scenes:
            return 1
        return 0
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        _emit_boundary_error("main", "Visual regression workflow failed", exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
