from __future__ import annotations

import re
import time

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error, safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch, get_diagnostics_logger, new_context

MODULE_PATH = "mac_health_checkup/diagnostics/network.py"

_DOWN_RE = re.compile(r"Downlink capacity:\s*([0-9.]+)\s*Mbps", re.IGNORECASE)
_UP_RE = re.compile(r"Uplink capacity:\s*([0-9.]+)\s*Mbps", re.IGNORECASE)
_INTERFACE_RE = re.compile(r"Interface:\s*(\w+)")
_ROUTE_IFACE_RE = re.compile(r"^\s*interface:\s*(\w+)\s*$", re.MULTILINE)
_AIRPORT_KV_RE = re.compile(r"^\s*([A-Za-z0-9]+)\s*:\s*(.+?)\s*$")
_IFCONFIG_INET_RE = re.compile(r"^\s*inet\s+([0-9.]+)\s+", re.MULTILINE)


class NetworkQualityDiagnostics:
    """
    Summary
    Collect network diagnostics with fast local metrics and optional networkQuality capacity.

    Inputs
    None. Executes local networking commands and may run networkQuality.

    Outputs
    Dict with interface, IP, Wi‑Fi stats, and optional capacity numbers.

    Side effects
    Executes subprocess commands.

    Error handling
    Returns partial signals when some commands are unavailable; raises `RuntimeError` with module and method context
    when parsing fails unexpectedly.

    Ties to other methods
    Used by the Network section in the GUI.

    Why this exists
    The UI needs reliable, instant network visibility even when Internet speed tests are slow or blocked.
    """

    _cache = Cache(get_config().timeouts.network_cache_ttl)
    _last_bytes: tuple[float, int, int] | None = None

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch network quality metrics with caching.

        Inputs
        None.

        Outputs
        Dict with network metrics.

        Side effects
        Executes networkQuality when the cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching fails unexpectedly.

        Ties to other methods
        Used by Network section handler.

        Why this exists
        Avoids running networkQuality too frequently.
        """
        try:
            return cached_fetch(
                NetworkQualityDiagnostics._cache, "network", NetworkQualityDiagnostics._fetch_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "NetworkQualityDiagnostics.fetch", "Failed to fetch network", exc)
            ) from exc

    @staticmethod
    def _fetch_uncached() -> JsonDict:
        """
        Summary
        Fetch network diagnostics without caching.

        Inputs
        None.

        Outputs
        Dict with network diagnostics and optional networkQuality capacity.

        Side effects
        Executes subprocess commands.

        Error handling
        Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Separates IO from caching logic for testing and keeps fast paths deterministic.
        """
        try:
            logger = get_diagnostics_logger()
            context = new_context("NetworkQualityDiagnostics")
            iface, ipv4 = _primary_interface_and_ipv4()
            wifi = _airport_info()
            ssid = wifi.get("ssid")
            ssid_str = ssid if isinstance(ssid, str) else None
            rssi_dbm = wifi.get("rssi_dbm")
            rssi_int = rssi_dbm if isinstance(rssi_dbm, int) else None
            tx_rate_mbps = wifi.get("tx_rate_mbps")
            tx_rate_int = tx_rate_mbps if isinstance(tx_rate_mbps, int) else None
            rx_bytes, tx_bytes = _interface_bytes(iface) if iface else (None, None)
            rx_mbps, tx_mbps = _rate_mbps_from_bytes(rx_bytes, tx_bytes)

            capacity_down = None
            capacity_up = None
            capacity_iface = None
            timeout = get_config().timeouts.network_quality_timeout
            out, err = safe_run(
                ["networkQuality", "-s"], context="networkQuality", allow_sudo=False, timeout=timeout
            )
            if out:
                capacity_down = _extract_float(_DOWN_RE, out)
                capacity_up = _extract_float(_UP_RE, out)
                capacity_iface = _extract_str(_INTERFACE_RE, out)
            else:
                logger.info(
                    "networkQuality unavailable",
                    event="network_quality_unavailable",
                    context=context,
                    payload={"error": err or ""},
                )

            return {
                "interface": iface or capacity_iface,
                "ipv4": ipv4,
                "ssid": ssid_str,
                "rssi_dbm": rssi_int,
                "tx_rate_mbps": tx_rate_int,
                "rx_mbps": rx_mbps,
                "tx_mbps": tx_mbps,
                "down_mbps": capacity_down,
                "up_mbps": capacity_up,
                "ok": True,
            }
        except (RuntimeError, ValueError, TypeError, OSError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH, "NetworkQualityDiagnostics._fetch_uncached", "Network parsing failed", exc
                )
            ) from exc


def _extract_float(pattern: re.Pattern[str], text: str) -> float | None:
    """
    Summary
    Extract a float from regex match.

    Inputs
    pattern: Regex pattern.
    text: Text to search.

    Outputs
    Float value or None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by `NetworkQualityDiagnostics` parsing.

    Why this exists
    Keeps float extraction logic consistent.
    """
    try:
        match = pattern.search(text)
        if not match:
            return None
        return float(match.group(1))
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_extract_float", "Failed to parse float", exc)) from exc


def _extract_str(pattern: re.Pattern[str], text: str) -> str | None:
    """
    Summary
    Extract a string from regex match.

    Inputs
    pattern: Regex pattern.
    text: Text to search.

    Outputs
    String value or None.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when parsing fails unexpectedly.

    Ties to other methods
    Used by `NetworkQualityDiagnostics` parsing.

    Why this exists
    Keeps string extraction logic consistent.
    """
    try:
        match = pattern.search(text)
        if not match:
            return None
        return match.group(1)
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_extract_str", "Failed to parse string", exc)) from exc


def _default_route_interface() -> str | None:
    """
    Summary
    Determine the primary outbound interface from the default route.

    Inputs
    None.

    Outputs
    Interface name like "en0" or None.

    Side effects
    Executes route(8).

    Error handling
    Raises `RuntimeError` with module and method context when command execution or parsing fails unexpectedly.

    Ties to other methods
    Used by `NetworkQualityDiagnostics` fast path.

    Why this exists
    The default route is the most reliable way to identify the interface in use without guessing.
    """
    try:
        out, _err = safe_run(
            ["route", "-n", "get", "default"], context="route_default", allow_sudo=False, timeout=3
        )
        if not out:
            return None
        match = _ROUTE_IFACE_RE.search(out)
        return match.group(1) if match else None
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_default_route_interface", "Failed to detect default interface", exc)
        ) from exc


def _primary_interface_and_ipv4() -> tuple[str | None, str | None]:
    """
    Summary
    Determine the primary active interface and its IPv4 address.

    Inputs
    None.

    Outputs
    Tuple (interface, ipv4) or (None, None).

    Side effects
    Executes route(8) and ifconfig(8).

    Error handling
    Raises `RuntimeError` with module and method context when command execution or parsing fails unexpectedly.

    Ties to other methods
    Used by `NetworkQualityDiagnostics` as a fast, non-privileged path.

    Why this exists
    Some environments restrict route sockets; ifconfig parsing provides a reliable fallback for the UI.
    """
    try:
        iface = _default_route_interface()
        if iface:
            out, _err = safe_run(["ifconfig", iface], context="ifconfig_iface", allow_sudo=False, timeout=2)
            if out:
                match = _IFCONFIG_INET_RE.search(out)
                if match:
                    return iface, match.group(1)

        out, _err = safe_run(["ifconfig", "-l"], context="ifconfig_list", allow_sudo=False, timeout=2)
        if not out:
            return None, None
        candidates = [item.strip() for item in out.split() if item.strip().startswith("en")]
        candidates.sort(key=_interface_priority)
        for candidate in candidates:
            block, _err = safe_run(
                ["ifconfig", candidate], context="ifconfig_probe", allow_sudo=False, timeout=2
            )
            if not block:
                continue
            if "status: active" not in block.lower():
                continue
            match = _IFCONFIG_INET_RE.search(block)
            if match:
                return candidate, match.group(1)
        return None, None
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_primary_interface_and_ipv4", "Failed to detect interface/IP", exc)
        ) from exc


def _interface_priority(name: str) -> int:
    """
    Summary
    Rank interfaces so primary Ethernet and Wi‑Fi interfaces are preferred.

    Inputs
    name: Interface name.

    Outputs
    Integer priority (lower is better).

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when ranking fails unexpectedly.

    Ties to other methods
    Used by `_primary_interface_and_ipv4`.

    Why this exists
    Systems often have many `en*` interfaces; prefer en0/en1 to avoid choosing inactive virtual adapters.
    """
    try:
        lower = (name or "").lower()
        match = re.fullmatch(r"en(\d+)", lower)
        if match:
            idx = int(match.group(1))
            return idx
        return 999
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_interface_priority", "Failed to rank interface", exc)
        ) from exc


def _airport_info() -> dict[str, object | None]:
    """
    Summary
    Read Wi‑Fi SSID, RSSI, and transmit rate when available.

    Inputs
    None.

    Outputs
    Dict with ssid, rssi_dbm, tx_rate_mbps (values may be None).

    Side effects
    Executes the private airport helper.

    Error handling
    Raises `RuntimeError` with module and method context when command execution or parsing fails unexpectedly.

    Ties to other methods
    Used by `NetworkQualityDiagnostics`.

    Why this exists
    RSSI and transmit rate are critical for diagnosing Wi‑Fi issues without running speed tests.
    """
    try:
        airport = "/System/Library/PrivateFrameworks/Apple80211.framework/Versions/Current/Resources/airport"
        out, _err = safe_run([airport, "-I"], context="airport", allow_sudo=False, timeout=2)
        if not out:
            return {"ssid": None, "rssi_dbm": None, "tx_rate_mbps": None}
        values: dict[str, str] = {}
        for line in out.splitlines():
            match = _AIRPORT_KV_RE.match(line)
            if not match:
                continue
            values[match.group(1).strip()] = match.group(2).strip()
        ssid = values.get("SSID")
        rssi_dbm = _try_int(values.get("agrCtlRSSI"))
        tx_rate_mbps = _try_int(values.get("lastTxRate"))
        return {"ssid": ssid, "rssi_dbm": rssi_dbm, "tx_rate_mbps": tx_rate_mbps}
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_airport_info", "Failed to read Wi-Fi metrics", exc)
        ) from exc


def _interface_bytes(interface: str | None) -> tuple[int | None, int | None]:
    """
    Summary
    Read cumulative receive and transmit bytes for an interface.

    Inputs
    interface: Interface name or None.

    Outputs
    Tuple (rx_bytes, tx_bytes) or (None, None).

    Side effects
    Executes netstat(1).

    Error handling
    Raises `RuntimeError` with module and method context when command execution or parsing fails unexpectedly.

    Ties to other methods
    Used by `NetworkQualityDiagnostics` to compute rates between refreshes.

    Why this exists
    Byte counters enable deterministic throughput graphs without external services.
    """
    try:
        if not interface:
            return None, None
        out, _err = safe_run(["netstat", "-ibn"], context="netstat_ibn", allow_sudo=False, timeout=3)
        if not out:
            return None, None
        header: list[str] | None = None
        for line in out.splitlines():
            parts = [p for p in line.split() if p]
            if not parts:
                continue
            if parts[0].lower() == "name":
                header = parts
                continue
            if header is None:
                continue
            if parts[0] != interface:
                continue
            indices = {name.lower(): idx for idx, name in enumerate(header)}
            rx_idx = indices.get("ibytes")
            tx_idx = indices.get("obytes")
            if rx_idx is None or tx_idx is None:
                return None, None
            if rx_idx >= len(parts) or tx_idx >= len(parts):
                continue
            rx = _try_int(parts[rx_idx])
            tx = _try_int(parts[tx_idx])
            if rx is not None and tx is not None:
                return rx, tx
        return None, None
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_interface_bytes", "Failed to read interface bytes", exc)
        ) from exc


def _rate_mbps_from_bytes(rx_bytes: int | None, tx_bytes: int | None) -> tuple[float | None, float | None]:
    """
    Summary
    Compute Mbps rates from cumulative byte counters.

    Inputs
    rx_bytes: Receive byte counter.
    tx_bytes: Transmit byte counter.

    Outputs
    Tuple (rx_mbps, tx_mbps) or (None, None).

    Side effects
    Mutates an internal last-sample cache.

    Error handling
    Raises `RuntimeError` with module and method context when computation fails unexpectedly.

    Ties to other methods
    Used by `NetworkQualityDiagnostics`.

    Why this exists
    Presents a live throughput estimate without requiring external network tests.
    """
    try:
        if rx_bytes is None or tx_bytes is None:
            NetworkQualityDiagnostics._last_bytes = None
            return None, None
        now = time.time()
        last = NetworkQualityDiagnostics._last_bytes
        NetworkQualityDiagnostics._last_bytes = (now, rx_bytes, tx_bytes)
        if last is None:
            return None, None
        last_t, last_rx, last_tx = last
        dt = now - last_t
        if dt <= 0.2:
            return None, None
        rx_rate_mbps = max(0.0, (rx_bytes - last_rx) * 8.0 / dt / 1_000_000.0)
        tx_rate_mbps = max(0.0, (tx_bytes - last_tx) * 8.0 / dt / 1_000_000.0)
        return rx_rate_mbps, tx_rate_mbps
    except (RuntimeError, ValueError, TypeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_rate_mbps_from_bytes", "Failed to compute Mbps", exc)
        ) from exc


def _try_int(value: str | None) -> int | None:
    """
    Summary
    Parse an integer from a string safely.

    Inputs
    value: Value string or None.

    Outputs
    Integer value or None.

    Side effects
    None.

    Error handling
    Never raises; returns None on malformed values.

    Ties to other methods
    Used by network parsing helpers.

    Why this exists
    Keeps parsing helpers resilient to missing or malformed command output.
    """
    try:
        if value is None:
            return None
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None
