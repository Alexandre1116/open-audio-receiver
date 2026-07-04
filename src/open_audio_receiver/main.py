"""
Entry point for Open Audio Receiver.

Usage:
    open-audio-receiver          # starts the GUI
    open-audio-receiver -v       # verbose/debug logging
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from .gui import DARK_QSS, MainWindow
from .utils import setup_logging


def main() -> None:
    setup_logging()

    # High-DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Open Audio Receiver")
    app.setApplicationDisplayName("Open Audio Receiver")
    app.setOrganizationName("open-audio-receiver")
    app.setStyle("Fusion")

    # Apply dark theme
    app.setStyleSheet(DARK_QSS)

    # Default font
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)

    # Launch main window
    window = MainWindow(app)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
