"""
Linux Bluetooth backend via BlueZ D-Bus API.

Registers an A2DP Sink profile via D-Bus org.bluez so the system's
Bluetooth stack advertises audio sink capability.  Relies on the system
BlueZ + PulseAudio/PipeWire for actual A2DP streaming.
"""

from __future__ import annotations

import logging
import subprocess
import threading
from typing import Optional

from . import BluetoothDevice, BluetoothManager, PairingRequest

logger = logging.getLogger(__name__)


class LinuxBluetoothManager(BluetoothManager):
    """Bluetooth A2DP Sink via BlueZ (D-Bus)."""

    def __init__(self):
        super().__init__()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

    def start(self, adapter_address: str = "") -> None:
        logger.info("Starting Linux Bluetooth manager (A2DP Sink via BlueZ)")

        # ── Ensure adapter is powered ───────────────────────────
        self._run_bluetoothctl("power on")

        # ── Make the device discoverable ────────────────────────
        self._run_bluetoothctl("discoverable on")
        self._run_bluetoothctl("pairable on")

        # ── Register A2DP Sink profile via D-Bus ────────────────
        # In production you would use pydbus / dbus-next to register
        # a profile at /org/bluez/hci0/A2DP_Sink.  For this MVP we
        # rely on the fact that modern BlueZ + PipeWire auto-register
        # an A2DP Sink when a Bluetooth audio device connects.

        logger.info("Bluetooth adapter advertising as audio sink")
        self._running = True

    def stop(self) -> None:
        self._running = False
        self._run_bluetoothctl("discoverable off")
        logger.info("Linux Bluetooth manager stopped")

    def disconnect_device(self, address: str) -> None:
        logger.info("Disconnecting %s via bluetoothctl", address)
        self._run_bluetoothctl(f"disconnect {address}")

    def unpair_device(self, address: str) -> None:
        logger.info("Removing %s via bluetoothctl", address)
        self._run_bluetoothctl(f"remove {address}")

    # ── Helpers ─────────────────────────────────────────────────

    @staticmethod
    def _run_bluetoothctl(cmd: str) -> str:
        """Run a bluetoothctl command and return output."""
        try:
            result = subprocess.run(
                ["bluetoothctl", *cmd.split()],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout + result.stderr
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("bluetoothctl failed: %s", exc)
            return ""
