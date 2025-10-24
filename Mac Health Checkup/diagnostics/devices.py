from __future__ import annotations   # if not already present
import re

# ── standard library ───────────────────────────────────────────────
import time
from typing import Any, Dict, Iterable, List, Optional, Tuple, Final

# ── internal diagnostics package ───────────────────────────────────
from constants import CACHE_TTL, TB_IGNORES
from utils import safe_run, classify_by_ids, classify_device
from diagnostics.base import (
    debug_msg,
    log_exc,
    dedupe_strings,
    classify_and_dedupe,
)
USB_VENDOR_PRODUCT_RE: Final[re.Pattern[str]] = re.compile(
    r'"idVendor" = 0x([0-9a-fA-F]+).*?"idProduct" = 0x([0-9a-fA-F]+)', re.DOTALL
)
USB_PRODUCT_NAME_RE: Final[re.Pattern[str]] = re.compile(r'"USB Product Name" = "([^"]+)"')
USB_PRODUCT_LINE_RE: Final[re.Pattern[str]] = re.compile(r'Product Name:\s*(.+)', re.IGNORECASE)
BT_CONNECTED_NAME_RE: Final[re.Pattern[str]] = re.compile(r'^\s+(.+?):\s+Connected: Yes', re.MULTILINE)
NETWORK_HARDWARE_RE: Final[re.Pattern[str]] = re.compile(r'Hardware:\s+(.+)')
INPUT_KEYWORD_MAP: Final[dict[str, str]] = {
    "keyboard" : "Keyboard",
    "trackpad" : "Trackpad",
    "mouse"    : "Mouse",
    "touch bar": "Touch Bar",
}


class DeviceScanner:
    """
    Unified, cached peripheral scanner for USB, Bluetooth, Thunderbolt and
    CDC-ECM network dongles.
    Used as a row/section builder for connected device lists.
    """
    _cache_ttl = CACHE_TTL
    _cache: Dict[str, Tuple[float, List[str]]] = {}

    # ─── cache helpers ──────────────────────────────────────────
    @staticmethod
    def _cached(key: str) -> Optional[List[str]]:
        entry = DeviceScanner._cache.get(key)
        if entry and time.time() - entry[0] < DeviceScanner._cache_ttl:
            return entry[1]
        return None

    @staticmethod
    def _store(key: str, devices: List[str]) -> None:
        DeviceScanner._cache[key] = (time.time(), devices)

    # ─── individual bus scanners ────────────────────────────────
    @staticmethod
    def scan_usb() -> List[str]:
        cached = DeviceScanner._cached("usb")
        if cached is not None:
            return cached
        out, _ = safe_run(["ioreg", "-p", "IOUSB", "-l"], "USBScan")
        devices: List[str] = []
        if out:
            pairs = USB_VENDOR_PRODUCT_RE.findall(out)
            for vend, prod in pairs:
                label = classify_by_ids(vend, prod)
                if label:
                    devices.append(label)
            names = USB_PRODUCT_NAME_RE.findall(out)
            devices.extend([classify_device(n) for n in names])
        devices = classify_and_dedupe(devices)
        DeviceScanner._store("usb", devices)
        return devices

    @staticmethod
    def scan_bluetooth() -> List[str]:
        cached = DeviceScanner._cached("bt")
        if cached is not None:
            return cached
        out, _ = safe_run(["system_profiler", "SPBluetoothDataType"], "BTScan")
        names = BT_CONNECTED_NAME_RE.findall(out or "")
        devices = classify_and_dedupe(names)
        DeviceScanner._store("bt", devices)
        return devices

    @staticmethod
    def _filter_tb_label(label: str) -> bool:
        """Return True if this Thunderbolt label should be kept (not ignored)."""
        try:
            low = label.lower().strip()
        except Exception:
            return False
        return not any(k in low for k in TB_IGNORES)

    @staticmethod
    def _iter_tb_labels(text: str) -> Iterable[str]:
        """Yield Thunderbolt header labels from system_profiler output."""
        for line in text.splitlines():
            m = re.match(r'^\s{8,}([^\n:]+):\s*$', line)
            if not m:
                continue
            label = m.group(1).strip()
            if DeviceScanner._filter_tb_label(label):
                yield label

    # --- Replace DeviceScanner.scan_thunderbolt ---
    @staticmethod
    def scan_thunderbolt() -> List[str]:
        cached = DeviceScanner._cached("tb")
        if cached is not None:
            return cached
        out, _ = safe_run(["system_profiler", "SPThunderboltDataType"], "TBScan")
        if not out:
            return []
        names: List[str] = [classify_device(label) for label in DeviceScanner._iter_tb_labels(out)]
        DeviceScanner._store("tb", DeviceScanner._dedupe(names))
        return DeviceScanner._cached("tb") or []

    @staticmethod
    def scan_network() -> List[str]:
        cached = DeviceScanner._cached("net")
        if cached is not None:
            return cached
        out, _ = safe_run(["system_profiler", "SPNetworkDataType"], "NETScan")
        names = NETWORK_HARDWARE_RE.findall(out or "")
        devices = classify_and_dedupe(names)
        DeviceScanner._store("net", devices)
        return devices

    # ─── public aggregate ───────────────────────────────────────
    @staticmethod
    def scan_all() -> List[str]:
        return DeviceScanner._dedupe(
            DeviceScanner.scan_usb()
            + DeviceScanner.scan_bluetooth()
            + DeviceScanner.scan_thunderbolt()
            + DeviceScanner.scan_network()
        )

    # ─── helpers ────────────────────────────────────────────────
    @staticmethod
    def _dedupe(seq: List[str]) -> List[str]:
        seen = set()
        out: List[str] = []
        for item in seq:
            if item and item not in seen:
                out.append(item)
                seen.add(item)
        return out


class PortsDiagnostics:
    """
    USB port device diagnostics section builder.
    Produces a row/section listing connected USB devices.
    """

    @staticmethod
    def _parse_usb_products(text: str) -> List[str]:
        """
        Extract and classify USB product names from raw system_profiler text.

        Returns:
            List[str]: De‑duplicated, order‑preserving list of friendly device
            labels suitable for UI presentation.
        """
        raw_names = re.findall(r'Product Name:\s*(.+)', text)
        friendly = [classify_device(n) for n in raw_names]
        return dedupe_strings(friendly)

    @staticmethod
    def fetch() -> Dict[str, Any]:
        """
        Fetch connected USB device info and return a normalized section dict.

        Returns:
            Dict[str, Any] with keys:
                - "devices": List[str] (USB device labels)
                - "raw": str (source, always empty here)
        """
        try:
            devices = DeviceScanner.scan_usb()
            debug_msg("PortsDiagnostics", f"USB devices detected: {len(devices)}")
            return PortsDiagnostics._build_row_section(devices, "")
        except Exception as exc:
            log_exc("PortsDiagnostics", exc)
            return PortsDiagnostics._build_row_section([], "")

    @staticmethod
    def _build_row_section(devices: list[str], raw: str) -> dict[str, Any]:
        """Assemble the canonical output dict for PortsDiagnostics."""
        return {
            "devices": devices,
            "raw"    : raw,
        }


class InputDiagnostics:
    """
    Input device (keyboard/trackpad) diagnostics section builder.
    Produces a row/section listing discovered input devices.
    """

    @staticmethod
    def _parse_input_devices(text: str) -> List[str]:
        """
        Identify input peripherals using both explicit USB/HID product names
        and broader keyword heuristics, then classify them to user‑friendly
        labels.
        """
        found: List[str] = []

        # 1) Explicit product names reported by system_profiler / ioreg
        raw_products = re.findall(r'Product Name:\s*(.+)', text, flags=re.IGNORECASE)
        for prod in raw_products:
            friendly = classify_device(prod)
            found.append(friendly)

        # 2) Keyword fallback for built-in devices that may lack Product Name
        lower = text.lower()
        for key, label in INPUT_KEYWORD_MAP.items():
            if key in lower:
                found.append(label)

        return dedupe_strings(found)

    @staticmethod
    def fetch() -> Dict[str, Any]:
        """
        Discover connected input devices and return a normalized section dict.

        Returns:
            Dict[str, Any] with keys:
                - "input_found": bool
                - "details": List[str] (device labels)
                - "raw": str (concatenated command outputs, trimmed)
        """
        try:
            commands = [
                ["system_profiler", "SPUSBDataType"],
                ["system_profiler", "SPUSBDataType", "-detailLevel", "full"],
                ["system_profiler", "SPHumanInterfaceDeviceDataType"],
                ["ioreg", "-p", "IOUSB", "-l"],
            ]

            combined_raw: List[str] = []
            detected: List[str] = []

            for idx, cmd in enumerate(commands, start=1):
                out, _ = safe_run(cmd, f"Input{idx}")
                if not out:
                    continue
                combined_raw.append(f"----- {' '.join(cmd)} -----\n{out}")
                detected = InputDiagnostics._parse_input_devices(out)
                if detected:
                    break  # Stop on first successful detection

            # Merge peripherals discovered through DeviceScanner (USB/Bluetooth/etc.)
            for dev in DeviceScanner.scan_all():
                if dev not in detected:
                    detected.append(dev)

            detected = classify_and_dedupe(detected)
            return InputDiagnostics._build_row_section(
                bool(detected), detected, "\n\n".join(combined_raw).strip()
            )
        except Exception as exc:
            log_exc("InputDiagnostics", exc)
            return InputDiagnostics._build_row_section(False, [], "")

    @staticmethod
    def _build_row_section(input_found: bool, details: list[str], raw: str) -> dict[str, Any]:
        """
        Assemble the canonical output dict for InputDiagnostics.
        """
        return {
            "input_found": input_found,
            "details"    : details,
            "raw"        : raw,
        }
