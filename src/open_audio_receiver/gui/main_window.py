"""
Main application window — orchestrates all panels and the system tray icon.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future
from typing import Optional

from PySide6.QtCore import Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from ..audio import AudioEngine
from ..bluetooth import BluetoothDevice, BluetoothManager, PairingRequest
from ..utils.config import AppConfig
from .audio_settings import AudioSettingsPanel
from .device_panel import DevicePanel

logger = logging.getLogger(__name__)

# Bluetooth backends fire pairing requests from their own worker thread
# (a WinRT event thread on Windows, a GLib D-Bus loop on Linux). Qt widgets
# may only be touched from the GUI thread, so the request is bounced onto it
# through a queued signal and the answer is handed back via a Future.
_PAIRING_TIMEOUT_SECONDS = 60.0


class MainWindow(QMainWindow):
    """Main window for the Open Audio Receiver."""

    _pairing_requested = Signal(object, object)  # (PairingRequest, Future[bool])

    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        self._config = AppConfig.load()
        self._bt_manager: Optional[BluetoothManager] = None
        self._audio_engine: Optional[AudioEngine] = None

        self.setWindowTitle("Open Audio Receiver")
        self.resize(self._config.window_width, self._config.window_height)
        self.setMinimumSize(480, 400)

        # ── Central widget ─────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)

        # ── Status bar ─────────────────────────────────────
        status_layout = QHBoxLayout()
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #6c7086; font-size: 20px;")
        self._status_label = QLabel("Initialising...")
        self._status_label.setObjectName("statusLabel")
        status_layout.addWidget(self._status_dot)
        status_layout.addWidget(self._status_label, stretch=1)
        layout.addLayout(status_layout)

        # ── Device panel ───────────────────────────────────
        self.device_panel = DevicePanel()
        layout.addWidget(self.device_panel, stretch=2)

        # ── Audio settings ─────────────────────────────────
        self.audio_settings = AudioSettingsPanel()
        layout.addWidget(self.audio_settings)

        # ── Start/Stop button ──────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._start_btn = QPushButton("▶  Start Receiver")
        self._start_btn.setObjectName("primaryButton")
        self._start_btn.clicked.connect(self._toggle_receiver)
        btn_row.addWidget(self._start_btn)
        layout.addLayout(btn_row)

        # ── Wire signals ────────────────────────────────────
        self.device_panel.disconnect_requested.connect(self._on_disconnect_request)
        self.device_panel.unpair_requested.connect(self._on_unpair_request)
        self.audio_settings.output_device_changed.connect(self._on_device_changed)
        self.audio_settings.volume_changed.connect(self._on_volume_changed)
        self._pairing_requested.connect(self._show_pairing_dialog_on_main_thread)

        # ── System tray ────────────────────────────────────
        self._setup_tray()

        # ── Populate UI ────────────────────────────────────
        self._populate_audio_devices()
        self._apply_config()
        self._update_status("Ready", "idle")

    # ── Initialisation helpers ────────────────────────────

    def _setup_tray(self) -> None:
        self._tray_icon = QSystemTrayIcon(self)
        # Built-in icon as fallback; custom icon can be set later
        self._tray_icon.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self._tray_icon.setToolTip("Open Audio Receiver")

        from PySide6.QtWidgets import QMenu

        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show)
        toggle_action = QAction("▶ Start", self)
        toggle_action.triggered.connect(self._toggle_receiver)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)

        # Build menu
        menu = QMenu()
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(toggle_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray_menu = menu
        self._tray_action = toggle_action
        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _populate_audio_devices(self) -> None:
        devices = AudioEngine.list_devices()
        self.audio_settings.populate_devices(devices, self._config.output_device_id)
        logger.info("Found %d audio output devices", len(devices))

    def _apply_config(self) -> None:
        self.audio_settings.set_volume(self._config.volume)
        self.audio_settings.auto_accept = self._config.auto_accept_pairing

    # ── Receiver lifecycle ────────────────────────────────

    @Slot()
    def _toggle_receiver(self) -> None:
        if self._bt_manager is not None and self._bt_manager.is_running:
            self._stop_receiver()
        else:
            self._start_receiver()

    def _start_receiver(self) -> None:
        def on_pairing(req: PairingRequest) -> bool:
            if self.audio_settings.auto_accept:
                return True
            # May be called from a non-GUI thread (WinRT/D-Bus worker) — bounce
            # the dialog onto the main thread and wait for the answer.
            future: Future = Future()
            self._pairing_requested.emit(req, future)
            try:
                return future.result(timeout=_PAIRING_TIMEOUT_SECONDS)
            except Exception:
                logger.warning("Pairing confirmation for %s timed out or failed", req.address)
                return False

        try:
            self._bt_manager = BluetoothManager.create(on_pairing=on_pairing)
            self._bt_manager.on_device_connected(self._on_device_connected)
            self._bt_manager.on_device_disconnected(self._on_device_disconnected)
            self._bt_manager.start(self._config.adapter_address)

            self._audio_engine = AudioEngine.create(self._config.output_device_id)
            self._audio_engine.volume = self._config.volume
            self._audio_engine.start()

            self._start_btn.setText("⏹  Stop Receiver")
            self._tray_action.setText("⏹ Stop")
            self._update_status("Running", "active")
            logger.info("Receiver started")
        except RuntimeError as exc:
            self._update_status(f"Error: {exc}", "error")
            logger.error("Failed to start receiver: %s", exc)

    def _stop_receiver(self) -> None:
        if self._bt_manager:
            self._bt_manager.stop()
            self._bt_manager = None
        if self._audio_engine:
            self._audio_engine.stop()
            self._audio_engine = None
        self._start_btn.setText("▶  Start Receiver")
        self._tray_action.setText("▶ Start")
        self._update_status("Stopped", "idle")
        logger.info("Receiver stopped")

    @Slot(object, object)
    def _show_pairing_dialog_on_main_thread(self, req: PairingRequest, future: Future) -> None:
        try:
            future.set_result(self.device_panel.show_pairing_dialog(req))
        except Exception as exc:  # defensive: never let this crash the GUI thread
            future.set_exception(exc)

    # ── Status helper ───────────────────────────────────

    def _update_status(self, text: str, state: str = "idle") -> None:
        """Update status label and dot colour."""
        colours = {
            "idle": "#6c7086",
            "active": "#a6e3a1",
            "error": "#f38ba8",
        }
        self._status_label.setText(text)
        self._status_dot.setStyleSheet(
            f"color: {colours.get(state, '#6c7086')}; font-size: 20px;"
        )

    # ── Bluetooth callbacks ──────────────────────────────

    def _on_device_connected(self, dev: BluetoothDevice) -> None:
        logger.info("Device connected: %s (%s)", dev.name, dev.address)
        if self._audio_engine:
            self._audio_engine.attach_source(dev.address, dev.name)
        self._refresh_device_list()

    def _on_device_disconnected(self, dev: BluetoothDevice) -> None:
        logger.info("Device disconnected: %s (%s)", dev.name, dev.address)
        if self._audio_engine:
            self._audio_engine.detach_source(dev.address)
        self._refresh_device_list()

    def _refresh_device_list(self) -> None:
        if self._bt_manager:
            self.device_panel.update_devices(self._bt_manager.all_devices)

    # ── Slots from UI ────────────────────────────────────

    @Slot(str)
    def _on_disconnect_request(self, address: str) -> None:
        if self._bt_manager:
            self._bt_manager.disconnect_device(address)

    @Slot(str)
    def _on_unpair_request(self, address: str) -> None:
        if self._bt_manager:
            self._bt_manager.unpair_device(address)

    @Slot(str)
    def _on_device_changed(self, device_id: str) -> None:
        self._config.output_device_id = device_id
        self._config.save()
        logger.info("Output device changed to %s", device_id)
        if self._audio_engine and self._bt_manager:
            connected = list(self._bt_manager.connected_devices)
            self._audio_engine.stop()
            self._audio_engine = AudioEngine.create(device_id)
            self._audio_engine.volume = self._config.volume
            self._audio_engine.start()
            for dev in connected:
                self._audio_engine.attach_source(dev.address, dev.name)

    @Slot(float)
    def _on_volume_changed(self, volume: float) -> None:
        self._config.volume = volume
        self._config.save()
        if self._audio_engine:
            self._audio_engine.volume = volume

    @Slot()
    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()

    # ── Close / quit ─────────────────────────────────────

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._config.close_to_tray and self._tray_icon.isVisible():
            event.ignore()
            self.hide()
            self._tray_icon.showMessage(
                "Open Audio Receiver",
                "The app continues running in the system tray.",
                QSystemTrayIcon.Information,
                2000,
            )
        else:
            self._quit()

    def _quit(self) -> None:
        self._stop_receiver()
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        self._config.save()
        QApplication.quit()
