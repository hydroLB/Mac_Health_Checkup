from __future__ import annotations

import datetime as _dt
import html
from typing import Mapping, Sequence

from mac_health_checkup.app.backend.snapshot import Snapshot
from mac_health_checkup.app.reports.snapshot_diff import SnapshotDiff
from mac_health_checkup.core.utils.errors import format_error

MODULE_PATH = "mac_health_checkup/app/reports/snapshot_render.py"


def render_snapshot_markdown(snapshot: Snapshot, *, include_diagnostics: bool) -> str:
    """
    Summary
    Render a snapshot report as Markdown.

    Inputs
    snapshot: Snapshot to render.
    include_diagnostics: Whether to include the raw diagnostics dict per section.

    Outputs
    Markdown string.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails unexpectedly.

    Ties to other methods
    Used by the entrypoint `--export markdown` workflow.

    Why this exists
    Markdown exports are easy to share, diff in git, and paste into issue trackers.
    """
    try:
        generated = _format_unix_ms(snapshot.generated_at_unix_ms)
        lines: list[str] = []
        lines.append("# Mac Health Checkup Report")
        lines.append("")
        lines.append(f"- Generated: {generated}")
        lines.append(f"- OK: `{bool(snapshot.ok)}`")
        if snapshot.error:
            lines.append(f"- Error: `{snapshot.error}`")
        lines.append("")

        titles = {item.key: f"{item.title} ({item.subtitle})" for item in snapshot.section_catalog}
        for section in snapshot.sections:
            title = titles.get(section.key, section.key)
            lines.append(f"## {title}")
            lines.append("")
            if section.field:
                lines.append(f"**Summary:** {section.field}")
            else:
                lines.append("**Summary:** (none)")
            lines.append("")
            if section.metrics:
                lines.append("**Metrics**")
                lines.append("")
                lines.extend(_render_metrics_markdown(section.metrics))
                lines.append("")
            if section.table:
                lines.append("**Table**")
                lines.append("")
                lines.extend(_render_table_markdown(section.table.headers, section.table.rows))
                lines.append("")
            if include_diagnostics and section.diagnostics:
                lines.append("**Diagnostics (raw)**")
                lines.append("")
                lines.append("```json")
                lines.append(_json_pretty(section.diagnostics))
                lines.append("```")
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "render_snapshot_markdown", "Failed to render Markdown", exc)
        ) from exc


def render_diff_markdown(diff: SnapshotDiff) -> str:
    """
    Summary
    Render a snapshot diff report as Markdown.

    Inputs
    diff: SnapshotDiff object.

    Outputs
    Markdown string.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails unexpectedly.

    Ties to other methods
    Used by the entrypoint `--diff` and `--export` diff workflows.

    Why this exists
    Markdown diffs are readable in terminals and easy to share in tickets and pull requests.
    """
    try:
        before_ts = _format_unix_ms(diff.before_generated_at_unix_ms)
        after_ts = _format_unix_ms(diff.after_generated_at_unix_ms)
        lines: list[str] = []
        lines.append("# Mac Health Checkup Snapshot Diff")
        lines.append("")
        lines.append(f"- Before: {before_ts} (ok=`{diff.before_ok}`)")
        if diff.before_error:
            lines.append(f"- Before error: `{diff.before_error}`")
        lines.append(f"- After: {after_ts} (ok=`{diff.after_ok}`)")
        if diff.after_error:
            lines.append(f"- After error: `{diff.after_error}`")
        lines.append("")

        if diff.added_sections:
            lines.append(f"**Added sections:** {', '.join(f'`{k}`' for k in diff.added_sections)}")
        if diff.removed_sections:
            lines.append(f"**Removed sections:** {', '.join(f'`{k}`' for k in diff.removed_sections)}")
        if diff.added_sections or diff.removed_sections:
            lines.append("")

        changed_sections = diff.changed_sections
        if not changed_sections:
            lines.append("No UI-facing changes detected.")
            lines.append("")
            return "\n".join(lines).rstrip() + "\n"

        for section in changed_sections:
            lines.append(f"## {section.key}")
            lines.append("")
            if (section.field_before or "") != (section.field_after or ""):
                lines.append("**Summary**")
                lines.append("")
                lines.append(f"- Before: {section.field_before or '(none)'}")
                lines.append(f"- After: {section.field_after or '(none)'}")
                lines.append("")
            if section.metrics_added or section.metrics_removed or section.metrics_changed:
                lines.append("**Metrics changes**")
                lines.append("")
                for row in section.metrics_added:
                    label, value, status = row
                    lines.append(f"- Added: `{label}` = `{value}` ({status})")
                for row in section.metrics_removed:
                    label, value, status = row
                    lines.append(f"- Removed: `{label}` = `{value}` ({status})")
                for change in section.metrics_changed:
                    lines.append(
                        f"- Changed: `{change.label}` `{change.before}` ({change.before_status}) -> `{change.after}` ({change.after_status})"
                    )
                lines.append("")
            if section.table_changed:
                lines.append("**Table changes**")
                lines.append("")
                lines.append(f"- Rows: {section.table_before_rows} -> {section.table_after_rows}")
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "render_diff_markdown", "Failed to render diff Markdown", exc)
        ) from exc


def render_snapshot_html(snapshot: Snapshot, *, include_diagnostics: bool) -> str:
    """
    Summary
    Render a snapshot report as a standalone HTML document.

    Inputs
    snapshot: Snapshot to render.
    include_diagnostics: Whether to include the raw diagnostics dict per section.

    Outputs
    HTML string.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails unexpectedly.

    Ties to other methods
    Used by the entrypoint `--export html` workflow.

    Why this exists
    HTML exports can be opened locally and shared as a single file without additional tooling.
    """
    try:
        theme = snapshot.theme
        colors = theme.colors
        bg = _get_color(colors, "bg", "#111111")
        fg = _get_color(colors, "fg", "#eeeeee")
        section_color = _get_color(colors, "section", "#339af0")
        card_bg = _get_color(theme.gui, "card_bg", "#1b2027")
        border = _get_color(theme.gui, "card_border", "#2a313c")
        font_family = _get_str(theme.fonts, "family_default", "system-ui")
        mono_family = _get_str(theme.fonts, "family_mono", "ui-monospace")

        generated = html.escape(_format_unix_ms(snapshot.generated_at_unix_ms))
        ok = "true" if snapshot.ok else "false"
        error_html = (
            f"<p><strong>Error:</strong> <code>{html.escape(snapshot.error)}</code></p>"
            if snapshot.error
            else ""
        )

        titles = {item.key: f"{item.title} ({item.subtitle})" for item in snapshot.section_catalog}
        sections_html: list[str] = []
        for section in snapshot.sections:
            title = html.escape(titles.get(section.key, section.key))
            summary = html.escape(section.field or "(none)")
            metrics_html = _render_metrics_html(section.metrics) if section.metrics else ""
            table_html = (
                _render_table_html(section.table.headers, section.table.rows) if section.table else ""
            )
            diagnostics_html = ""
            if include_diagnostics and section.diagnostics:
                diagnostics_html = (
                    "<details><summary>Diagnostics (raw)</summary>"
                    f"<pre><code>{html.escape(_json_pretty(section.diagnostics))}</code></pre></details>"
                )
            sections_html.append(
                f"""
                <section class="card">
                  <h2>{title}</h2>
                  <p><strong>Summary:</strong> {summary}</p>
                  {metrics_html}
                  {table_html}
                  {diagnostics_html}
                </section>
                """.strip()
            )

        css = f"""
        :root {{
          --bg: {bg};
          --fg: {fg};
          --section: {section_color};
          --card-bg: {card_bg};
          --border: {border};
          --font: {font_family};
          --mono: {mono_family};
        }}
        body {{
          margin: 0;
          padding: 24px;
          background: var(--bg);
          color: var(--fg);
          font-family: var(--font);
        }}
        h1, h2 {{
          margin: 0 0 12px 0;
          color: var(--section);
        }}
        .meta code {{
          font-family: var(--mono);
        }}
        .card {{
          background: var(--card-bg);
          border: 1px solid var(--border);
          border-radius: 10px;
          padding: 16px;
          margin: 16px 0;
        }}
        table {{
          width: 100%;
          border-collapse: collapse;
          margin: 8px 0 0 0;
          font-family: var(--mono);
          font-size: 13px;
        }}
        th, td {{
          border: 1px solid var(--border);
          padding: 6px 8px;
          text-align: left;
          vertical-align: top;
        }}
        th {{
          background: rgba(255,255,255,0.04);
        }}
        details summary {{
          cursor: pointer;
          margin-top: 10px;
        }}
        pre {{
          white-space: pre-wrap;
          word-break: break-word;
        }}
        """.strip()

        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Mac Health Checkup Report</title>
    <style>{css}</style>
  </head>
  <body>
    <h1>Mac Health Checkup Report</h1>
    <div class="meta">
      <p><strong>Generated:</strong> {generated}</p>
      <p><strong>OK:</strong> <code>{ok}</code></p>
      {error_html}
    </div>
    {"".join(sections_html)}
  </body>
</html>
"""
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "render_snapshot_html", "Failed to render HTML", exc)
        ) from exc


def render_diff_html(diff: SnapshotDiff) -> str:
    """
    Summary
    Render a snapshot diff as a standalone HTML document.

    Inputs
    diff: SnapshotDiff object.

    Outputs
    HTML string.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when rendering fails unexpectedly.

    Ties to other methods
    Used by the entrypoint `--export html` diff workflow.

    Why this exists
    HTML diffs are easy to scan visually and share as a single file.
    """
    try:
        before_ts = html.escape(_format_unix_ms(diff.before_generated_at_unix_ms))
        after_ts = html.escape(_format_unix_ms(diff.after_generated_at_unix_ms))

        added = ", ".join(html.escape(k) for k in diff.added_sections) if diff.added_sections else ""
        removed = ", ".join(html.escape(k) for k in diff.removed_sections) if diff.removed_sections else ""

        sections_html: list[str] = []
        for section in diff.changed_sections:
            parts: list[str] = [f"<h2>{html.escape(section.key)}</h2>"]
            if (section.field_before or "") != (section.field_after or ""):
                parts.append("<h3>Summary</h3>")
                parts.append(
                    f"<ul><li><strong>Before:</strong> {html.escape(section.field_before or '(none)')}</li>"
                    f"<li><strong>After:</strong> {html.escape(section.field_after or '(none)')}</li></ul>"
                )
            if section.metrics_added or section.metrics_removed or section.metrics_changed:
                parts.append("<h3>Metrics changes</h3>")
                parts.append("<ul>")
                for label, value, status in section.metrics_added:
                    parts.append(
                        f"<li>Added <code>{html.escape(label)}</code> = <code>{html.escape(value)}</code> ({html.escape(status)})</li>"
                    )
                for label, value, status in section.metrics_removed:
                    parts.append(
                        f"<li>Removed <code>{html.escape(label)}</code> = <code>{html.escape(value)}</code> ({html.escape(status)})</li>"
                    )
                for change in section.metrics_changed:
                    parts.append(
                        f"<li>Changed <code>{html.escape(change.label)}</code> "
                        f"<code>{html.escape(change.before)}</code> ({html.escape(change.before_status)}) "
                        f"&rarr; <code>{html.escape(change.after)}</code> ({html.escape(change.after_status)})</li>"
                    )
                parts.append("</ul>")
            if section.table_changed:
                parts.append("<h3>Table changes</h3>")
                parts.append(
                    f"<p>Rows: {int(section.table_before_rows)} &rarr; {int(section.table_after_rows)}</p>"
                )
            sections_html.append(f'<section class="card">{"".join(parts)}</section>')

        css = """
        body { font-family: system-ui, -apple-system, Segoe UI, sans-serif; padding: 24px; }
        h1 { margin-top: 0; }
        code { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
        .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin: 16px 0; }
        """.strip()

        meta_parts: list[str] = [
            f"<p><strong>Before:</strong> {before_ts} (ok=<code>{str(diff.before_ok).lower()}</code>)</p>",
            f"<p><strong>After:</strong> {after_ts} (ok=<code>{str(diff.after_ok).lower()}</code>)</p>",
        ]
        if diff.before_error:
            meta_parts.append(
                f"<p><strong>Before error:</strong> <code>{html.escape(diff.before_error)}</code></p>"
            )
        if diff.after_error:
            meta_parts.append(
                f"<p><strong>After error:</strong> <code>{html.escape(diff.after_error)}</code></p>"
            )
        if added:
            meta_parts.append(f"<p><strong>Added sections:</strong> {added}</p>")
        if removed:
            meta_parts.append(f"<p><strong>Removed sections:</strong> {removed}</p>")

        body_html = "".join(meta_parts) + (
            "".join(sections_html) if sections_html else "<p>No UI-facing changes detected.</p>"
        )
        return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Mac Health Checkup Snapshot Diff</title>
    <style>{css}</style>
  </head>
  <body>
    <h1>Mac Health Checkup Snapshot Diff</h1>
    {body_html}
  </body>
</html>
"""
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "render_diff_html", "Failed to render diff HTML", exc)
        ) from exc


def _render_metrics_markdown(rows: list[tuple[str, str, str]]) -> list[str]:
    headers = ("Metric", "Value", "Status")
    table_rows: list[tuple[str, str, str]] = [(label, value, status) for label, value, status in rows]
    return _render_table_markdown(headers, table_rows)


def _render_table_markdown(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    safe_headers = [_md_escape(str(cell)) for cell in headers]
    lines = ["| " + " | ".join(safe_headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in safe_headers) + " |")
    for row in rows:
        row_list = [str(cell) for cell in row]
        padded = row_list + [""] * max(0, len(safe_headers) - len(row_list))
        safe_cells = [_md_escape(cell) for cell in padded[: len(safe_headers)]]
        lines.append("| " + " | ".join(safe_cells) + " |")
    return lines


def _render_metrics_html(rows: list[tuple[str, str, str]] | None) -> str:
    if not rows:
        return ""
    body_rows = "".join(
        f"<tr><td>{html.escape(label)}</td><td>{html.escape(value)}</td><td>{html.escape(status)}</td></tr>"
        for label, value, status in rows
    )
    return (
        "<h3>Metrics</h3>"
        "<table><thead><tr><th>Metric</th><th>Value</th><th>Status</th></tr></thead>"
        f"<tbody>{body_rows}</tbody></table>"
    )


def _render_table_html(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    head = "".join(f"<th>{html.escape(h)}</th>" for h in headers)
    body_rows: list[str] = []
    for row in rows:
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        tds = "".join(f"<td>{html.escape(cell)}</td>" for cell in padded[: len(headers)])
        body_rows.append(f"<tr>{tds}</tr>")
    return f"<h3>Table</h3><table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _md_escape(text: str) -> str:
    safe = (text or "").replace("\\", "\\\\").replace("|", "\\|").replace("\n", " ").strip()
    return safe if safe else " "


def _format_unix_ms(unix_ms: int) -> str:
    dt = _dt.datetime.fromtimestamp(unix_ms / 1000.0).astimezone()
    return dt.isoformat(timespec="seconds")


def _json_pretty(value: Mapping[str, object]) -> str:
    import json

    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)


def _get_color(source: Mapping[str, object], key: str, default: str) -> str:
    value = source.get(key)
    return value if isinstance(value, str) and value.strip() else default


def _get_str(source: Mapping[str, object], key: str, default: str) -> str:
    value = source.get(key)
    return value if isinstance(value, str) and value.strip() else default
