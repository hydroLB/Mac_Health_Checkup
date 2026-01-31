from __future__ import annotations

import json
import unittest
import urllib.error
import urllib.request

from mac_health_checkup.app.backend.server import SnapshotApiServer, pick_free_port, wait_until_ready
from mac_health_checkup.app.gui.sections.types import SectionHost
from mac_health_checkup.core.config import ApiConfig
from mac_health_checkup.core.types import JsonDict

MODULE_PATH = "tests/test_snapshot_server.py"


def _handler_ok(host: SectionHost) -> JsonDict:
    """
    Purpose: Provide a deterministic handler for server tests.
    Ties: Used by SnapshotServerTests.
    Inputs: host receives field output.
    Outputs: Minimal diagnostics dict.
    Side effects: Writes field output.
    Why: Avoids invoking macOS system commands in unit tests.
    """
    host.set_field("test", "hello")
    return {"ok": True}


class SnapshotServerTests(unittest.TestCase):
    """
    Purpose: Validate the local snapshot API server endpoints and auth behavior.
    Ties: Exercises SnapshotApiServer and the HTTP handler logic.
    Inputs: None.
    Outputs: Assertions on endpoint responses and JSON payload shape.
    Side effects: Binds a local TCP port and performs HTTP requests.
    Why: Protects the iOS client contract and prevents regressions in token auth.
    """

    def test_snapshot_endpoint_auth_and_shape(self) -> None:
        """
        Purpose: Verify the snapshot endpoint requires auth and returns JSON.
        Ties: Validates SnapshotApiServer and request handler behavior.
        Inputs: None.
        Outputs: Assertions on status codes and JSON schema fields.
        Side effects: Binds a local TCP port and performs HTTP requests.
        Why: Ensures the iOS client API contract is stable and protected by a token.
        """
        server: SnapshotApiServer | None = None
        try:
            try:
                port = pick_free_port("127.0.0.1")
            except RuntimeError as exc:
                if "Operation not permitted" in str(exc):
                    self.skipTest("Socket bind not permitted in this environment")
                raise
            api = ApiConfig(
                enabled=True,
                bind_host="127.0.0.1",
                port=port,
                allow_lan=False,
                allow_insecure_http_lan=False,
                tls_enabled=False,
                tls_cert_path=".local/tls/agent-cert.pem",
                tls_key_path=".local/tls/agent-key.pem",
                auth_token="unit-test-token-0123456789-abcdefghijklmnopqrstuvwxyz",
                min_auth_token_length=24,
                blocked_auth_tokens=["change-me", "changeme", "password", "token"],
                rate_limit_requests_per_minute=120,
                max_auth_failures_per_minute=10,
                auth_ban_seconds=60,
                request_timeout_sec=5,
            )
            server = SnapshotApiServer({"test": _handler_ok}, api)
            server.start()
            self.assertTrue(wait_until_ready(server.url(), timeout_sec=3))

            def _fetch(path: str, token: str | None) -> tuple[int, dict[str, object]]:
                url = f"{server.url()}{path}"
                req = urllib.request.Request(url, method="GET")
                if token is not None:
                    req.add_header("Authorization", f"Bearer {token}")
                try:
                    with urllib.request.urlopen(req, timeout=2) as resp:
                        return int(resp.status), json.loads(resp.read().decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    body = exc.read().decode("utf-8")
                    return int(exc.code), json.loads(body)

            status, payload = _fetch("/v1/health", token=None)
            self.assertEqual(status, 200)
            self.assertTrue(bool(payload.get("ok")))

            status, payload = _fetch("/v1/snapshot", token=None)
            self.assertEqual(status, 401)
            self.assertFalse(bool(payload.get("ok")))

            status, payload = _fetch(
                "/v1/snapshot", token="unit-test-token-0123456789-abcdefghijklmnopqrstuvwxyz"
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload.get("schema_version"), 2)
            self.assertIsInstance(payload.get("sections"), list)
            self.assertIsInstance(payload.get("theme"), dict)
            self.assertIsInstance(payload.get("section_catalog"), list)

            status, payload = _fetch("/v1/section?key=test", token=None)
            self.assertEqual(status, 401)
            self.assertFalse(bool(payload.get("ok")))

            status, payload = _fetch(
                "/v1/section",
                token="unit-test-token-0123456789-abcdefghijklmnopqrstuvwxyz",
            )
            self.assertEqual(status, 400)
            self.assertFalse(bool(payload.get("ok")))
            self.assertEqual(payload.get("error"), "missing_section_key")

            status, payload = _fetch(
                "/v1/section?key=test",
                token="unit-test-token-0123456789-abcdefghijklmnopqrstuvwxyz",
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload.get("schema_version"), 2)
            self.assertIsInstance(payload.get("sections"), list)
            sections = payload.get("sections")
            self.assertTrue(isinstance(sections, list) and len(sections) == 1)
            if isinstance(sections, list) and sections:
                first = sections[0]
                self.assertTrue(isinstance(first, dict))
                if isinstance(first, dict):
                    self.assertEqual(first.get("key"), "test")
        except unittest.SkipTest:
            raise
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:SnapshotServerTests.test_snapshot_endpoint_auth_and_shape failed: {exc}"
            ) from exc
        finally:
            if server is not None:
                try:
                    server.stop()
                except Exception:
                    pass


if __name__ == "__main__":
    unittest.main()
