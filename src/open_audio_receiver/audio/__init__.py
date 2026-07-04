"""Audio device enumeration and playback engine."""

from __future__ import annotations

import platform
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..utils import is_windows


# ── Data types ──────────────────────────────────────────────────────────────


@dataclass
class AudioDevice:
    """Represents an audio output device (physical or virtual)."""

    id: str
    name: str
    is_default: bool = False
    channels: int = 2
    sample_rate: int = 48000


# ── Abstract engine ─────────────────────────────────────────────────────────


class AudioEngine(ABC):
    """Plays incoming A2DP audio streams.

    One engine instance is created per connected device.  Subclasses
    implement the platform-specific playback loop.
    """

    def __init__(self, device_id: str, sample_rate: int = 48000, channels: int = 2):
        self.device_id = device_id
        self.sample_rate = sample_rate
        self.channels = channels
        self._volume: float = 1.0
        self._running = False

    @abstractmethod
    def start(self) -> None:
        """Open the output device and prepare for playback."""

    @abstractmethod
    def stop(self) -> None:
        """Stop playback and release resources."""

    @abstractmethod
    def write(self, pcm_data: bytes) -> None:
        """Feed decoded PCM audio into the output device."""

    def attach_source(self, device_address: str, device_name: str = "") -> None:
        """Route a newly-connected Bluetooth device's audio to the output device.

        Default is a no-op. Override on platforms where the OS audio stack
        does not already do this automatically (see ``LinuxAudioEngine``).
        """

    def detach_source(self, device_address: str) -> None:
        """Undo :meth:`attach_source` for a device that disconnected."""

    @property
    def volume(self) -> float:
        return self._volume

    @volume.setter
    def volume(self, val: float) -> None:
        self._volume = max(0.0, min(1.0, val))

    # ── factory ──────────────────────────────────────────────────────────

    @staticmethod
    def create(device_id: str = "default") -> "AudioEngine":
        """Return the right engine for the current platform."""
        if is_windows():
            from .windows_audio import WindowsAudioEngine

            return WindowsAudioEngine(device_id)
        from .linux_audio import LinuxAudioEngine

        return LinuxAudioEngine(device_id)

    @staticmethod
    def list_devices() -> list[AudioDevice]:
        """Enumerate available audio output devices."""
        if is_windows():
            from .windows_audio import enumerate_devices

            return enumerate_devices()
        from .linux_audio import enumerate_devices

        return enumerate_devices()


# ── Dummy engine (fallback) ─────────────────────────────────────────────────


class DummyAudioEngine(AudioEngine):
    """Silently discards audio.  Used when no real engine is available."""

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def write(self, pcm_data: bytes) -> None:
        pass
