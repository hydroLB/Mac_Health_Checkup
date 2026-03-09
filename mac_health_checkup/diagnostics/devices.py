from __future__ import annotations

import re

from mac_health_checkup.core.config import get_config
from mac_health_checkup.core.types import JsonDict
from mac_health_checkup.core.utils import format_error, parse_usb_tree_items, safe_run
from mac_health_checkup.diagnostics.base import Cache, cached_fetch

MODULE_PATH = "mac_health_checkup/diagnostics/devices.py"

BT_CONNECTED_RE = re.compile(r"^\s+(.+?):\s+Connected:\s+Yes", re.MULTILINE)
NETWORK_HARDWARE_RE = re.compile(r"Hardware:\s+(.+)")
THUNDERBOLT_HEADER_RE = re.compile(r"^\s{8,}([^:\n]+):\s*$")
_IOREG_PRODUCT_RE = re.compile(r'^\s*(?:\|\s*)?"Product"\s*=\s*"(?P<value>[^"]+)"\s*$')
_IOREG_USAGE_PAGE_RE = re.compile(r'^\s*(?:\|\s*)?"PrimaryUsagePage"\s*=\s*(?P<value>\d+)\s*$')
_IOREG_USAGE_RE = re.compile(r'^\s*(?:\|\s*)?"PrimaryUsage"\s*=\s*(?P<value>\d+)\s*$')
_IOREG_TRANSPORT_RE = re.compile(r'^\s*(?:\|\s*)?"Transport"\s*=\s*"(?P<value>[^"]+)"\s*$')


class DeviceScanner:
    """
    Summary
    Scan connected devices across buses.

    Inputs
    None. Reads system_profiler outputs.

    Outputs
    Device labels grouped by source or flattened into a single list.

    Side effects
    Executes system_profiler commands.

    Error handling
    Returns empty lists when command output is missing; raises `RuntimeError` with module and method context when
    parsing fails unexpectedly.

    Ties to other methods
    Used by Devices and Ports sections.

    Why this exists
    Provides a unified view of connected devices.
    """

    _cache = Cache(get_config().timeouts.cache_ttl)

    @staticmethod
    def scan_by_bus() -> JsonDict:
        """
        Summary
        Scan devices grouped by bus or source with caching.

        Inputs
        None.

        Outputs
        Dict with keys usb, bluetooth, thunderbolt, network, and devices.

        Side effects
        Executes system_profiler commands when cache is stale.

        Error handling
        Raises `RuntimeError` with module and method context when caching or scanning fails unexpectedly.

        Ties to other methods
        Used by the Devices section to render a richer table without re-running expensive probes.

        Why this exists
        The UI needs to show where a device is connected, and grouping enables a settings-style presentation.
        """
        try:
            return cached_fetch(
                DeviceScanner._cache, "device_scan_by_bus", DeviceScanner._scan_by_bus_uncached
            )
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DeviceScanner.scan_by_bus", "Failed to scan devices by bus", exc)
            ) from exc

    @staticmethod
    def _scan_by_bus_uncached() -> JsonDict:
        """
        Summary
        Scan devices grouped by bus or source without caching.

        Inputs
        None.

        Outputs
        Dict with per-bus device lists and a combined `devices` list.

        Side effects
        Executes system_profiler commands.

        Error handling
        Raises `RuntimeError` with module and method context when scanning fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Keeps IO isolated from caching for testing and consistent behavior.
        """
        try:
            usb = DeviceScanner.scan_usb()
            bluetooth = DeviceScanner.scan_bluetooth()
            thunderbolt = DeviceScanner.scan_thunderbolt()
            network = DeviceScanner.scan_network()
            combined: list[str] = _dedupe(usb + bluetooth + thunderbolt + network)
            return {
                "usb": usb,
                "bluetooth": bluetooth,
                "thunderbolt": thunderbolt,
                "network": network,
                "devices": combined,
            }
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(
                    MODULE_PATH,
                    "DeviceScanner._scan_by_bus_uncached",
                    "Failed to scan grouped devices",
                    exc,
                )
            ) from exc

    @staticmethod
    def scan_all() -> list[str]:
        """
        Summary
        Scan all buses and return combined device labels.

        Inputs
        None.

        Outputs
        List of device label strings.

        Side effects
        Executes system_profiler.

        Error handling
        Raises `RuntimeError` with module and method context when scanning fails unexpectedly.

        Ties to other methods
        Used by Devices section handler.

        Why this exists
        Provides a single call to gather connected devices.
        """
        try:
            data = cached_fetch(DeviceScanner._cache, "device_scan", DeviceScanner._scan_uncached)
            value = data.get("devices")
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                return value
            return []
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DeviceScanner.scan_all", "Failed to scan devices", exc)
            ) from exc

    @staticmethod
    def _scan_uncached() -> JsonDict:
        """
        Summary
        Scan all buses without caching.

        Inputs
        None.

        Outputs
        Dict with devices list.

        Side effects
        Executes system_profiler.

        Error handling
        Raises `RuntimeError` with module and method context when scanning fails unexpectedly.

        Ties to other methods
        Used by `cached_fetch`.

        Why this exists
        Keeps IO separate from cache logic for testing.
        """
        try:
            devices = []
            devices.extend(DeviceScanner.scan_usb())
            devices.extend(DeviceScanner.scan_bluetooth())
            devices.extend(DeviceScanner.scan_thunderbolt())
            devices.extend(DeviceScanner.scan_network())
            return {"devices": _dedupe(devices)}
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DeviceScanner._scan_uncached", "Failed to scan devices", exc)
            ) from exc

    @staticmethod
    def scan_usb() -> list[str]:
        """
        Summary
        Scan USB devices from system_profiler.

        Inputs
        None.

        Outputs
        List of USB device labels.

        Side effects
        Executes system_profiler.

        Error handling
        Returns an empty list when output is missing; raises `RuntimeError` with module and method context when parsing
        fails unexpectedly.

        Ties to other methods
        Used by `DeviceScanner.scan_all` and `PortsDiagnostics`.

        Why this exists
        Provides USB device discovery.
        """
        try:
            out, _err = safe_run(["system_profiler", "SPUSBDataType"], context="usb_scan", allow_sudo=False)
            if not out:
                return []
            items = parse_usb_tree_items(out)
            labels: list[str] = []
            for item in items:
                label = item.get("label")
                if isinstance(label, str) and label:
                    labels.append(label)
            return _dedupe(labels)
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DeviceScanner.scan_usb", "Failed to scan USB", exc)
            ) from exc

    @staticmethod
    def scan_bluetooth() -> list[str]:
        """
        Summary
        Scan connected Bluetooth devices.

        Inputs
        None.

        Outputs
        List of Bluetooth device labels.

        Side effects
        Executes system_profiler.

        Error handling
        Returns an empty list when output is missing; raises `RuntimeError` with module and method context when parsing
        fails unexpectedly.

        Ties to other methods
        Used by `DeviceScanner.scan_all`.

        Why this exists
        Provides Bluetooth device discovery.
        """
        try:
            out, _err = safe_run(
                ["system_profiler", "SPBluetoothDataType"], context="bt_scan", allow_sudo=False
            )
            if not out:
                return []
            return _dedupe([match.group(1).strip() for match in BT_CONNECTED_RE.finditer(out)])
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DeviceScanner.scan_bluetooth", "Failed to scan Bluetooth", exc)
            ) from exc

    @staticmethod
    def scan_thunderbolt() -> list[str]:
        """
        Summary
        Scan Thunderbolt devices.

        Inputs
        None.

        Outputs
        List of Thunderbolt device labels.

        Side effects
        Executes system_profiler.

        Error handling
        Returns an empty list when output is missing; raises `RuntimeError` with module and method context when parsing
        fails unexpectedly.

        Ties to other methods
        Used by `DeviceScanner.scan_all`.

        Why this exists
        Provides Thunderbolt device discovery.
        """
        try:
            out, _err = safe_run(
                ["system_profiler", "SPThunderboltDataType"], context="tb_scan", allow_sudo=False
            )
            if not out:
                return []
            labels = [match.group(1).strip() for match in THUNDERBOLT_HEADER_RE.finditer(out)]
            return _dedupe(labels)
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DeviceScanner.scan_thunderbolt", "Failed to scan Thunderbolt", exc)
            ) from exc

    @staticmethod
    def scan_network() -> list[str]:
        """
        Summary
        Scan network hardware devices.

        Inputs
        None.

        Outputs
        List of network hardware labels.

        Side effects
        Executes system_profiler.

        Error handling
        Returns an empty list when output is missing; raises `RuntimeError` with module and method context when parsing
        fails unexpectedly.

        Ties to other methods
        Used by `DeviceScanner.scan_all`.

        Why this exists
        Provides network device discovery.
        """
        try:
            out, _err = safe_run(
                ["system_profiler", "SPNetworkDataType"], context="net_scan", allow_sudo=False
            )
            if not out:
                return []
            return _dedupe([match.group(1).strip() for match in NETWORK_HARDWARE_RE.finditer(out)])
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "DeviceScanner.scan_network", "Failed to scan network", exc)
            ) from exc


class PortsDiagnostics:
    """
    Summary
    Collect connected USB port devices.

    Inputs
    None.

    Outputs
    Dict with devices list.

    Side effects
    Executes system_profiler.

    Error handling
    Raises `RuntimeError` with module and method context when device scanning fails unexpectedly.

    Ties to other methods
    Used by Ports section in the GUI.

    Why this exists
    Provides a focused USB ports view.
    """

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch connected USB device labels.

        Inputs
        None.

        Outputs
        Dict with devices list.

        Side effects
        Executes system_profiler.

        Error handling
        Raises `RuntimeError` with module and method context when scanning fails unexpectedly.

        Ties to other methods
        Used by Ports section handler.

        Why this exists
        Keeps USB port diagnostics in a single place.
        """
        try:
            return {"devices": DeviceScanner.scan_usb()}
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "PortsDiagnostics.fetch", "Failed to fetch ports", exc)
            ) from exc


class InputDiagnostics:
    """
    Summary
    Collect connected input device labels.

    Inputs
    None.

    Outputs
    Dict with details list.

    Side effects
    Executes system_profiler or ioreg, depending on availability.

    Error handling
    Returns empty lists when signals are missing; raises `RuntimeError` with module and method context when parsing
    fails unexpectedly.

    Ties to other methods
    Used by Input section in the GUI.

    Why this exists
    Provides a focused input device view.
    """

    _input_keywords = ("keyboard", "trackpad", "mouse", "touch bar")

    @staticmethod
    def fetch() -> JsonDict:
        """
        Summary
        Fetch input device labels.

        Inputs
        None.

        Outputs
        Dict with input device details.

        Side effects
        May execute ioreg and system_profiler depending on available signals.

        Error handling
        Raises `RuntimeError` with module and method context when scanning fails unexpectedly.

        Ties to other methods
        Used by Input section handler.

        Why this exists
        Keeps input device parsing centralized.
        """
        try:
            hid_inputs = _scan_hid_inputs()
            if hid_inputs:
                return {"details": hid_inputs, "source": "ioreg_hid"}
            devices = DeviceScanner.scan_all()
            inputs = [label for label in devices if _is_input_device(label)]
            return {"details": inputs, "source": "system_profiler"}
        except (RuntimeError, ValueError, TypeError, OSError, KeyError) as exc:
            raise RuntimeError(
                format_error(MODULE_PATH, "InputDiagnostics.fetch", "Failed to fetch inputs", exc)
            ) from exc


def _is_input_device(label: str) -> bool:
    """
    Summary
    Determine if a label represents an input device.

    Inputs
    label: Device name.

    Outputs
    True when the label looks like an input device.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when classification fails unexpectedly.

    Ties to other methods
    Used by `InputDiagnostics`.

    Why this exists
    Filters device lists to just input related hardware.
    """
    try:
        lower = label.lower()
        return any(keyword in lower for keyword in InputDiagnostics._input_keywords)
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_is_input_device", "Failed to classify input", exc)
        ) from exc


def _dedupe(values: list[str]) -> list[str]:
    """
    Summary
    Deduplicate labels while preserving order.

    Inputs
    values: List of strings.

    Outputs
    Deduplicated list.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when deduping fails unexpectedly.

    Ties to other methods
    Used by `DeviceScanner` parsing helpers.

    Why this exists
    Keeps device lists stable for UI rendering.
    """
    try:
        seen: set[str] = set()
        output: list[str] = []
        for value in values:
            if value and value not in seen:
                output.append(value)
                seen.add(value)
        return output
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(format_error(MODULE_PATH, "_dedupe", "Failed to dedupe list", exc)) from exc


def _scan_hid_inputs() -> list[str]:
    """
    Summary
    Scan IOHIDDevice services for input devices without relying on name heuristics.

    Inputs
    None.

    Outputs
    List of formatted device labels.

    Side effects
    Executes ioreg.

    Error handling
    Returns an empty list when output is missing; raises `RuntimeError` with module and method context when parsing
    fails unexpectedly.

    Ties to other methods
    Used by `InputDiagnostics.fetch` for a robust input inventory.

    Why this exists
    system_profiler often omits Bluetooth or internal HID devices; IORegistry is more complete.
    """
    try:
        out, _err = safe_run(
            ["ioreg", "-rl", "-c", "IOHIDDevice", "-w0"], context="ioreg_hid", allow_sudo=False, timeout=4
        )
        if not out:
            return []
        merged: dict[tuple[str, str], set[str]] = {}
        current_product: str | None = None
        current_page: int | None = None
        current_usage: int | None = None
        current_transport: str | None = None

        def flush() -> None:
            """
            Summary
            Execute `flush` for its module-level responsibility.

            Inputs
            None.

            Outputs
            None.

            Side effects
            None beyond this method boundary.

            Error handling
            Raises contextual errors from `mac_health_checkup/diagnostics/devices.py:flush` when this method encounters invalid state or runtime failures.

            Ties to other methods
            Used by workflows in `mac_health_checkup/diagnostics/devices.py`.

            Why this exists
            Keeps `flush` explicit, testable, and maintainable.
            """
            nonlocal current_product, current_page, current_usage, current_transport
            if not current_product:
                return
            kind = _classify_hid_device(current_product, current_page, current_usage)
            if kind is None:
                current_product = None
                current_page = None
                current_usage = None
                current_transport = None
                return
            transport = (current_transport or "").strip() or "?"
            key = (current_product.strip(), transport)
            merged.setdefault(key, set()).add(kind)
            current_product = None
            current_page = None
            current_usage = None
            current_transport = None

        for line in out.splitlines():
            if line.startswith("+-o "):
                flush()
                continue
            match = _IOREG_PRODUCT_RE.match(line)
            if match:
                current_product = match.group("value").strip()
                continue
            match = _IOREG_USAGE_PAGE_RE.match(line)
            if match:
                current_page = int(match.group("value"))
                continue
            match = _IOREG_USAGE_RE.match(line)
            if match:
                current_usage = int(match.group("value"))
                continue
            match = _IOREG_TRANSPORT_RE.match(line)
            if match:
                current_transport = match.group("value").strip()
                continue
        flush()
        consolidated: list[tuple[str, str]] = []
        for (product, transport), kinds in merged.items():
            final_kind = _finalize_hid_kinds(product, kinds)
            if final_kind is None:
                continue
            label = f"{final_kind}: {product}"
            if transport and transport != "?":
                label = f"{label} ({transport})"
            consolidated.append((final_kind, label))

        labels = _dedupe([label for _kind, label in consolidated])
        ordering = {
            "Keyboard + Trackpad": 0,
            "Keyboard": 1,
            "Mouse": 2,
            "Trackpad": 3,
            "Backlight": 4,
            "Other": 9,
        }
        labels.sort(key=lambda label: (ordering.get(label.split(":", 1)[0], 99), label.lower()))
        return labels
    except (RuntimeError, ValueError, TypeError, OSError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_scan_hid_inputs", "Failed to scan HID inputs", exc)
        ) from exc


def _finalize_hid_kinds(product: str, kinds: set[str]) -> str | None:
    """
    Summary
    Consolidate multiple IOHIDDevice classifications for the same product into a single user-facing type.

    Inputs
    product: Device product name.
    kinds: Set of candidate kind strings (Keyboard, Mouse, Trackpad, Other, Receiver, Backlight).

    Outputs
    A single kind string, or None when the device should be excluded.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when normalization fails.

    Ties to other methods
    Used by `_scan_hid_inputs` to dedupe multiple HID interfaces into one row per device.

    Why this exists
    Many real peripherals expose multiple HID interfaces, which otherwise produces duplicate rows and misclassification in the UI.
    """
    try:
        name = (product or "").strip()
        lower = name.lower()
        if not name:
            return None

        if "backlight" in lower:
            return "Backlight"
        if "receiver" in lower:
            return "Mouse"

        if "keyboard" in lower and "trackpad" in lower:
            return "Keyboard + Trackpad"
        if "trackpad" in lower or "touchpad" in lower:
            if "keyboard" in lower:
                return "Keyboard + Trackpad"
            return "Trackpad"
        if "keyboard" in lower:
            return "Keyboard"
        if "mouse" in lower:
            return "Mouse"

        if "Backlight" in kinds:
            return "Backlight"

        if "Keyboard" in kinds and "Trackpad" in kinds:
            return "Keyboard + Trackpad"
        if "Keyboard" in kinds and "Mouse" in kinds:
            return "Keyboard"
        if "Keyboard" in kinds:
            return "Keyboard"
        if "Mouse" in kinds:
            return "Mouse"
        if "Trackpad" in kinds:
            return "Trackpad"
        if "Other" in kinds:
            return "Other"
        return None
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_finalize_hid_kinds", "Failed to finalize HID kinds", exc)
        ) from exc


def _classify_hid_device(product: str, usage_page: int | None, usage: int | None) -> str | None:
    """
    Summary
    Classify an IOHIDDevice as keyboard, mouse, or trackpad when possible.

    Inputs
    product: Product name.
    usage_page: HID usage page when available.
    usage: HID usage when available.

    Outputs
    Kind string or None when not an input device.

    Side effects
    None.

    Error handling
    Raises `RuntimeError` with module and method context when classification fails unexpectedly.

    Ties to other methods
    Used by `_scan_hid_inputs`.

    Why this exists
    Avoids brittle keyword-only filtering and excludes unrelated HID services.
    """
    try:
        name = (product or "").strip()
        lower = name.lower()
        if not name:
            return None
        if lower.startswith("pmu "):
            return None
        if "temp" in lower or "sensor" in lower or "power" in lower:
            return None
        if "backlight" in lower:
            return "Backlight"
        if "receiver" in lower:
            return "Mouse"
        if "keyboard" in lower:
            return "Keyboard"
        if "trackpad" in lower or "touchpad" in lower:
            return "Trackpad"
        if "mouse" in lower:
            return "Mouse"

        if usage_page == 1 and usage == 6:
            return "Keyboard"
        if usage_page == 1 and usage == 2:
            return "Mouse"
        if usage_page == 13:
            return "Trackpad"
        if usage_page in {1, 7}:
            return "Other"
        return None
    except (RuntimeError, ValueError, TypeError, AttributeError) as exc:
        raise RuntimeError(
            format_error(MODULE_PATH, "_classify_hid_device", "Failed to classify HID device", exc)
        ) from exc
