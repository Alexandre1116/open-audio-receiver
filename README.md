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

## Building

```bash
pip install -e .
pip install pyinstaller
pyinstaller --onefile --windowed src/open_audio_receiver/main.py
```

## License

MIT
