"""
Configuration manager for Open Audio Receiver.

Loads/saves user preferences from a JSON file in the user's config directory.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class AppConfig:
    """Serializable application configuration."""

    # Audio
    output_device_id: str = "default"
    volume: float = 1.0
    codec_preference: str = "auto"

    # Bluetooth
    auto_accept_pairing: bool = False
    adapter_address: str = ""  # empty = first adapter

    # Window
    window_width: int = 600
    window_height: int = 500
    start_minimized: bool = False
    close_to_tray: bool = True

    # Theme
    dark_mode: bool = True

    # Known devices — dict[address, friendly_name]
    known_devices: dict[str, str] = field(default_factory=dict)

    @classmethod
    def config_dir(cls) -> Path:
        """Return the platform-specific config directory."""
        system = platform.system()
        if system == "Windows":
            base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        elif system == "Linux":
            xdg = os.environ.get("XDG_CONFIG_HOME")
            base = Path(xdg) if xdg else Path.home() / ".config"
        else:
            base = Path.home() / ".config"
        return base / "open-audio-receiver"

    @classmethod
    def load(cls) -> "AppConfig":
        """Load config from disk, or return defaults."""
        path = cls.config_dir() / "config.json"
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return cls(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            return cls()

    def save(self) -> None:
        """Persist config to disk."""
        path = self.config_dir()
        path.mkdir(parents=True, exist_ok=True)
        (path / "config.json").write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def config_path(self) -> Path:
        return self.config_dir() / "config.json"
