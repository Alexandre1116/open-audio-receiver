# Open Audio Receiver

A cross-platform Bluetooth audio receiver that lets your PC act as a Bluetooth
speaker — receive audio from smartphones, tablets, or other computers.

## Features

- 🎵 **A2DP Sink** — Receive high-quality audio via Bluetooth
- 🖥️ **Cross‑platform** — Windows (primary) and Linux
- 🎚️ **Audio output selection** — Choose your speakers, headphones, etc.
- 🔔 **Pairing confirmation** — Pop‑up request for each new device
- 🎨 **Modern dark GUI** — Built with PySide6

## Installation

### Windows

```powershell
pip install PySide6 pywinrt pycaw comtypes
```

### Linux

```bash
sudo apt install python3-dbus python3-gi libbluetooth-dev pipewire
pip install PySide6 dbus-python PyGObject
```

## Usage

```bash
open-audio-receiver
```

Or directly:

```bash
python -m open_audio_receiver.main
```

## Requirements

- **Windows:** Windows 10/11 with Bluetooth adapter
- **Linux:** BlueZ and PipeWire installed
- Python 3.10+

## How it works

1. The app advertises itself as an A2DP Sink Bluetooth device
2. When a phone/computers connects, a pop‑up asks for confirmation
3. Audio is received via Bluetooth and played to your chosen output device
4. Use the system tray icon to control everything

### Platform status

- **Linux:** the app makes the adapter discoverable, registers a BlueZ pairing
  agent (needs `dbus-python` + `PyGObject`, see Installation) so pairing
  requests trigger the confirmation pop-up, and tracks device connect/disconnect
  via D-Bus. BlueZ + PipeWire/WirePlumber decode the incoming A2DP stream
  automatically; the app routes it to your chosen output device with a
  `pactl` loopback. If it can't find a matching capture source (naming varies
  across PipeWire versions), route it manually with `pavucontrol`/`qpwgraph`.
- **Windows:** pairing confirmation works over BLE advertisements as an MVP
  proxy, but real A2DP audio playback is **not implemented**. Windows does
  not expose a public API for a third-party app to register as a Bluetooth
  A2DP Sink and receive decoded audio — that normally requires a signed
  Bluetooth profile driver (as bundled with some third-party Bluetooth audio
  receiver dongles), which is out of scope for an application-level project.

## Building

```bash
pip install -e .
pip install pyinstaller
pyinstaller --onefile --windowed --name open-audio-receiver --paths src run.py
```

The build produces a single-file executable in `dist/` (`open-audio-receiver.exe` on
Windows, `open-audio-receiver` on Linux). Building on Linux produces a Linux binary
and building on Windows produces a Windows `.exe` — PyInstaller does not cross-compile,
so run it on the target OS.

## License

MIT
