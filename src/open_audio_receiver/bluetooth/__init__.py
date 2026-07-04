"""
Bluetooth manager — abstract interface + factory.

Subclasses implement A2DP Sink for each platform.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class BluetoothDevice:
    """Represents a discovered or connected Bluetooth device."""

    address: str
    name: str
    is_connected: bool = False
    is_paired: bool = False
    codec: str = "SBC"  # SBC, AAC, aptX, LDAC


@dataclass
class PairingRequest:
    """Emitted when a new device tries to pair or connect."""

    address: str
    name: str
    auto_confirm: bool = False


# Callback types
OnDeviceConnected = Callable[[BluetoothDevice], None]
OnDeviceDisconnected = Callable[[BluetoothDevice], None]
OnPairingRequest = Callable[[PairingRequest], bool]  # return True to accept


class BluetoothManager(ABC):
    """Abstract Bluetooth receiver controller.

    Callbacks are set before calling start().
    """

    def __init__(self):
        self._on_connected: Optional[OnDeviceConnected] = None
        self._on_disconnected: Optional[OnDeviceDisconnected] = None
        self._on_pairing: Optional[OnPairingRequest] = None
        self._devices: dict[str, BluetoothDevice] = {}

    # ── Callback setters ────────────────────────────────────────────────

    def on_device_connected(self, cb: OnDeviceConnected) -> None:
        self._on_connected = cb

    def on_device_disconnected(self, cb: OnDeviceDisconnected) -> None:
        self._on_disconnected = cb

    def on_pairing_request(self, cb: OnPairingRequest) -> None:
        self._on_pairing = cb

    # ── Lifecycle ───────────────────────────────────────────────────────

    @abstractmethod
    def start(self, adapter_address: str = "") -> None:
        """Start advertising as A2DP Sink and listen for connections."""

    @abstractmethod
    def stop(self) -> None:
        """Stop advertising and disconnect all devices."""

    @abstractmethod
    def disconnect_device(self, address: str) -> None:
        """Disconnect a specific device."""

    @abstractmethod
    def unpair_device(self, address: str) -> None:
        """Remove pairing with a device."""

    @property
    def is_running(self) -> bool:
        """Whether the manager has been started and hasn't been stopped."""
        return getattr(self, "_running", False)

    @property
    def connected_devices(self) -> list[BluetoothDevice]:
        return [d for d in self._devices.values() if d.is_connected]

    @property
    def all_devices(self) -> list[BluetoothDevice]:
        return list(self._devices.values())

    # ── factory ─────────────────────────────────────────────────────────

    @staticmethod
    def create(on_pairing: Optional[OnPairingRequest] = None) -> BluetoothManager:
        """Return the right manager for the current platform."""
        from ..utils import get_platform

        plat = get_platform()
        if plat == "windows":
            from .windows_bt import WindowsBluetoothManager

            mgr: BluetoothManager = WindowsBluetoothManager()
        elif plat == "linux":
            from .linux_bt import LinuxBluetoothManager

            mgr = LinuxBluetoothManager()
        else:
            raise RuntimeError(f"Unsupported platform: {plat}")

        if on_pairing is not None:
            mgr.on_pairing_request(on_pairing)
        return mgr

    # ── Internal helpers for subclasses ─────────────────────────────────

    def _set_device_connected(self, address: str, name: str, connected: bool = True) -> None:
        if address not in self._devices:
            self._devices[address] = BluetoothDevice(address=address, name=name)
        dev = self._devices[address]
        dev.name = name
        dev.is_connected = connected
        dev.is_paired = True

    def _fire_connected(self, dev: BluetoothDevice) -> None:
        if self._on_connected:
            self._on_connected(dev)

    def _fire_disconnected(self, dev: BluetoothDevice) -> None:
        if self._on_disconnected:
            self._on_disconnected(dev)
