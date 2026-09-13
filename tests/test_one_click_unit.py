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
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
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
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_read_json_dict_requires_object_root failed: {exc}"
            ) from exc

    def test_run_one_click_agent_falls_back_to_loopback_when_tls_is_unavailable(self) -> None:
        """
        Summary
        Ensure one-click agent startup never opts into insecure HTTP when TLS setup fails.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates a temporary repository layout and derived one-click config.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `run_one_click_agent` with mocked network, TLS, port, token, and server startup boundaries.

        Why this exists
        A TLS failure must reduce exposure to loopback rather than silently weakening LAN transport security.
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                config_dir = root / "config"
                config_dir.mkdir()
                (config_dir / "config.json").write_text('{"api": {}}\n', encoding="utf-8")

                with patch.dict(
                    os.environ,
                    {"MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL": "https://stale.example.test:9999"},
                    clear=True,
                ):
                    with patch(
                        "mac_health_checkup.app.backend.one_click._best_effort_lan_ip",
                        autospec=True,
                        return_value="192.168.1.25",
                    ):
                        with patch(
                            "mac_health_checkup.app.backend.one_click._ensure_self_signed_cert",
                            autospec=True,
                            return_value=(False, "openssl unavailable"),
                        ):
                            with patch(
                                "mac_health_checkup.app.backend.one_click._pick_free_port",
                                autospec=True,
                                return_value=43210,
                            ) as pick_port:
                                with patch(
                                    "mac_health_checkup.app.backend.one_click.secrets.token_urlsafe",
                                    autospec=True,
                                    return_value="secure-test-token-with-more-than-32-characters",
                                ):
                                    with patch(
                                        "mac_health_checkup.app.entrypoint.main",
                                        autospec=True,
                                        return_value=0,
                                    ):
                                        code = one_click.run_one_click_agent(repo_root=root)

                    self.assertEqual(code, 0)
                    pick_port.assert_called_once_with("127.0.0.1")
                    derived_path = Path(os.environ["MAC_HEALTH_CHECKUP_CONFIG"])
                    derived = cast(JsonDict, json.loads(derived_path.read_text(encoding="utf-8")))
                    api = derived.get("api")
                    self.assertIsInstance(api, dict)
                    if isinstance(api, dict):
                        self.assertEqual(api.get("bind_host"), "127.0.0.1")
                        self.assertIs(api.get("allow_lan"), False)
                        self.assertIs(api.get("allow_insecure_http_lan"), False)
                        self.assertIs(api.get("tls_enabled"), False)
                    self.assertNotIn("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL", os.environ)
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_run_one_click_agent_falls_back_to_loopback_when_tls_is_unavailable failed: {exc}"
            ) from exc

    def test_run_one_click_agent_keeps_tls_lan_mode_when_material_is_ready(self) -> None:
        """
        Summary
        Ensure one-click agent startup preserves secure LAN pairing when TLS setup succeeds.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates a temporary repository layout and derived one-click config.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `run_one_click_agent` with mocked network, TLS, port, token, and server startup boundaries.

        Why this exists
        Fail-closed fallback must not regress the existing HTTPS LAN path when certificate material is available.
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                config_dir = root / "config"
                config_dir.mkdir()
                (config_dir / "config.json").write_text('{"api": {}}\n', encoding="utf-8")

                with patch.dict(os.environ, {}, clear=True):
                    with patch(
                        "mac_health_checkup.app.backend.one_click._best_effort_lan_ip",
                        autospec=True,
                        return_value="192.168.1.25",
                    ):
                        with patch(
                            "mac_health_checkup.app.backend.one_click._ensure_self_signed_cert",
                            autospec=True,
                            return_value=(True, None),
                        ):
                            with patch(
                                "mac_health_checkup.app.backend.one_click._pick_free_port",
                                autospec=True,
                                return_value=43210,
                            ) as pick_port:
                                with patch(
                                    "mac_health_checkup.app.backend.one_click.secrets.token_urlsafe",
                                    autospec=True,
                                    return_value="secure-test-token-with-more-than-32-characters",
                                ):
                                    with patch(
                                        "mac_health_checkup.app.entrypoint.main",
                                        autospec=True,
                                        return_value=0,
                                    ):
                                        code = one_click.run_one_click_agent(repo_root=root)

                    self.assertEqual(code, 0)
                    pick_port.assert_called_once_with("192.168.1.25")
                    derived_path = Path(os.environ["MAC_HEALTH_CHECKUP_CONFIG"])
                    derived = cast(JsonDict, json.loads(derived_path.read_text(encoding="utf-8")))
                    api = derived.get("api")
                    self.assertIsInstance(api, dict)
                    if isinstance(api, dict):
                        self.assertEqual(api.get("bind_host"), "192.168.1.25")
                        self.assertIs(api.get("allow_lan"), True)
                        self.assertIs(api.get("allow_insecure_http_lan"), False)
                        self.assertIs(api.get("tls_enabled"), True)
                    self.assertEqual(
                        os.environ.get("MAC_HEALTH_CHECKUP_PUBLIC_BASE_URL"),
                        "https://192.168.1.25:43210",
                    )
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_run_one_click_agent_keeps_tls_lan_mode_when_material_is_ready failed: {exc}"
            ) from exc

    def test_run_one_click_agent_enforces_private_modes_on_existing_paths(self) -> None:
        """
        Summary
        Ensure generated secret directories and configuration are owner-only.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates deliberately over-permissive one-click paths and runs the agent with mocked startup boundaries.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `run_one_click_agent`, `_ensure_private_directory`, and `_write_private_text`.

        Why this exists
        Existing paths and an ambient umask must not expose generated TLS material or the API auth token.
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                config_dir = root / "config"
                config_dir.mkdir()
                (config_dir / "config.json").write_text('{"api": {}}\n', encoding="utf-8")

                local_dir = root / ".local"
                tls_dir = local_dir / "tls"
                tls_dir.mkdir(parents=True)
                derived_path = local_dir / "one-click-config.json"
                derived_path.write_text('{"api": {"auth_token": "stale-token"}}\n', encoding="utf-8")
                local_dir.chmod(0o755)
                tls_dir.chmod(0o755)
                derived_path.chmod(0o644)

                with patch.dict(os.environ, {}, clear=True):
                    with (
                        patch(
                            "mac_health_checkup.app.backend.one_click._best_effort_lan_ip",
                            autospec=True,
                            return_value=None,
                        ),
                        patch(
                            "mac_health_checkup.app.backend.one_click._ensure_self_signed_cert",
                            autospec=True,
                            return_value=(False, "openssl unavailable"),
                        ),
                        patch(
                            "mac_health_checkup.app.backend.one_click._pick_free_port",
                            autospec=True,
                            return_value=43210,
                        ),
                        patch(
                            "mac_health_checkup.app.backend.one_click.secrets.token_urlsafe",
                            autospec=True,
                            return_value="secure-test-token-with-more-than-32-characters",
                        ),
                        patch(
                            "mac_health_checkup.app.entrypoint.main",
                            autospec=True,
                            return_value=0,
                        ),
                    ):
                        code = one_click.run_one_click_agent(repo_root=root)

                self.assertEqual(code, 0)
                self.assertEqual(stat.S_IMODE(local_dir.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(tls_dir.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(derived_path.stat().st_mode), 0o600)
                derived = cast(JsonDict, json.loads(derived_path.read_text(encoding="utf-8")))
                api = derived.get("api")
                self.assertIsInstance(api, dict)
                if isinstance(api, dict):
                    self.assertEqual(
                        api.get("auth_token"),
                        "secure-test-token-with-more-than-32-characters",
                    )
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_run_one_click_agent_enforces_private_modes_on_existing_paths failed: {exc}"
            ) from exc

    def test_write_private_text_cleans_up_failed_atomic_replacement(self) -> None:
        """
        Summary
        Ensure a failed private-file replacement leaves no partial token file.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Creates a temporary destination and forces its atomic replacement to fail.

        Error handling
        Asserts the helper raises a contextual `RuntimeError` and cleans its temporary file.

        Ties to other methods
        Exercises `_write_private_text` failure cleanup and existing-file handling.

        Why this exists
        A storage error must preserve the last complete configuration without leaving another token-bearing artifact.
        """
        try:
            with tempfile.TemporaryDirectory() as td:
                local_dir = Path(td) / ".local"
                local_dir.mkdir(mode=0o755)
                destination = local_dir / "one-click-config.json"
                original = '{"api": {"auth_token": "last-complete-token"}}\n'
                destination.write_text(original, encoding="utf-8")
                destination.chmod(0o644)

                with patch(
                    "mac_health_checkup.app.backend.one_click.os.replace",
                    autospec=True,
                    side_effect=OSError("forced replacement failure"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "_write_private_text"):
                        one_click._write_private_text(
                            destination,
                            '{"api": {"auth_token": "new-secret-token"}}\n',
                        )

                self.assertEqual(destination.read_text(encoding="utf-8"), original)
                self.assertEqual(stat.S_IMODE(local_dir.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)
                self.assertEqual(list(local_dir.glob(".one-click-config.json.*.tmp")), [])
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_write_private_text_cleans_up_failed_atomic_replacement failed: {exc}"
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
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
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
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
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
                    """
                    Summary
                    Execute `__enter__` for its module-level responsibility.

                    Inputs
                    None.

                    Outputs
                    Returns `'_Sock'`.

                    Side effects
                    None beyond this method boundary.

                    Error handling
                    Raises contextual errors from `tests/test_one_click_unit.py:__enter__` when this method encounters invalid state or runtime failures.

                    Ties to other methods
                    Used by workflows in `tests/test_one_click_unit.py`.

                    Why this exists
                    Keeps `__enter__` explicit, testable, and maintainable.
                    """
                    return self

                def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
                    """
                    Summary
                    Execute `__exit__` for its module-level responsibility.

                    Inputs
                    exc_type: `object` parameter from the function signature.
                    exc: `object` parameter from the function signature.
                    tb: `object` parameter from the function signature.

                    Outputs
                    None.

                    Side effects
                    None beyond this method boundary.

                    Error handling
                    Raises contextual errors from `tests/test_one_click_unit.py:__exit__` when this method encounters invalid state or runtime failures.

                    Ties to other methods
                    Used by workflows in `tests/test_one_click_unit.py`.

                    Why this exists
                    Keeps `__exit__` explicit, testable, and maintainable.
                    """
                    _ = exc_type
                    _ = exc
                    _ = tb
                    return

                def connect(self, _addr: object) -> None:
                    """
                    Summary
                    Execute `connect` for its module-level responsibility.

                    Inputs
                    _addr: `object` parameter from the function signature.

                    Outputs
                    None.

                    Side effects
                    None beyond this method boundary.

                    Error handling
                    Raises contextual errors from `tests/test_one_click_unit.py:connect` when this method encounters invalid state or runtime failures.

                    Ties to other methods
                    Used by workflows in `tests/test_one_click_unit.py`.

                    Why this exists
                    Keeps `connect` explicit, testable, and maintainable.
                    """
                    return

                def getsockname(self) -> tuple[str, int]:
                    """
                    Summary
                    Execute `getsockname` for its module-level responsibility.

                    Inputs
                    None.

                    Outputs
                    Returns `tuple[str, int]`.

                    Side effects
                    None beyond this method boundary.

                    Error handling
                    Raises contextual errors from `tests/test_one_click_unit.py:getsockname` when this method encounters invalid state or runtime failures.

                    Ties to other methods
                    Used by workflows in `tests/test_one_click_unit.py`.

                    Why this exists
                    Keeps `getsockname` explicit, testable, and maintainable.
                    """
                    return ("127.0.0.1", 0)

            with patch(
                "mac_health_checkup.app.backend.one_click.socket.socket", autospec=True, return_value=_Sock()
            ):
                self.assertIsNone(one_click._best_effort_lan_ip())
        except (
            AssertionError,
            RuntimeError,
            ValueError,
            TypeError,
            AttributeError,
            KeyError,
            IndexError,
            OSError,
        ) as exc:
            raise AssertionError(
                f"{MODULE_PATH}:OneClickUnitTests.test_best_effort_lan_ip_returns_none_on_loopback failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
