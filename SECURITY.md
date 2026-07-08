# Security Policy

## Supported Versions

Only the latest tagged release and the `main` branch are supported with security updates.

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | ✅                 |

## Reporting a Vulnerability

**Do not open a public issue.** Instead, email the maintainer:

📧 alexandremarquesramos11@gmail.com

You will receive a response within 72 hours. Once confirmed, we will:

1. Acknowledge the report within 3 business days
2. Provide a timeline for the fix
3. Credit the reporter in the release notes (unless you prefer anonymity)

## Scope

The app runs locally and does not expose network services. The primary security concerns are:

- **Command injection** via subprocess calls (e.g. `bluetoothctl`, `pactl`)
- **Configuration file tampering** (user-writable `config.json`)
- **Bluetooth pairing** — only accept devices the user explicitly approves

## Best Practices for Contributors

1. **Never** interpolate unsanitized user input into shell commands — use argument lists (`subprocess.run(["cmd", arg1, arg2])`), never string concatenation with `shell=True`.
2. Validate all Bluetooth addresses match the format `XX:XX:XX:XX:XX:XX` before passing to subprocess.
3. Validate volume ranges (0.0–1.0) and codec values against a known allowlist.
4. Config values are loaded from a local JSON file only; never from environment variables or remote sources.