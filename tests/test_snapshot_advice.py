from __future__ import annotations

import json
import unittest
from typing import cast

from mac_health_checkup.app.backend import emit_snapshot_json
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_snapshot_advice.py"


def _handler_warn(host: SectionHost) -> JsonDict:
    """
    Summary
    Provide a deterministic handler that emits a warn metric.

    Inputs
    `host` receives rendered output.

    Outputs
    A minimal diagnostics dict.

    Side effects
    Writes metrics on the host.

    Error handling
    Raises `RuntimeError` with module context if the handler fails.

    Ties to other methods
    Used by `SnapshotAdviceTests` to validate advice injection.

    Why this exists
    Ensures advice uses rendered status labels for severity.
    """
    try:
        host.set_field("warn", "field")
        host.render_metrics_table("warn", [("Signal", "value", "warn")], columns=2)
        return {"ok": True, "kind": "warn"}
    except (
        RuntimeError,
        ValueError,
        TypeError,
        AttributeError,
        KeyError,
        IndexError,
        OSError,
    ) as exc:
        raise RuntimeError(f"{MODULE_PATH}:_handler_warn failed: {exc}") from exc


class SnapshotAdviceTests(unittest.TestCase):
    """
    Summary
    Validate snapshot diagnostics include per-section advice.

    Inputs
    None.

    Outputs
    Assertions on advice structure and types.

    Side effects
    None.

    Error handling
    Failures bubble as unittest assertions.

    Ties to other methods
    Exercises the snapshot builder advice injection path via `emit_snapshot_json`.

    Why this exists
    Advice should be available to frontends without schema-breaking changes.
    """

    def test_snapshot_includes_advice_in_diagnostics(self) -> None:
        """
        Summary
        Ensure advice is injected into diagnostics and reflects warn severity from metrics.

        Inputs
        Deterministic handler that emits a warn metric.

        Outputs
        Assertions on `diagnostics.advice` fields.

        Side effects
        None.

        Error handling
        Raises `AssertionError` with module and test context on unexpected outcomes.

        Ties to other methods
        Calls `emit_snapshot_json`.

        Why this exists
        Advice must be machine-readable and stable.
        """
        handlers = {"warn": _handler_warn}
        code, payload = emit_snapshot_json(handlers, pretty=False)
        self.assertEqual(code, 0)
        data = json.loads(payload)
        section = data["sections"][0]
        diagnostics = cast(JsonDict, section["diagnostics"])
        advice = cast(JsonDict, diagnostics.get("advice"))
        self.assertEqual(advice.get("severity"), "warn")
        self.assertIsInstance(advice.get("diagnosis"), str)
        self.assertIsInstance(advice.get("next_steps"), list)


if __name__ == "__main__":
    unittest.main()
