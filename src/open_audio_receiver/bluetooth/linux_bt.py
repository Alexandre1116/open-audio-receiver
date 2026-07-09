"""
Linux Bluetooth backend via BlueZ D-Bus API.
"""
from __future__ import annotations
import logging
import re
import subprocess
import threading
import time
from typing import Optional
from . import BluetoothDevice, BluetoothManager, PairingRequest
logger = logging.getLogger(__name__)
_BT_ADDR_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

def _safe_bt_addr(address: str) -> str:
    if _BT_ADDR_RE.match(address):
        return address
    raise ValueError(f"Invalid Bluetooth address: {address}")

AGENT_PATH = "/org/open_audio_receiver/agent"
AGENT_CAPABILITY = "DisplayYesNo"
BLUEZ_SERVICE = "org.bluez"
CONFIRM_GRACE_SECONDS = 5.0

try:
    import dbus, dbus.mainloop.glib, dbus.service
    from gi.repository import GLib
    _HAVE_DBUS = True
except ImportError:
    _HAVE_DBUS = False
    logger.warning("dbus-python / PyGObject not available")

if _HAVE_DBUS:
    class Rejected(dbus.DBusException):
        _dbus_error_name = "org.bluez.Error.Rejected"

    class _PairingAgent(dbus.service.Object):
        def __init__(self, bus, manager):
            super().__init__(bus, AGENT_PATH)
            self._manager = manager
            self._recent = {}
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
        def _confirm(self, device_path):
            now = time.monotonic()
            last = self._recent.get(device_path)
            if last is not None and now - last < CONFIRM_GRACE_SECONDS:
                return
            address, name = self._manager._device_info(device_path)
            accepted = True
            if self._manager._on_pairing:
                accepted = self._manager._on_pairing(PairingRequest(address=address, name=name))
            if not accepted:
                raise Rejected("Pairing request rejected")
            self._recent[device_path] = now
            self._manager._set_trusted(device_path)

class LinuxBluetoothManager(BluetoothManager):
    def __init__(self):
        super().__init__()
        self._running = False
        self._bus = None
        self._query_bus = None
        self._agent = None
        self._loop = None
        self._thread = None

    def start(self, adapter_address=""):
        logger.info("Starting Linux Bluetooth manager (A2DP Sink via BlueZ)")
        if adapter_address:
            self._run_bluetoothctl(f"select {adapter_address}")
        self._run_bluetoothctl("power on")
        self._run_bluetoothctl("discoverable on")
        self._run_bluetoothctl("pairable on")
        if _HAVE_DBUS:
            try:
                self._start_dbus_agent()
            except Exception as exc:
                logger.warning("Could not register Bluetooth pairing agent: %s", exc)
        self._running = True
        logger.info("Bluetooth adapter advertising as audio sink")

    def _start_dbus_agent(self):
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self._bus = dbus.SystemBus()
        self._query_bus = dbus.SystemBus(private=True)
        self._agent = _PairingAgent(self._bus, self)
        agent_manager = dbus.Interface(self._bus.get_object(BLUEZ_SERVICE, "/org/bluez"), "org.bluez.AgentManager1")
        agent_manager.RegisterAgent(AGENT_PATH, AGENT_CAPABILITY)
        agent_manager.RequestDefaultAgent(AGENT_PATH)
        self._bus.add_signal_receiver(self._on_properties_changed, dbus_interface="org.freedesktop.DBus.Properties", signal_name="PropertiesChanged", path_keyword="path")
        self._scan_existing_devices()
        self._loop = GLib.MainLoop()
        self._thread = threading.Thread(target=self._loop.run, daemon=True, name="bluez-agent-loop")
        self._thread.start()
        logger.info("Bluetooth pairing agent registered")

    def _scan_existing_devices(self):
        try:
            object_manager = dbus.Interface(self._bus.get_object(BLUEZ_SERVICE, "/"), "org.freedesktop.DBus.ObjectManager")
            objects = object_manager.GetManagedObjects()
        except Exception as exc:
            logger.debug("Could not enumerate existing devices: %s", exc)
            return
        for _path, interfaces in objects.items():
            device = interfaces.get("org.bluez.Device1")
            if device and device.get("Connected"):
                address = str(device.get("Address", ""))
                name = str(device.get("Alias", address))
                if address:
                    self._set_device_connected(address, name, connected=True)
                    self._fire_connected(self._devices[address])

    def _on_properties_changed(self, interface, changed, invalidated, path=None):
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

    def _device_info(self, device_path):
        try:
            obj = self._query_bus.get_object(BLUEZ_SERVICE, device_path)
            props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            address = str(props.Get("org.bluez.Device1", "Address"))
            name = str(props.Get("org.bluez.Device1", "Alias"))
        except Exception:
            tail = device_path.rsplit("/", 1)[-1]
            address = tail.replace("dev_", "").replace("_", ":")
            name = address
        return address, name

    def _set_trusted(self, device_path):
        try:
            obj = self._query_bus.get_object(BLUEZ_SERVICE, device_path)
            props = dbus.Interface(obj, "org.freedesktop.DBus.Properties")
            props.Set("org.bluez.Device1", "Trusted", True)
        except Exception as exc:
            logger.debug("Could not mark %s as trusted: %s", device_path, exc)

    def stop(self):
        self._running = False
        if self._loop is not None:
            self._loop.quit()
            self._loop = None
        if self._bus is not None:
            try:
                agent_manager = dbus.Interface(self._bus.get_object(BLUEZ_SERVICE, "/org/bluez"), "org.bluez.AgentManager1")
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

    def disconnect_device(self, address):
        addr = _safe_bt_addr(address)
        logger.info("Disconnecting %s via bluetoothctl", addr)
        self._run_bluetoothctl(f"disconnect {addr}")

    def unpair_device(self, address):
        addr = _safe_bt_addr(address)
        logger.info("Removing %s via bluetoothctl", addr)
        self._run_bluetoothctl(f"remove {addr}")

    @staticmethod
    def _run_bluetoothctl(cmd):
        try:
            result = subprocess.run(["bluetoothctl", *cmd.split()], capture_output=True, text=True, timeout=10)
            return result.stdout + result.stderr
        except Exception as exc:
            logger.warning("bluetoothctl failed: %s", exc)
            return ""
