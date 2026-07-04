"""
Linux Bluetooth backend via BlueZ D-Bus API.

Makes the adapter discoverable/pairable, registers a pairing agent so
connection requests surface as a confirmation callback (wired to the app's
pairing dialog), and tracks device Connected state via D-Bus signals.
Actual A2DP decoding/streaming is handled by the system's BlueZ + PipeWire
stack — see ``LinuxAudioEngine`` for how the resulting audio gets routed to
the chosen output device.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from typing import Optional

from . import BluetoothDevice, BluetoothManager, PairingRequest

logger = logging.getLogger(__name__)

AGENT_PATH = "/org/open_audio_receiver/agent"
AGENT_CAPABILITY = "DisplayYesNo"
BLUEZ_SERVICE = "org.bluez"
CONFIRM_GRACE_SECONDS = 5.0  # de-dupe RequestConfirmation + AuthorizeService for the same connect

try:
    import dbus
    import dbus.mainloop.glib
    import dbus.service
    from gi.repository import GLib

    _HAVE_DBUS = True
except ImportError:
    _HAVE_DBUS = False
    logger.warning(
        "dbus-python / PyGObject not available — Linux pairing pop-ups and "
        "device tracking are disabled (install with: pip install dbus-python PyGObject)"
    )


if _HAVE_DBUS:

    class Rejected(dbus.DBusException):
        _dbus_error_name = "org.bluez.Error.Rejected"

    class _PairingAgent(dbus.service.Object):
        """BlueZ pairing agent — bridges confirmation/authorization requests
        to the app's ``on_pairing`` callback."""

        def __init__(self, bus, manager: "LinuxBluetoothManager"):
            super().__init__(bus, AGENT_PATH)
            self._manager = manager
            self._recent: dict[str, float] = {}

        @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
        def Release(self):
            logger.debug("Bluetooth agent released")

        @dbus.service.method("org.bluez.Agent1", in_signature="ou", out_signature="")
        def RequestConfirmation(self, device, passkey):
            self._confirm(device)

        @dbus.service.method("org.bluez.Agent1", in_signature="o", out_signature="")
        def RequestAuthorization(self, device):
            self._confirm(device)

        @dbus.service.method("org.bluez.Agent1", in_signature="os", out_signature="")
        def AuthorizeService(self, device, uuid):
            self._confirm(device)

        @dbus.service.method("org.bluez.Agent1", in_signature="", out_signature="")
        def Cancel(self):
            logger.debug("Bluetooth agent request cancelled")

        def _confirm(self, device_path: str) -> None:
            now = time.monotonic()
            last = self._recent.get(device_path)
            if last is not None and now - last < CONFIRM_GRACE_SECONDS:
                return  # already confirmed this device a moment ago (e.g. A2DP + AVRCP)

            address, name = self._manager._device_info(device_path)
            accepted = True
            if self._manager._on_pairing:
                accepted = self._manager._on_pairing(PairingRequest(address=address, name=name))
            if not accepted:
                raise Rejected("Pairing request rejected by user")

            self._recent[device_path] = now
            self._manager._set_trusted(device_path)


class LinuxBluetoothManager(BluetoothManager):
    """Bluetooth A2DP Sink via BlueZ (D-Bus)."""

    def __init__(self):
        super().__init__()
        self._running = False
        self._bus = None
        self._query_bus = None
        self._agent = None
        self._loop = None
        self._thread: Optional[threading.Thread] = None

    def start(self, adapter_address: str = "") -> None:
        logger.info("Starting Linux Bluetooth manager (A2DP Sink via BlueZ)")

        if adapter_address:
            self._run_bluetoothctl(f"select {adapter_address}")

        # ── Ensure adapter is powered and discoverable ──────────
        self._run_bluetoothctl("power on")
        self._run_bluetoothctl("discoverable on")
        self._run_bluetoothctl("pairable on")

        if _HAVE_DBUS:
            try:
                self._start_dbus_agent()
            except Exception as exc:
                logger.warning(
                    "Could not register Bluetooth pairing agent — falling back to "
                    "adapter-only mode (no pairing pop-ups or device tracking): %s",
                    exc,
                )

        logger.info("Bluetooth adapter advertising as audio sink")
        self._running = True

    def _start_dbus_agent(self) -> None:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SystemBus()
        # A separate connection for queries made *from inside* agent callbacks
        # (_device_info/_set_trusted): issuing a blocking call on the same
        # connection that is mid-dispatch of the incoming call that triggered
        # it deadlocks the underlying libdbus connection.
        self._query_bus = dbus.SystemBus(private=True)
        self._agent = _PairingAgent(self._bus, self)

        agent_manager = dbus.Interface(
            self._bus.get_object(BLUEZ_SERVICE, "/org/bluez"), "org.bluez.AgentManager1"
        )
        agent_manager.RegisterAgent(AGENT_PATH, AGENT_CAPABILITY)
        agent_manager.RequestDefaultAgent(AGENT_PATH)

        self._bus.add_signal_receiver(
            self._on_properties_changed,
            dbus_interface="org.freedesktop.DBus.Properties",
            signal_name="PropertiesChanged",
            path_keyword="path",
        )

        self._scan_existing_devices()

        self._loop = GLib.MainLoop()
        self._thread = threading.Thread(target=self._loop.run, daemon=True, name="bluez-agent-loop")
        self._thread.start()
        logger.info("Bluetooth pairing agent registered")

    def _scan_existing_devices(self) -> None:
        """Pick up devices that are already connected when the receiver starts."""
        try:
            object_manager = dbus.Interface(
                self._bus.get_object(BLUEZ_SERVICE, "/"), "org.freedesktop.DBus.ObjectManager"
            )
            objects = object_manager.GetManagedObjects()
        except Exception as exc:
            logger.debug("Could not enumerate existing Bluetooth devices: %s", exc)
            return

        for _path, interfaces in objects.items():
            device = interfaces.get("org.bluez.Device1")
            if device and device.get("Connected"):
                address = str(device.get("Address", ""))
                name = str(device.get("Alias", address))
                if address:
                    self._set_device_connected(address, name, connected=True)
                    self._fire_connected(self._devices[address])

    def _on_properties_changed(self, interface, changed, invalidated, path=None) -> None:
        if interface != "org.bluez.Device1" or "Connected" not in changed:
            return
        address, name = self._device_info(path)
        if not address:
            return
        if bool(changed["Connected"]):
            self._set_device_connected(address, name, connected=True)
            self._fire_connected(self._devices[address])
        elif address in self._devices:
            self._devices[address].is_connected = False
            self._fire_disconnected(self._devices[address])

    def _device_info(self, device_path: str) -> tuple[str, str]:
        try:
            obj = self._query_bus.get_object(BLUEZ_SERVICE, device_path)
            props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            address = str(props.Get("org.bluez.Device1", "Address"))
            name = str(props.Get("org.bluez.Device1", "Alias"))
        except Exception:
            # Fall back to decoding the address straight from the object path
            # (.../dev_AA_BB_CC_DD_EE_FF)
            tail = device_path.rsplit("/", 1)[-1]
            address = tail.replace("dev_", "").replace("_", ":")
            name = address
        return address, name

    def _set_trusted(self, device_path: str) -> None:
        try:
            obj = self._query_bus.get_object(BLUEZ_SERVICE, device_path)
            props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            props.Set("org.bluez.Device1", "Trusted", True)
        except Exception as exc:
            logger.debug("Could not mark %s as trusted: %s", device_path, exc)

    def stop(self) -> None:
        self._running = False
        if self._loop is not None:
            self._loop.quit()
            self._loop = None
        if self._bus is not None:
            try:
                agent_manager = dbus.Interface(
                    self._bus.get_object(BLUEZ_SERVICE, "/org/bluez"), "org.bluez.AgentManager1"
                )
                agent_manager.UnregisterAgent(AGENT_PATH)
            except Exception:
                pass
        if self._query_bus is not None:
            try:
                self._query_bus.close()
            except Exception:
                pass
        self._agent = None
        self._bus = None
        self._query_bus = None
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
