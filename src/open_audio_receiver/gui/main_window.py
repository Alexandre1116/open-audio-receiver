"""
Main application window — orchestrates all panels and the system tray icon.
"""
from __future__ import annotations
import logging
from concurrent.futures import Future
from typing import Optional
from PySide6.QtCore import Signal, Slot, QTimer
from PySide6.QtGui import QAction, QCloseEvent, QKeyEvent, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QStyle, QSystemTrayIcon, QVBoxLayout, QWidget,
)
from ..audio import AudioEngine
from ..bluetooth import BluetoothDevice, BluetoothManager, PairingRequest
from ..utils.config import AppConfig
from .audio_settings import AudioSettingsPanel
from .device_panel import DevicePanel

logger = logging.getLogger(__name__)
_PAIRING_TIMEOUT_SECONDS = 60.0

class MainWindow(QMainWindow):
    _pairing_requested = Signal(object, object)

    def __init__(self, app: QApplication):
        super().__init__()
        self._app = app
        self._config = AppConfig.load()
        self._bt_manager: Optional[BluetoothManager] = None
        self._audio_engine: Optional[AudioEngine] = None
        self.setWindowTitle("Open Audio Receiver")
        self.resize(self._config.window_width, self._config.window_height)
        self.setMinimumSize(480, 400)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 12, 16, 12)
        status_layout = QHBoxLayout()
        self._status_dot = QLabel("\u25cf")
        self._status_dot.setStyleSheet("color: #6c7086; font-size: 20px;")
        self._status_label = QLabel("Initialising...")
        self._status_label.setObjectName("statusLabel")
        status_layout.addWidget(self._status_dot)
        status_layout.addWidget(self._status_label, stretch=1)
        layout.addLayout(status_layout)
        self.device_panel = DevicePanel()
        layout.addWidget(self.device_panel, stretch=2)
        self.audio_settings = AudioSettingsPanel()
        layout.addWidget(self.audio_settings)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._start_btn = QPushButton("\u25b6  Start Receiver")
        self._start_btn.setObjectName("primaryButton")
        self._start_btn.clicked.connect(self._toggle_receiver)
        btn_row.addWidget(self._start_btn)
        layout.addLayout(btn_row)
        sec_row = QHBoxLayout()
        sec_row.addStretch()
        self._about_btn = QPushButton("\u2139  About")
        self._about_btn.clicked.connect(self._show_about)
        sec_row.addWidget(self._about_btn)
        self._refresh_audio_btn = QPushButton("\ud83d\udd03 Refresh Audio")
        self._refresh_audio_btn.clicked.connect(self._refresh_audio_devices)
        sec_row.addWidget(self._refresh_audio_btn)
        layout.addLayout(sec_row)
        self.device_panel.disconnect_requested.connect(self._on_disconnect_request)
        self.device_panel.unpair_requested.connect(self._on_unpair_request)
        self.device_panel.refresh_requested.connect(self._refresh_device_list)
        self.audio_settings.output_device_changed.connect(self._on_device_changed)
        self.audio_settings.volume_changed.connect(self._on_volume_changed)
        self._pairing_requested.connect(self._show_pairing_dialog_on_main_thread)
        self._setup_tray()
        self._populate_audio_devices()
        self._apply_config()
        self._update_status("Ready", "idle")

    def _setup_tray(self):
        self._tray_icon = QSystemTrayIcon(self)
        try:
            from importlib.resources import files
            icon_path = files("open_audio_receiver.gui") / "icon.svg"
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                self._tray_icon.setIcon(QIcon(pixmap))
            else:
                raise ValueError("pixmap is null")
        except Exception:
            self._tray_icon.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self._tray_icon.setToolTip("Open Audio Receiver")
        from PySide6.QtWidgets import QMenu
        show_action = QAction("Show Window", self)
        show_action.triggered.connect(self.show)
        toggle_action = QAction("\u25b6 Start", self)
        toggle_action.triggered.connect(self._toggle_receiver)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit)
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

    def _populate_audio_devices(self):
        devices = AudioEngine.list_devices()
        if not devices:
            from ..audio import AudioDevice
            devices = [AudioDevice(id="default", name="System Default", is_default=True)]
        self.audio_settings.populate_devices(devices, self._config.output_device_id)
        logger.info("Found %d audio output devices", len(devices))

    def _apply_config(self):
        self.audio_settings.set_volume(self._config.volume)
        self.audio_settings.auto_accept = self._config.auto_accept_pairing

    @Slot()
    def _toggle_receiver(self):
        if self._bt_manager is not None and self._bt_manager.is_running:
            self._stop_receiver()
        else:
            self._start_receiver()

    def _start_receiver(self):
        def on_pairing(req: PairingRequest) -> bool:
            if self.audio_settings.auto_accept:
                return True
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
            self._start_btn.setText("\u23f9  Stop Receiver")
            self._tray_action.setText("\u23f9 Stop")
            self._update_status("Running", "active")
            logger.info("Receiver started")
        except RuntimeError as exc:
            self._update_status(f"Error: {exc}", "error")
            logger.error("Failed to start receiver: %s", exc)

    def _stop_receiver(self):
        if self._bt_manager:
            self._bt_manager.stop()
            self._bt_manager = None
        if self._audio_engine:
            self._audio_engine.stop()
            self._audio_engine = None
        self._start_btn.setText("\u25b6  Start Receiver")
        self._tray_action.setText("\u25b6 Start")
        self._update_status("Stopped", "idle")
        logger.info("Receiver stopped")

    @Slot(object, object)
    def _show_pairing_dialog_on_main_thread(self, req: PairingRequest, future: Future):
        try:
            future.set_result(self.device_panel.show_pairing_dialog(req))
        except Exception as exc:
            future.set_exception(exc)

    def _update_status(self, text: str, state: str = "idle"):
        colours = {"idle": "#6c7086", "active": "#a6e3a1", "error": "#f38ba8"}
        self._status_label.setText(text)
        self._status_dot.setStyleSheet(f"color: {colours.get(state, '#6c7086')}; font-size: 20px;")

    def _on_device_connected(self, dev: BluetoothDevice):
        logger.info("Device connected: %s (%s)", dev.name, dev.address)
        if self._audio_engine:
            self._audio_engine.attach_source(dev.address, dev.name)
        self._refresh_device_list()

    def _on_device_disconnected(self, dev: BluetoothDevice):
        logger.info("Device disconnected: %s (%s)", dev.name, dev.address)
        if self._audio_engine:
            self._audio_engine.detach_source(dev.address)
        self._refresh_device_list()

    def _refresh_device_list(self):
        if self._bt_manager:
            self.device_panel.update_devices(self._bt_manager.all_devices)

    @Slot(str)
    def _on_disconnect_request(self, address: str):
        if self._bt_manager:
            self._bt_manager.disconnect_device(address)

    @Slot(str)
    def _on_unpair_request(self, address: str):
        if self._bt_manager:
            self._bt_manager.unpair_device(address)

    @Slot(str)
    def _on_device_changed(self, device_id: str):
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
    def _on_volume_changed(self, volume: float):
        self._config.volume = volume
        self._config.save()
        if self._audio_engine:
            self._audio_engine.volume = volume

    @Slot()
    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.raise_()
            self.activateWindow()

    def _show_about(self):
        from .. import __version__
        dlg = QDialog(self)
        dlg.setWindowTitle("About \u2014 Open Audio Receiver")
        dlg.setMinimumWidth(380)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        title = QLabel("\ud83c\udfb5 Open Audio Receiver")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #89b4fa;")
        layout.addWidget(title)
        version = QLabel(f"Version {__version__}")
        version.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(version)
        info = QLabel(
            "A cross-platform Bluetooth audio receiver that lets your PC\n"
            "act as a Bluetooth speaker.\n\n"
            "Receive audio from smartphones, tablets, or other computers\n"
            "via A2DP.\n\n"
            "\u2728 Built with PySide6 \u00b7 BlueZ \u00b7 PipeWire\n"
            "GPL-3.0 License"
        )
        info.setStyleSheet("color: #cdd6f4; font-size: 13px; line-height: 1.6;")
        info.setWordWrap(True)
        layout.addWidget(info, stretch=1)
        ok_btn = QPushButton("Close")
        ok_btn.clicked.connect(dlg.accept)
        layout.addWidget(ok_btn, alignment=2)
        dlg.exec()

    @Slot()
    def _refresh_audio_devices(self):
        self._populate_audio_devices()
        self._update_status("Audio devices refreshed", "idle")
        QTimer.singleShot(2000, lambda: self._update_status("Running" if self._bt_manager else "Ready", "active" if self._bt_manager else "idle"))

    def keyPressEvent(self, event: QKeyEvent):
        from PySide6.QtCore import Qt as Q
        if event.modifiers() & Q.ControlModifier and event.key() == Q.Key_Q:
            self._quit()
        elif event.modifiers() & Q.ControlModifier and event.key() == Q.Key_R:
            self._refresh_audio_devices()
        elif event.key() == Q.Key_Space and self._start_btn.isEnabled():
            self._toggle_receiver()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent):
        if self._config.close_to_tray and self._tray_icon.isVisible():
            event.ignore()
            self.hide()
            self._tray_icon.showMessage("Open Audio Receiver", "The app continues running in the system tray.", QSystemTrayIcon.Information, 2000)
        else:
            self._quit()

    def _quit(self):
        self._stop_receiver()
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        self._config.save()
        QApplication.quit()
