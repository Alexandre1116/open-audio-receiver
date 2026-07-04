"""
Windows Bluetooth backend via WinRT (Windows.Devices.Bluetooth).

Uses pywinrt to access the Windows Bluetooth RFCOMM / A2DP Sink APIs.
Advertising as an A2DP Sink on Windows requires enabling the "Bluetooth
Audio Receiver" service in the Windows Bluetooth settings or using the
Windows.Devices.Bluetooth.Rfcomm API.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

from . import BluetoothDevice, BluetoothManager, PairingRequest

logger = logging.getLogger(__name__)

try:
    import winrt.windows.devices.bluetooth.advertisement as bta
    import winrt.windows.devices.bluetooth.rfcomm as rfcomm
    from winrt.system import EventHandler

    _HAVE_WINRT = True
except ImportError:
    _HAVE_WINRT = False
    logger.warning("pywinrt not available — Windows Bluetooth disabled")


class WindowsBluetoothManager(BluetoothManager):
    """Bluetooth A2DP Sink via WinRT."""

    def __init__(self):
        super().__init__()
        self._watcher = None
        self._advertiser = None
        self._running = False
        self._lock = threading.Lock()

    def start(self, adapter_address: str = "") -> None:
        if not _HAVE_WINRT:
            logger.error("Cannot start Bluetooth — pywinrt not installed")
            return

        logger.info("Starting Windows Bluetooth manager (A2DP Sink)")

        # ── Start device watcher ─────────────────────────────────
        self._watcher = bta.BluetoothLEAdvertisementWatcher()
        self._watcher.received += EventHandler(self._on_advertisement)
        self._watcher.stopped += EventHandler(lambda s, e: logger.info("BLE watcher stopped"))
        self._watcher.start()

        # ── Publish RFCOMM SPP service (simplified) ──────────────
        # Full A2DP Sink registration requires a Windows driver.
        # For this MVP we listen for RFCOMM connections as a proxy.
        try:
            provider = rfcomm.RfcommServiceProvider.create_async(
                rfcomm.RfcommService_id.from_uuid(rfcomm.RfcommService_id.PORT_ANY)
            ).get()
            self._advertiser = bta.BluetoothLEAdvertisementPublisher()
            self._advertiser.start()
            logger.info("RFCOMM service published (advertisement started)")
        except Exception as exc:
            logger.warning("Could not publish RFCOMM service: %s", exc)

        self._running = True

    def stop(self) -> None:
        with self._lock:
            if self._watcher:
                try:
                    self._watcher.stop()
                except Exception:
                    pass
            if self._advertiser:
                try:
                    self._advertiser.stop()
                except Exception:
                    pass
            self._running = False
        logger.info("Windows Bluetooth manager stopped")

    def disconnect_device(self, address: str) -> None:
        logger.info("Disconnect requested for %s", address)

    def unpair_device(self, address: str) -> None:
        logger.info("Unpair requested for %s", address)

    # ── Event handlers ──────────────────────────────────────────

    def _on_advertisement(self, sender, args) -> None:
        """Handle BLE advertisement — this is where we detect nearby devices."""
        addr = args.bluetooth_address
        addr_str = ":".join(f"{(addr >> (8 * i)) & 0xFF:02X}" for i in range(5, -1, -1))
        name = args.advertisement.local_name or f"Device_{addr_str}"

        # Simulate pairing request for unknown devices
        with self._lock:
            if addr_str not in self._devices:
                req = PairingRequest(address=addr_str, name=name)
                accepted = True
                if self._on_pairing:
                    accepted = self._on_pairing(req)
                if accepted:
                    self._set_device_connected(addr_str, name, connected=False)
                    logger.info("Accepted pairing from %s (%s)", name, addr_str)
                else:
                    logger.info("Rejected pairing from %s (%s)", name, addr_str)
