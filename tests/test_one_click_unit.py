from __future__ import annotations

import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from mac_health_checkup.app.backend import one_click
from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_one_click_unit.py"


class OneClickUnitTests(unittest.TestCase):
    """
    Summary
    Validate one-click runner helper functions with mocked IO.

    Inputs
    None.

    Outputs
    Assertions on derived config shapes and best-effort helpers.

    Side effects
    Creates temporary files and modifies PATH for test scope.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `mac_health_checkup/app/backend/one_click.py` helpers.

    Why this exists
    The one-click runner is a UX entrypoint; helpers should be deterministic and safe under partial environments.
    """

    def test_build_config_with_api_overrides_merges_only_api_section(self) -> None:
        """
        Summary
        Ensure only the API section is merged and other sections remain unchanged.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_build_config_with_api_overrides`.

        Why this exists
        The runner should not accidentally mutate unrelated configuration.
        """
        try:
            base = cast(JsonDict, {"api": {"enabled": False, "port": 1}, "ui": {"title": "x"}})
            derived = one_click._build_config_with_api_overrides(
                base, {"enabled": True, "port": 9999, "auth_token": "t"}
            )
            self.assertEqual(derived["ui"], {"title": "x"})
            api = derived.get("api")
            self.assertIsInstance(api, dict)
            if isinstance(api, dict):
                self.assertEqual(api.get("enabled"), True)
                self.assertEqual(api.get("port"), 9999)
                self.assertEqual(api.get("auth_token"), "t")
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_build_config_with_api_overrides_merges_only_api_section failed: {exc}"
            ) from exc

    def test_read_json_dict_requires_object_root(self) -> None:
        """
        Summary
        Ensure JSON reader rejects non-object roots with a clear error.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Writes a temp file.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_read_json_dict`.

        Why this exists
        The base config is a structured object; failing early avoids confusing runtime behavior.
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "bad.json"
                path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
                with self.assertRaises(RuntimeError):
                    _ = one_click._read_json_dict(path)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_read_json_dict_requires_object_root failed: {exc}"
            ) from exc

    def test_find_executable_searches_path(self) -> None:
        """
        Summary
        Ensure PATH lookup returns an executable file when present.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates an executable temp file and mutates PATH within the test.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_find_executable`.

        Why this exists
        TLS generation should be best-effort and should not rely on brittle hard-coded paths.
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                exe = Path(td) / "openssl"
                exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
                with patch.dict(os.environ, {"PATH": td}, clear=False):
                    found = one_click._find_executable("openssl")
                    self.assertEqual(found, str(exe))
                self.assertIsNone(one_click._find_executable(""))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_find_executable_searches_path failed: {exc}"
            ) from exc

    def test_ensure_self_signed_cert_handles_missing_openssl_and_timeouts(self) -> None:
        """
        Summary
        Ensure TLS cert generation degrades gracefully when openssl is missing or fails.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates temp paths and patches subprocess behavior.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_ensure_self_signed_cert`.

        Why this exists
        One-click should keep running even when TLS auto-generation is unavailable.
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                cert = Path(td) / "cert.pem"
                key = Path(td) / "key.pem"
                with patch(
                    "mac_health_checkup.app.backend.one_click._find_executable",
                    autospec=True,
                    return_value=None,
                ):
                    ready, msg = one_click._ensure_self_signed_cert(cert_path=cert, key_path=key)
                    self.assertFalse(ready)
                    self.assertIsInstance(msg, str)

                with patch(
                    "mac_health_checkup.app.backend.one_click._find_executable",
                    autospec=True,
                    return_value="/bin/openssl",
                ):
                    with patch(
                        "mac_health_checkup.app.backend.one_click.subprocess.run",
                        autospec=True,
                        side_effect=subprocess.TimeoutExpired(cmd=["openssl"], timeout=1),
                    ):
                        ready2, msg2 = one_click._ensure_self_signed_cert(cert_path=cert, key_path=key)
                        self.assertFalse(ready2)
                        self.assertIn("timed out", str(msg2))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_ensure_self_signed_cert_handles_missing_openssl_and_timeouts failed: {exc}"
            ) from exc

    def test_best_effort_lan_ip_returns_none_on_loopback(self) -> None:
        """
        Summary
        Ensure LAN IP helper returns None for loopback-like values and handles OSError.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches socket.socket.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_best_effort_lan_ip`.

        Why this exists
        Pairing URLs should not advertise loopback addresses for LAN mode.
        """
        try:

            class _Sock:
                def __enter__(self) -> "_Sock":
                    return self

                def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                    _ = exc_type
                    _ = exc
                    _ = tb
                    return

                def connect(self, _addr: object) -> None:
                    return

                def getsockname(self) -> tuple[str, int]:
                    return ("127.0.0.1", 0)

            with patch(
                "mac_health_checkup.app.backend.one_click.socket.socket", autospec=True, return_value=_Sock()
            ):
                self.assertIsNone(one_click._best_effort_lan_ip())
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_best_effort_lan_ip_returns_none_on_loopback failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
