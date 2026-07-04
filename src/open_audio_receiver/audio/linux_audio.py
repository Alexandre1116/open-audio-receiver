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
    devices: list[AudioDevice] = []
    try:
        raw = subprocess.check_output(
            ["pactl", "list", "sinks", "--format=json"],
            timeout=5,
            text=True,
        )
        sinks = json.loads(raw)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        # Fallback: parse plain-text output
        return _parse_pactl_text()
    except Exception as exc:
        logger.warning("pactl (json) failed: %s", exc)
        return devices

    default_name = _get_default_sink_name()
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
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
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
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


class LinuxAudioEngine(AudioEngine):
    """Plays audio via PipeWire (placeholder)."""

    def start(self) -> None:
        logger.info("LinuxAudioEngine started (device=%s)", self.device_id)

    def stop(self) -> None:
        logger.info("LinuxAudioEngine stopped (device=%s)", self.device_id)

    def write(self, pcm_data: bytes) -> None:
        # TODO: PipeWire / ALSA PCM output via pyalsaaudio or GStreamer
        pass
