"""
Audio device enumeration for Linux via PipeWire / ALSA.
"""
from __future__ import annotations
import json
import logging
import re
import subprocess
from . import AudioDevice, AudioEngine
logger = logging.getLogger(__name__)
def enumerate_devices() -> list[AudioDevice]:
    try:
        raw = subprocess.check_output(["pactl", "--format=json", "list", "sinks"], timeout=5, text=True)
        sinks = json.loads(raw)
    except Exception as exc:
        logger.debug("pactl (json) unavailable, falling back to text parsing: %s", exc)
        return _parse_pactl_text()
    default_name = _get_default_sink_name()
    devices = []
    for sink in sinks:
        name = sink.get("name") or sink.get("description", "Unknown")
        dev_id = sink.get("name", str(sink.get("index", 0)))
        devices.append(AudioDevice(id=dev_id, name=name, is_default=dev_id == default_name))
    return devices

def _parse_pactl_text():
    devices = []
    default_name = _get_default_sink_name()
    current = {}
    try:
        text = subprocess.check_output(["pactl", "list", "sinks"], timeout=5, text=True)
    except Exception as exc:
        logger.warning("pactl (text) failed: %s", exc)
        return devices
    for line in text.splitlines():
        m = re.match(r"^\s*Name:\s+(.+)$", line)
        if m:
            if current:
                devices.append(AudioDevice(id=current["name"], name=current.get("description", current["name"]), is_default=current["name"] == default_name))
            current = {"name": m.group(1).strip()}
            continue
        m = re.match(r"^\s*Description:\s+(.+)$", line)
        if m:
            current["description"] = m.group(1).strip()
    if current:
        devices.append(AudioDevice(id=current["name"], name=current.get("description", current["name"]), is_default=current["name"] == default_name))
    return devices

def _get_default_sink_name():
    try:
        return subprocess.check_output(["pactl", "get-default-sink"], timeout=3, text=True).strip()
    except Exception:
        return ""

class LinuxAudioEngine(AudioEngine):
    def __init__(self, device_id, sample_rate=48000, channels=2):
        super().__init__(device_id, sample_rate, channels)
        self._loopback_modules = {}
    def start(self):
        logger.info("LinuxAudioEngine started (output=%s)", self.device_id)
        self._apply_volume()
    def stop(self):
        for address in list(self._loopback_modules):
            self.detach_source(address)
        logger.info("LinuxAudioEngine stopped (output=%s)", self.device_id)
    def write(self, pcm_data):
        pass
    def attach_source(self, device_address, device_name=""):
        source_name = self._find_bluez_source(device_address)
        if not source_name:
            logger.warning("Could not find capture source for %s (%s)", device_name or device_address, device_address)
            return
        try:
            module_id = subprocess.check_output(["pactl", "load-module", "module-loopback", f"source={source_name}", f"sink={self.device_id}", "latency_msec=40"], timeout=5, text=True).strip()
            self._loopback_modules[device_address] = int(module_id)
            logger.info("Routing audio from %s (%s) to %s", device_name or device_address, source_name, self.device_id)
        except Exception as exc:
            logger.warning("Failed to route audio from %s: %s", source_name, exc)
    def detach_source(self, device_address):
        module_id = self._loopback_modules.pop(device_address, None)
        if module_id is None:
            return
        try:
            subprocess.run(["pactl", "unload-module", str(module_id)], timeout=5, check=False)
        except Exception:
            pass
    @property
    def volume(self):
        return self._volume
    @volume.setter
    def volume(self, val):
        self._volume = max(0.0, min(1.0, val))
        self._apply_volume()
    def _apply_volume(self):
        pct = int(self._volume * 100)
        try:
            subprocess.run(["pactl", "set-sink-volume", self.device_id, f"{pct}%"], timeout=5, check=False)
        except Exception:
            pass
    @staticmethod
    def _find_bluez_source(device_address):
        needle = device_address.replace(":", "_").upper()
        try:
            raw = subprocess.check_output(["pactl", "list", "sources", "short"], timeout=5, text=True)
        except Exception:
            return None
        for line in raw.splitlines():
            parts = line.split("	")
            if len(parts) >= 2 and needle in parts[1].upper():
                return parts[1]
        return None
