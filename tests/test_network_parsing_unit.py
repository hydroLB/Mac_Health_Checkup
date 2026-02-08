from __future__ import annotations

import unittest
from unittest.mock import patch

from mac_health_checkup.diagnostics import network as net

MODULE_PATH = "tests/test_network_parsing_unit.py"


class NetworkParsingUnitTests(unittest.TestCase):
    """
    Summary
    Validate network parsing helpers using mocked command outputs.

    Inputs
    None.

    Outputs
    Assertions on parsed interface, Wi-Fi metrics, and throughput calculations.

    Side effects
    Patches `safe_run` and time functions to avoid real networking commands.

    Error handling
    Raises AssertionError with module and method context on failures.

    Ties to other methods
    Exercises `mac_health_checkup/diagnostics/network.py`.

    Why this exists
    The network section should remain useful even when networkQuality is unavailable, and parsers must be stable.
    """

    def setUp(self) -> None:
        try:
            net.NetworkQualityDiagnostics._last_bytes = None
        except Exception as exc:
            raise RuntimeError(f"{MODULE_PATH}:NetworkParsingUnitTests.setUp failed: {exc}") from exc

    def test_interface_priority_and_try_int(self) -> None:
        """
        Summary
        Ensure interface ranking prefers low-numbered en* and integer parsing is conservative.

        Inputs
        None.

        Outputs
        None.

        Side effects
        None.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_interface_priority` and `_try_int`.

        Why this exists
        Stable interface selection prevents flapping between inactive adapters.
        """
        try:
            self.assertEqual(net._interface_priority("en0"), 0)
            self.assertEqual(net._interface_priority("en10"), 10)
            self.assertEqual(net._interface_priority("awdl0"), 999)
            self.assertEqual(net._try_int(" 42 "), 42)
            self.assertIsNone(net._try_int("nope"))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:NetworkParsingUnitTests.test_interface_priority_and_try_int failed: {exc}"
            ) from exc

    def test_rate_mbps_from_bytes_requires_two_samples(self) -> None:
        """
        Summary
        Ensure throughput computation is based on two samples and a minimum time delta.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches time.time.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `_rate_mbps_from_bytes`.

        Why this exists
        Avoids reporting unstable spikes during fast UI refresh intervals.
        """
        try:
            with patch(
                "mac_health_checkup.diagnostics.network.time.time", autospec=True, side_effect=[0.0, 1.0]
            ):
                rx0, tx0 = net._rate_mbps_from_bytes(1000, 2000)
                self.assertEqual((rx0, tx0), (None, None))
                rx1, tx1 = net._rate_mbps_from_bytes(1010000, 2020000)
                self.assertIsNotNone(rx1)
                self.assertIsNotNone(tx1)
                if rx1 is not None and tx1 is not None:
                    self.assertGreater(rx1, 0.0)
                    self.assertGreater(tx1, 0.0)
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:NetworkParsingUnitTests.test_rate_mbps_from_bytes_requires_two_samples failed: {exc}"
            ) from exc

    def test_fetch_uncached_parses_command_outputs(self) -> None:
        """
        Summary
        Ensure the uncached fetch path stitches together interface, wifi, bytes, and networkQuality fields.

        Inputs
        None.

        Outputs
        None.

        Side effects
        Patches safe_run to return deterministic outputs.

        Error handling
        Raises AssertionError with context on failures.

        Ties to other methods
        Exercises `NetworkQualityDiagnostics._fetch_uncached`.

        Why this exists
        This is the core network collector logic used by the UI and snapshot backend.
        """
        try:

            def _fake_safe_run(
                cmd: object, context: str, *, allow_sudo: bool, timeout: int | None
            ) -> tuple[str | None, str | None]:
                _ = allow_sudo
                _ = timeout
                cmd_list = list(cmd) if isinstance(cmd, (list, tuple)) else []
                if cmd_list[:3] == ["route", "-n", "get"]:
                    return "   interface: en0\n", None
                if cmd_list[:2] == ["ifconfig", "en0"]:
                    return "status: active\n inet 192.168.1.10 netmask 0xffffff00\n", None
                if cmd_list[:2] == ["ifconfig", "-l"]:
                    return "en0 en1 awdl0 lo0", None
                if cmd_list[:2] == ["ifconfig", "en1"]:
                    return "status: inactive\n", None
                if cmd_list and isinstance(cmd_list[0], str) and cmd_list[0].endswith("/airport"):
                    return "     SSID: MyWifi\n agrCtlRSSI: -50\n lastTxRate: 867\n", None
                if cmd_list[:2] == ["netstat", "-ibn"]:
                    return (
                        "Name Mtu Network Address Ipkts Ierrs Opkts Oerrs Coll Ibytes Obytes\n"
                        "en0 1500 link#4 xx 0 0 0 0 0 1000 2000\n"
                    ), None
                if cmd_list[:2] == ["networkQuality", "-s"]:
                    return (
                        "Downlink capacity: 100.0 Mbps\nUplink capacity: 20.0 Mbps\nInterface: en0\n"
                    ), None
                return None, "unexpected"

            with patch(
                "mac_health_checkup.diagnostics.network.safe_run", autospec=True, side_effect=_fake_safe_run
            ):
                data = net.NetworkQualityDiagnostics._fetch_uncached()
                self.assertEqual(data.get("interface"), "en0")
                self.assertEqual(data.get("ipv4"), "192.168.1.10")
                self.assertEqual(data.get("ssid"), "MyWifi")
                self.assertEqual(data.get("rssi_dbm"), -50)
                self.assertEqual(data.get("tx_rate_mbps"), 867)
                self.assertEqual(data.get("down_mbps"), 100.0)
                self.assertEqual(data.get("up_mbps"), 20.0)
                self.assertTrue(data.get("ok"))
        except Exception as exc:
            raise AssertionError(
                f"{MODULE_PATH}:NetworkParsingUnitTests.test_fetch_uncached_parses_command_outputs failed: {exc}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
