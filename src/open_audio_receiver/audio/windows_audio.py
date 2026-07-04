"""Audio device enumeration for Windows via pycaw / MMDevice API."""

from __future__ import annotations

import logging
from typing import Optional

from . import AudioDevice, AudioEngine

logger = logging.getLogger(__name__)

try:
    from pycaw.pycaw import AudioUtilities, EDataFlow, ERole, DEVICE_STATE
except ImportError:
    _HAVE_PYCAW = False
    AudioUtilities = None
    logger.warning("pycaw not available — Windows audio device listing disabled")
else:
    _HAVE_PYCAW = True
    from comtypes import COMError


def enumerate_devices() -> list[AudioDevice]:
    """List all active audio render (output) devices via MMDevice API."""
    devices: list[AudioDevice] = []
    if not _HAVE_PYCAW:
        return devices
    try:
        collection = AudioUtilities.GetAllDevices(EDataFlow.eRender.value)
    except COMError as exc:
        logger.warning("COM error enumerating audio devices: %s", exc)
        return devices

    default_id = _get_default_id()

    for dev in collection:
        if dev.state != DEVICE_STATE.ACTIVE:
            continue
        dev_id = dev.id  # string
        devices.append(
            AudioDevice(
                id=dev_id,
                name=dev.FriendlyName or "Unknown Device",
                is_default=dev_id == default_id,
                channels=2,
                sample_rate=48000,
            )
        )
    return devices


def _get_default_id() -> Optional[str]:
    """Return the default render device's ID string."""
    try:
        dev = AudioUtilities.GetDefaultAudioDevice(EDataFlow.eRender.value, ERole.eMultimedia.value)
        return getattr(dev, "id", None)
    except COMError:
        return None


class WindowsAudioEngine(AudioEngine):
    """Plays audio via WASAPI loopback (placeholder — needs WASAPI integration)."""

    def __init__(self, device_id: str):
        super().__init__(device_id)
        self._buf: list[bytes] = []

    def start(self) -> None:
        logger.info("WindowsAudioEngine started (device=%s)", self.device_id)

    def stop(self) -> None:
        logger.info("WindowsAudioEngine stopped (device=%s)", self.device_id)

    def write(self, pcm_data: bytes) -> None:
        # TODO: real WASAPI output via pycaw / ctypes
        pass
