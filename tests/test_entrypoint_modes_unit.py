from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import mac_health_checkup.__main__ as package_main
import mac_health_checkup.app.entrypoint as entrypoint
from mac_health_checkup.app.backend.snapshot import Snapshot, SnapshotTheme

MODULE_PATH = "tests/test_entrypoint_modes_unit.py"


def _minimal_snapshot(*, ok: bool) -> Snapshot:
    return Snapshot(
        schema_version=2,
        generated_at_unix_ms=0,
        theme=SnapshotTheme(ui={}, colors={}, fonts={}, gui={}),
        section_catalog=[],
        sections=[],
        ok=ok,
        error=None,
    )


class EntrypointModesUnitTests(unittest.TestCase):
    """
    Summary
    Validate entrypoint mode selection and automation behavior under mocks.

    Inputs
    None.

    Outputs
    Assertions on exit codes and emitted JSON/files.

    Side effects
    Patches sys.argv and selected dependencies to avoid UI, network binds, and long-running loops.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `mac_health_checkup/app/entrypoint.py` and `mac_health_checkup/__main__.py`.

    Why this exists
    Entrypoint behavior is the primary user surface area. Mode selection should be deterministic and safe.
    """

    def test_package_main_run_exits_with_entrypoint_code(self) -> None:
        """
        Summary
        Ensure `python -m mac_health_checkup` exits with the entrypoint return code.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches entrypoint.main to avoid running real collectors.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `mac_health_checkup.__main__._run`.

        Why this exists
        Module entrypoints should be thin wrappers with consistent exit behavior for automation.
        """
        try:
            with patch("mac_health_checkup.__main__.main", autospec=True, return_value=0):
                with self.assertRaises(SystemExit) as exc:
                    package_main._run()
                self.assertEqual(exc.exception.code, 0)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:EntrypointModesUnitTests.test_package_main_run_exits_with_entrypoint_code failed: {exc}"
            ) from exc

    def test_snapshot_json_mode_prints_json(self) -> None:
        """
        Summary
        Ensure `--snapshot-json` prints a JSON snapshot and returns an ok exit code.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches sys.argv and SnapshotBuilder.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises entrypoint snapshot stdout mode.

        Why this exists
        Snapshot mode is the stable contract for native frontends.
        """
        try:
            snap = _minimal_snapshot(ok=True)

            class _StubBuilder:
                def __init__(self, _handlers: object) -> None:
                    return

                def build(self) -> Snapshot:
                    return snap

            argv = ["prog", "--snapshot-json", "--snapshot-pretty"]
            with patch.object(sys, "argv", argv):
                with patch(
                    "mac_health_checkup.app.entrypoint.ShutdownManager", autospec=True
                ) as shutdown_mock:
                    shutdown_mock.return_value.install_handlers.return_value = None
                    shutdown_mock.return_value.trigger_shutdown.return_value = None
                    with patch("mac_health_checkup.app.backend.snapshot.SnapshotBuilder", _StubBuilder):
                        with patch("builtins.print") as print_mock:
                            code = entrypoint.main()
                            self.assertEqual(code, 0)
                            printed = str(print_mock.call_args[0][0])
                            payload = json.loads(printed)
                            self.assertEqual(payload.get("schema_version"), 2)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:EntrypointModesUnitTests.test_snapshot_json_mode_prints_json failed: {exc}"
            ) from exc

    def test_snapshot_json_out_mode_writes_file(self) -> None:
        """
        Summary
        Ensure `--snapshot-json-out` writes a file and returns an ok exit code.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Writes a temp file under pytest tmp_path via patched argv.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises entrypoint snapshot file output mode.

        Why this exists
        Snapshot files are used for diffing and report exports.
        """
        try:
            snap = _minimal_snapshot(ok=True)

            class _StubBuilder:
                def __init__(self, _handlers: object) -> None:
                    return

                def build(self) -> Snapshot:
                    return snap

            with patch("mac_health_checkup.app.entrypoint.ShutdownManager", autospec=True) as shutdown_mock:
                shutdown_mock.return_value.install_handlers.return_value = None
                shutdown_mock.return_value.trigger_shutdown.return_value = None
                with patch("mac_health_checkup.app.backend.snapshot.SnapshotBuilder", _StubBuilder):
                    with tempfile_path() as out_path:
                        argv = ["prog", "--snapshot-json-out", str(out_path)]
                        with patch.object(sys, "argv", argv):
                            code = entrypoint.main()
                            self.assertEqual(code, 0)
                            text = out_path.read_text(encoding="utf-8")
                            payload = json.loads(text)
                            self.assertTrue(payload.get("ok"))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:EntrypointModesUnitTests.test_snapshot_json_out_mode_writes_file failed: {exc}"
            ) from exc

    def test_diff_against_requires_export(self) -> None:
        """
        Summary
        Ensure --diff-against fails fast without --export.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches argv.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises entrypoint option validation.

        Why this exists
        Diff-against is an export-only mode; failing early provides actionable feedback.
        """
        try:
            argv = ["prog", "--diff-against", "/tmp/snapshot.json"]
            with patch.object(sys, "argv", argv):
                with patch(
                    "mac_health_checkup.app.entrypoint.ShutdownManager", autospec=True
                ) as shutdown_mock:
                    shutdown_mock.return_value.install_handlers.return_value = None
                    shutdown_mock.return_value.trigger_shutdown.return_value = None
                    code = entrypoint.main()
                    self.assertEqual(code, 1)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:EntrypointModesUnitTests.test_diff_against_requires_export failed: {exc}"
            ) from exc


class _TempPath:
    def __init__(self, path: Path) -> None:
        self._path = path

    def __enter__(self) -> Path:
        return self._path

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        _ = exc_type
        _ = exc
        _ = tb
        return


def tempfile_path() -> _TempPath:
    """
    Summary
    Provide a deterministic temporary path within the repo's writable `.local/` folder.

    Inputs
    None.

    Outputs
    Context manager returning a Path.

    Side effects
    Creates parent directories as needed.

    Error handling
    Raises RuntimeError on unexpected filesystem errors.

    Ties to other methods
    Used by entrypoint mode tests for snapshot JSON out.

    Why this exists
    Some environments restrict OS temp directories; using the repo-local `.local/` path stays within the sandbox.
    """
    out = Path(".local") / "tests" / "snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    return _TempPath(out)


if __name__ == "__main__":
    unittest.main()
