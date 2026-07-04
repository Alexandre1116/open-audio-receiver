"""Audio device enumeration for Linux via PipeWire / ALSA."""

from __future__ import annotations

import json
import logging
import re
import subprocess

from . import AudioDevice, AudioEngine

logger = logging.getLogger(__name__)


def enumerate_devices() -> list[AudioDevice]:
    """List audio sinks via ``pactl list sinks`` (PipeWire/PulseAudio)."""
    try:
        # --format is a global pactl option and must come *before* the
        # subcommand; `pactl list sinks --format=json` is rejected by pactl
        # (it prints usage help and exits non-zero) on current versions.
        raw = subprocess.check_output(
            ["pactl", "--format=json", "list", "sinks"],
            timeout=5,
            text=True,
        )
        sinks = json.loads(raw)
    except (
        FileNotFoundError,
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        json.JSONDecodeError,
    ) as exc:
        logger.debug("pactl (json) unavailable, falling back to text parsing: %s", exc)
        return _parse_pactl_text()

    default_name = _get_default_sink_name()
    devices: list[AudioDevice] = []
    for sink in sinks:
        name = sink.get("name") or sink.get("description", "Unknown")
        dev_id = sink.get("name", str(sink.get("index", 0)))
        devices.append(
            AudioDevice(
                id=dev_id,
                name=name,
                is_default=dev_id == default_name,
            )
        )
    return devices


def _parse_pactl_text() -> list[AudioDevice]:
    """Fallback parser for ``pactl list sinks`` plain text."""
    devices: list[AudioDevice] = []
    default_name = _get_default_sink_name()
    current: dict = {}
    try:
        text = subprocess.check_output(["pactl", "list", "sinks"], timeout=5, text=True)
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        logger.warning("pactl (text) failed: %s", exc)
        return devices

    for line in text.splitlines():
        m = re.match(r"^\s*Name:\s+(.+)$", line)
        if m:
            if current:
                devices.append(
                    AudioDevice(
                        id=current.get("name", ""),
                        name=current.get("description", current.get("name", "Unknown")),
                        is_default=current.get("name") == default_name,
                    )
                )
            current = {"name": m.group(1).strip()}
            continue
        m = re.match(r"^\s*Description:\s+(.+)$", line)
        if m:
            current["description"] = m.group(1).strip()
    if current:
        devices.append(
            AudioDevice(
                id=current.get("name", ""),
                name=current.get("description", current.get("name", "Unknown")),
                is_default=current.get("name") == default_name,
            )
        )
    return devices


def _get_default_sink_name() -> str:
    """Return the default PulseAudio/PipeWire sink name."""
    try:
        return subprocess.check_output(
            ["pactl", "get-default-sink"], timeout=3, text=True
        ).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return ""


class LinuxAudioEngine(AudioEngine):
    """Routes BlueZ A2DP Sink audio to the chosen output device.

    On Linux, BlueZ + PipeWire/WirePlumber already negotiate and decode the
    A2DP stream; the incoming audio shows up as a regular capture source
    (e.g. ``bluez_input.AA_BB_CC_DD_EE_FF``). This engine never touches raw
    PCM — it links that source to the selected output sink with a
    ``module-loopback`` for as long as the device stays connected.
    """

    def __init__(self, device_id: str, sample_rate: int = 48000, channels: int = 2):
        super().__init__(device_id, sample_rate, channels)
        self._loopback_modules: dict[str, int] = {}  # bt address -> pactl module id

    def start(self) -> None:
        logger.info("LinuxAudioEngine started (output=%s)", self.device_id)

    def stop(self) -> None:
        for address in list(self._loopback_modules):
            self.detach_source(address)
        logger.info("LinuxAudioEngine stopped (output=%s)", self.device_id)

    def write(self, pcm_data: bytes) -> None:
        # Routing happens at the PipeWire graph level; see attach_source().
        pass

    def attach_source(self, device_address: str, device_name: str = "") -> None:
        source_name = self._find_bluez_source(device_address)
        if not source_name:
            logger.warning(
                "Could not find a PipeWire/PulseAudio capture source for %s (%s) — "
                "route it to your output manually (e.g. with pavucontrol/qpwgraph)",
                device_name or device_address,
                device_address,
            )
            return
        try:
            module_id = subprocess.check_output(
                [
                    "pactl",
                    "load-module",
                    "module-loopback",
                    f"source={source_name}",
                    f"sink={self.device_id}",
                    "latency_msec=40",
                ],
                timeout=5,
                text=True,
            ).strip()
            self._loopback_modules[device_address] = int(module_id)
            logger.info(
                "Routing audio from %s (%s) to %s",
                device_name or device_address,
                source_name,
                self.device_id,
            )
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            ValueError,
        ) as exc:
            logger.warning("Failed to route audio from %s: %s", source_name, exc)

    def detach_source(self, device_address: str) -> None:
        module_id = self._loopback_modules.pop(device_address, None)
        if module_id is None:
            return
        try:
            subprocess.run(["pactl", "unload-module", str(module_id)], timeout=5, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    @staticmethod
    def _find_bluez_source(device_address: str) -> str | None:
        """Find the pactl source name carrying a connected Bluetooth device's audio."""
        needle = device_address.replace(":", "_").upper()
        try:
            raw = subprocess.check_output(
                ["pactl", "list", "sources", "short"], timeout=5, text=True
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return None
        for line in raw.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and needle in parts[1].upper():
                return parts[1]
        return None
