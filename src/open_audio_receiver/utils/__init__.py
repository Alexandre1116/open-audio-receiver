"""Utility helpers — auto-start, logging, platform checks."""

from __future__ import annotations

import logging
import platform
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """Configure a clean console logger."""
    level = logging.DEBUG if "-v" in sys.argv or "--verbose" in sys.argv else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def is_windows() -> bool:
    return platform.system() == "Windows"


def is_linux() -> bool:
    return platform.system() == "Linux"


def get_platform() -> str:
    """Return 'windows' or 'linux'.  Raises on unsupported systems."""
    sys_name = platform.system()
    if sys_name == "Windows":
        return "windows"
    if sys_name == "Linux":
        return "linux"
    raise RuntimeError(f"Unsupported platform: {sys_name}")
