"""
Device panel — list of known Bluetooth devices with connect/disconnect controls.
"""
from __future__ import annotations
import time
from typing import Optional
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout, QWidget)
from ..bluetooth import BluetoothDevice, PairingRequest

class DevicePanel(QWidget):
    disconnect_requested = Signal(str)
    unpair_requested = Signal(str)
    refresh_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        header_row = QHBoxLayout()
        header = QLabel("📡 Bluetooth Devices")
        header.setStyleSheet("font-size: 15px; font-weight: 600; margin-bottom: 4px;")
        header_row.addWidget(header)
        header_row.addStretch()
        self._device_count = QLabel("")
        self._device_count.setStyleSheet("color: #6c7086; font-size: 12px;")
        header_row.addWidget(self._device_count)
        layout.addLayout(header_row)
        self.device_list = QListWidget()
        self.device_list.setAlternatingRowColors(False)
        layout.addWidget(self.device_list, stretch=1)
        self._empty_label = QLabel("No devices paired yet.\nStart the receiver and pair from your phone/computer.")
        self._empty_label.setStyleSheet("color: #6c7086; font-size: 13px; text-align: center; padding: 40px;")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)
        btn_row = QHBoxLayout()
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setToolTip("Re-scan for Bluetooth devices (Ctrl+R)")
        btn_row.addWidget(self.refresh_btn)
        self.disconnect_btn = QPushButton("⏹ Disconnect")
        self.disconnect_btn.setEnabled(False)
        btn_row.addWidget(self.disconnect_btn)
        self.unpair_btn = QPushButton("🗑 Unpair")
        self.unpair_btn.setEnabled(False)
        btn_row.addWidget(self.unpair_btn)
        layout.addLayout(btn_row)
        self.device_list.currentItemChanged.connect(self._on_selection_changed)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.unpair_btn.clicked.connect(self._on_unpair)
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)

    def update_devices(self, devices: list[BluetoothDevice]):
        self.device_list.clear()
        self._device_count.setText(f"{len(devices)} device(s)")
        if not devices:
            self._empty_label.show()
            self.device_list.hide()
            return
        self._empty_label.hide()
        self.device_list.show()
        for dev in devices:
            status = "Connected" if dev.is_connected else "Disconnected"
            text = f"{'🔵' if dev.is_connected else '⚪'}  {dev.name}\n    {dev.address}  ·  {dev.codec}  ·  {status}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, dev.address)
            item.setData(Qt.UserRole + 1, dev.is_connected)
            self.device_list.addItem(item)

    def show_pairing_dialog(self, req: PairingRequest) -> bool:
        msg = QMessageBox(self)
        msg.setWindowTitle("🔗 Bluetooth Pairing Request")
        msg.setText(f"<b>{req.name}</b> wants to pair with your computer.<br><br><b>Address:</b> {req.address}<br><b>Type:</b> A2DP Audio Sink")
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        return msg.exec() == QMessageBox.Yes

    @Slot()
    def _on_selection_changed(self):
        item = self.device_list.currentItem()
        if item is None:
            self.disconnect_btn.setEnabled(False)
            self.unpair_btn.setEnabled(False)
            return
        self.disconnect_btn.setEnabled(bool(item.data(Qt.UserRole + 1)))
        self.unpair_btn.setEnabled(True)

    @Slot()
    def _on_disconnect(self):
        item = self.device_list.currentItem()
        if item is not None:
            self.disconnect_requested.emit(item.data(Qt.UserRole))

    @Slot()
    def _on_unpair(self):
        item = self.device_list.currentItem()
        if item is not None:
            self.unpair_requested.emit(item.data(Qt.UserRole))
