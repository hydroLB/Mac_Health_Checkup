from __future__ import annotations

import datetime as dt
import unittest

from mac_health_checkup.diagnostics.backups import (
    _age_days,
    _extract_tm_timestamp,
    _parse_tm_timestamp,
    _tm_is_running,
)
from mac_health_checkup.diagnostics.processes import _parse_ps_rows
from mac_health_checkup.diagnostics.security import (
    _parse_filevault_status,
    _parse_firewall_globalstate,
    _parse_gatekeeper_status,
    _parse_sip_status,
)
from mac_health_checkup.diagnostics.system import _parse_df_root, _parse_memory_pressure
from mac_health_checkup.diagnostics.updates import _parse_update_labels

MODULE_PATH = "tests/test_diagnostics_parsing_extended.py"


class SecurityPostureParsingTests(unittest.TestCase):
    """
    Summary
    Validate security posture parsers normalize common macOS command outputs.

    Inputs
    None.

    Outputs
    Assertions on parse results.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises parsers in `mac_health_checkup/diagnostics/security.py`.

    Why this exists
    These parsers feed the UI, exports, and automation layers. They must be conservative and deterministic.
    """

    def test_parse_filevault_status_handles_on_off_and_unknown(self) -> None:
        """
        Summary
        Ensure FileVault output normalization covers common variants.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_parse_filevault_status`.

        Why this exists
        FileVault phrasing varies across macOS versions; the UI needs a stable enabled flag.
        """
        try:
            self.assertEqual(_parse_filevault_status("FileVault is On."), {"enabled": True, "status": "on"})
            self.assertEqual(
                _parse_filevault_status("FileVault is Off."), {"enabled": False, "status": "off"}
            )
            self.assertEqual(_parse_filevault_status(""), {"enabled": None, "status": "unknown"})
            self.assertEqual(
                _parse_filevault_status("unexpected output"), {"enabled": None, "status": "unknown"}
            )
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:SecurityPostureParsingTests.test_parse_filevault_status_handles_on_off_and_unknown failed: {exc}"
            ) from exc

    def test_parse_sip_gatekeeper_and_firewall(self) -> None:
        """
        Summary
        Ensure SIP, Gatekeeper, and firewall parsing produce stable booleans.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_parse_sip_status`, `_parse_gatekeeper_status`, `_parse_firewall_globalstate`.

        Why this exists
        These values feed the actionable posture summary; they should degrade to unknown rather than guess.
        """
        try:
            self.assertEqual(
                _parse_sip_status("System Integrity Protection status: enabled."),
                {"enabled": True, "status": "enabled"},
            )
            self.assertEqual(
                _parse_sip_status("System Integrity Protection status: disabled."),
                {"enabled": False, "status": "disabled"},
            )
            self.assertEqual(
                _parse_gatekeeper_status("assessments enabled"), {"enabled": True, "status": "enabled"}
            )
            self.assertEqual(
                _parse_gatekeeper_status("assessments disabled"), {"enabled": False, "status": "disabled"}
            )
            self.assertEqual(_parse_firewall_globalstate("0\n"), {"enabled": False, "state": 0})
            self.assertEqual(_parse_firewall_globalstate("2\n"), {"enabled": True, "state": 2})
            self.assertEqual(_parse_firewall_globalstate("not_an_int\n"), {"enabled": None, "state": None})
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:SecurityPostureParsingTests.test_parse_sip_gatekeeper_and_firewall failed: {exc}"
            ) from exc


class SystemPressureParsingTests(unittest.TestCase):
    """
    Summary
    Validate storage and memory pressure parsing helpers.

    Inputs
    None.

    Outputs
    Assertions on computed percentages.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises parsers in `mac_health_checkup/diagnostics/system.py`.

    Why this exists
    Percent computations drive warn/bad thresholds and should be robust to formatting variation.
    """

    def test_parse_df_root_computes_free_percent(self) -> None:
        """
        Summary
        Ensure `df` capacity parsing returns used and free percent.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_parse_df_root`.

        Why this exists
        Disk free percent is a high-signal, size-independent metric and must be computed consistently.
        """
        try:
            raw = (
                "Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted on\n"
                "/dev/disk3s1  975000000  780000000 195000000  80%  1234  5678  18%  /\n"
            )
            parsed = _parse_df_root(raw)
            self.assertEqual(parsed.get("used_percent"), 80.0)
            self.assertEqual(parsed.get("free_percent"), 20.0)
            self.assertEqual(_parse_df_root(""), {"used_percent": None, "free_percent": None})
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:SystemPressureParsingTests.test_parse_df_root_computes_free_percent failed: {exc}"
            ) from exc

    def test_parse_memory_pressure_extracts_free_percent(self) -> None:
        """
        Summary
        Ensure `memory_pressure` parsing extracts the system-wide free percent when present.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_parse_memory_pressure`.

        Why this exists
        The UI and automation layer rely on a stable numeric signal without privileged collectors.
        """
        try:
            raw = "System-wide memory free percentage: 13.2%\n"
            parsed = _parse_memory_pressure(raw)
            self.assertEqual(parsed.get("free_percent"), 13.2)
            self.assertEqual(_parse_memory_pressure("no match"), {"free_percent": None})
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:SystemPressureParsingTests.test_parse_memory_pressure_extracts_free_percent failed: {exc}"
            ) from exc


class SoftwareUpdateParsingTests(unittest.TestCase):
    """
    Summary
    Validate softwareupdate parsing is stable across noisy output.

    Inputs
    None.

    Outputs
    Assertions on parsed labels.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_parse_update_labels` in `mac_health_checkup/diagnostics/updates.py`.

    Why this exists
    Update labels are used in reports and diffs; duplicates and noise should be handled deterministically.
    """

    def test_parse_update_labels_dedupes_and_preserves_order(self) -> None:
        """
        Summary
        Ensure update label parsing returns unique labels in first-seen order.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_parse_update_labels`.

        Why this exists
        `softwareupdate` output can repeat labels; reports should not oscillate due to duplicates.
        """
        try:
            raw = "\n".join(
                [
                    "Software Update Tool",
                    "* Label One",
                    "  some details",
                    "* Label Two",
                    "* label one",
                    "",
                ]
            )
            labels = _parse_update_labels(raw)
            self.assertEqual(labels, ["Label One", "Label Two"])
            self.assertEqual(_parse_update_labels(""), [])
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:SoftwareUpdateParsingTests.test_parse_update_labels_dedupes_and_preserves_order failed: {exc}"
            ) from exc


class TimeMachineParsingTests(unittest.TestCase):
    """
    Summary
    Validate Time Machine timestamp extraction and status parsing helpers.

    Inputs
    None.

    Outputs
    Assertions on extracted timestamps and state.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises helpers in `mac_health_checkup/diagnostics/backups.py`.

    Why this exists
    Backup recency thresholds depend on correct timestamp parsing and conservative status detection.
    """

    def test_extract_and_parse_timestamp(self) -> None:
        """
        Summary
        Ensure timestamp extraction works on typical latestbackup paths.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_extract_tm_timestamp` and `_parse_tm_timestamp`.

        Why this exists
        `tmutil latestbackup` returns a path; recency depends on the embedded timestamp.
        """
        try:
            path = "/Volumes/TimeMachine/Backups.backupdb/Host/2026-02-05-120102"
            ts = _extract_tm_timestamp(path)
            self.assertEqual(ts, "2026-02-05-120102")
            parsed = _parse_tm_timestamp(ts or "")
            self.assertIsNotNone(parsed)
            if parsed is not None:
                self.assertIsNotNone(parsed.tzinfo)
            self.assertIsNone(_parse_tm_timestamp("not a timestamp"))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:TimeMachineParsingTests.test_extract_and_parse_timestamp failed: {exc}"
            ) from exc

    def test_age_days_and_running_state_are_conservative(self) -> None:
        """
        Summary
        Ensure age calculations never go negative and running detection is best-effort.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_age_days` and `_tm_is_running`.

        Why this exists
        Automation uses these signals; flapping or negative ages would be misleading.
        """
        try:
            now = dt.datetime.now().astimezone()
            three_days_ago = now - dt.timedelta(days=3)
            age = _age_days(three_days_ago)
            self.assertGreaterEqual(age, 2.8)
            self.assertLessEqual(age, 3.2)
            self.assertIsNone(_tm_is_running(""))
            self.assertTrue(_tm_is_running("Running = 1;"))
            self.assertFalse(_tm_is_running("running = 0"))
            self.assertIsNone(_tm_is_running("no running key"))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:TimeMachineParsingTests.test_age_days_and_running_state_are_conservative failed: {exc}"
            ) from exc


class ProcessesParsingTests(unittest.TestCase):
    """
    Summary
    Validate `ps` parsing produces deterministic process rows.

    Inputs
    None.

    Outputs
    Assertions on parsed row structure.

    Side effects
    None.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `_parse_ps_rows` in `mac_health_checkup/diagnostics/processes.py`.

    Why this exists
    Process offenders are an actionability feature; parsing must ignore malformed rows safely.
    """

    def test_parse_ps_rows_skips_header_and_respects_limit(self) -> None:
        """
        Summary
        Ensure header rows are ignored, malformed lines are skipped, and limits are respected.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context if parsing fails.

        Ties to other methods
        Exercises `_parse_ps_rows`.

        Why this exists
        `ps` output is unstructured; the parser should be conservative and bounded.
        """
        try:
            raw = "\n".join(
                [
                    "PID %CPU %MEM COMMAND",
                    "1  10.5  2.3  kernel_task",
                    "bad line",
                    "42  0.1  0.2  Google Chrome Helper",
                ]
            )
            rows = _parse_ps_rows(raw, limit=1)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].pid, 1)
            self.assertEqual(rows[0].command, "kernel_task")

            rows2 = _parse_ps_rows(raw, limit=5)
            self.assertEqual(len(rows2), 2)
            self.assertEqual(rows2[1].pid, 42)
            self.assertIn("Chrome", rows2[1].command)
            self.assertEqual(_parse_ps_rows(raw, limit=0), [])
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:ProcessesParsingTests.test_parse_ps_rows_skips_header_and_respects_limit failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
