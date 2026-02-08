from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mac_health_checkup.diagnostics.startup import _best_effort_plist_label, _read_launch_items

MODULE_PATH = "tests/test_startup_items_parsing.py"


class StartupItemsParsingTests(unittest.TestCase):
    """
    Summary
    Validate launchd startup item helpers remain deterministic and resilient.

    Inputs
    None.

    Outputs
    Assertions on extracted and sorted labels.

    Side effects
    Creates temporary files on disk for test isolation.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_best_effort_plist_label` and `_read_launch_items` in `mac_health_checkup/diagnostics/startup.py`.

    Why this exists
    Startup enumeration is a high-value signal and must degrade gracefully when plutil parsing fails.
    """

    def test_best_effort_plist_label_prefers_plutil_output(self) -> None:
        """
        Summary
        Ensure plutil label extraction wins over filename stems when available.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates a temp plist file and patches safe_run.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_best_effort_plist_label`.

        Why this exists
        Launchd labels are the stable identifiers users recognize; filename stems are a fallback only.
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                plist_path = Path(td) / "com.example.test.plist"
                plist_path.write_text("{}", encoding="utf-8")
                with patch(
                    "mac_health_checkup.diagnostics.startup.safe_run",
                    autospec=True,
                    return_value=("com.vendor.agent\n", ""),
                ):
                    label = _best_effort_plist_label(plist_path, timeout=1)
                    self.assertEqual(label, "com.vendor.agent")
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:StartupItemsParsingTests.test_best_effort_plist_label_prefers_plutil_output failed: {exc}"
            ) from exc

    def test_read_launch_items_sorts_and_dedupes(self) -> None:
        """
        Summary
        Ensure launch item enumeration sorts case-insensitively and removes duplicates.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates temp plist files and patches label extraction.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_read_launch_items`.

        Why this exists
        Stable ordering prevents report diffs from flapping due to filesystem enumeration order.
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                directory = Path(td)
                (directory / "a.plist").write_text("{}", encoding="utf-8")
                (directory / "b.plist").write_text("{}", encoding="utf-8")
                (directory / "c.plist").write_text("{}", encoding="utf-8")

                labels = ["Com.Example.B", "com.example.a", "com.example.a"]

                def _fake_label(path: Path, *, timeout: int) -> str:
                    _ = path
                    _ = timeout
                    return labels.pop(0)

                with patch(
                    "mac_health_checkup.diagnostics.startup._best_effort_plist_label",
                    autospec=True,
                    side_effect=_fake_label,
                ):
                    out = _read_launch_items(directory, timeout=1)
                    self.assertEqual(out, ["com.example.a", "Com.Example.B"])

                missing = _read_launch_items(directory / "missing", timeout=1)
                self.assertEqual(missing, [])
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:StartupItemsParsingTests.test_read_launch_items_sorts_and_dedupes failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
