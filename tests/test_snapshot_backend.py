from __future__ import annotations

import json
import unittest
from typing import cast

from mac_health_checkup.app.backend.snapshot import emit_snapshot_json
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_snapshot_backend.py"


def _handler_field_only(host: SectionHost) -> JsonDict:
    """
    Summary
    Provide a deterministic handler that sets only a field.

    Inputs
    host: SectionHost used to store render output.

    Outputs
    Minimal diagnostics dict.

    Side effects
    Writes into the host via `set_field`.

    Error handling
    None.

    Ties to other methods
    Used by `SnapshotBackendTests` to validate snapshot JSON encoding.

    Why this exists
    Keeps tests deterministic without invoking macOS system commands.
    """
    host.set_field("field_only", "hello")
    return {"ok": True, "kind": "field_only"}


def _handler_full(host: SectionHost) -> JsonDict:
    """
    Summary
    Provide a deterministic handler that sets field, metrics, and table.

    Inputs
    host: SectionHost used to store render output.

    Outputs
    Minimal diagnostics dict.

    Side effects
    Writes into the host via `set_field`, `render_metrics_table`, and `render_table`.

    Error handling
    None.

    Ties to other methods
    Used by `SnapshotBackendTests` to validate full snapshot payload shape.

    Why this exists
    Ensures the snapshot schema supports all UI primitives.
    """
    host.set_field("full", "summary")
    host.render_metrics_table("full", [("A", "1", "ok"), ("B", "2", "warn")], columns=2)
    host.render_table("full", ("Col",), [("Row",)])
    return {"ok": True, "kind": "full"}


def _handler_raises(_host: SectionHost) -> JsonDict:
    """
    Summary
    Provide a deterministic handler that raises an exception.

    Inputs
    _host: SectionHost (unused).

    Outputs
    Never returns.

    Side effects
    None.

    Error handling
    Always raises `RuntimeError`.

    Ties to other methods
    Used by `SnapshotBackendTests` to validate per-section failure capture.

    Why this exists
    Ensures snapshot building is resilient when a section fails.
    """
    raise RuntimeError("boom")


class SnapshotBackendTests(unittest.TestCase):
    """
    Summary
    Validate the Python JSON snapshot backend used by the SwiftUI frontend.

    Inputs
    None.

    Outputs
    None.

    Side effects
    None.

    Error handling
    Relies on unittest assertions.

    Ties to other methods
    Tests `emit_snapshot_json` from `mac_health_checkup.app.backend.snapshot`.

    Why this exists
    Prevents schema drift and keeps frontend integration deterministic.
    """

    def test_snapshot_ok(self) -> None:
        """
        Summary
        Ensure a successful snapshot encodes required fields and section payloads.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Fails the test via assertions when output is invalid.

        Ties to other methods
        Calls `emit_snapshot_json` with deterministic handlers.

        Why this exists
        Protects the JSON contract expected by the Swift decoder.
        """
        handlers = {"field_only": _handler_field_only, "full": _handler_full}
        code, payload = emit_snapshot_json(handlers, pretty=False)
        self.assertEqual(code, 0)
        data = json.loads(payload)
        self.assertEqual(data["schema_version"], 2)
        self.assertTrue(data["ok"])
        self.assertIsInstance(data["generated_at_unix_ms"], int)
        self.assertEqual([s["key"] for s in data["sections"]], ["field_only", "full"])
        self.assertIn("theme", data)
        self.assertIn("section_catalog", data)
        self.assertIsInstance(data["section_catalog"], list)
        full = next(section for section in data["sections"] if section["key"] == "full")
        self.assertEqual(full["field"], "summary")
        self.assertEqual(full["metrics"][0], ["A", "1", "ok"])
        self.assertEqual(full["table"]["headers"], ["Col"])
        self.assertEqual(full["table"]["rows"], [["Row"]])

    def test_snapshot_section_failure(self) -> None:
        """
        Summary
        Ensure a failing section does not abort snapshot generation.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Fails the test via assertions when output does not capture errors.

        Ties to other methods
        Calls `emit_snapshot_json` with a handler that raises.

        Why this exists
        Ensures the native frontend can continue rendering partial data.
        """
        handlers = {"boom": _handler_raises}
        code, payload = emit_snapshot_json(handlers, pretty=False)
        self.assertEqual(code, 1)
        data = json.loads(payload)
        self.assertFalse(data["ok"])
        self.assertIsInstance(data.get("error"), str)
        self.assertIn("boom", data["error"])
        self.assertEqual(len(data["sections"]), 1)
        section = data["sections"][0]
        self.assertEqual(section["key"], "boom")
        diagnostics = cast(JsonDict, section["diagnostics"])
        self.assertIsInstance(diagnostics.get("error"), str)


if __name__ == "__main__":
    unittest.main()
