"""
Device panel — list of known Bluetooth devices with connect/disconnect controls.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..bluetooth import BluetoothDevice, PairingRequest


class DevicePanel(QWidget):
    """Panel showing paired/connected devices."""

    disconnect_requested = Signal(str)  # address
    unpair_requested = Signal(str)  # address

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Header ────────────────────────────────────────
        header = QLabel("📡 Bluetooth Devices")
        header.setStyleSheet("font-size: 15px; font-weight: 600; margin-bottom: 4px;")
        layout.addWidget(header)

        # ── Device list ───────────────────────────────────
        self.device_list = QListWidget()
        self.device_list.setAlternatingRowColors(False)
        layout.addWidget(self.device_list, stretch=1)

        # ── Buttons row ───────────────────────────────────
        btn_row = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 Refresh")
        btn_row.addWidget(self.refresh_btn)

        self.disconnect_btn = QPushButton("⏹ Disconnect")
        self.disconnect_btn.setEnabled(False)
        btn_row.addWidget(self.disconnect_btn)

        self.unpair_btn = QPushButton("🗑 Unpair")
        self.unpair_btn.setEnabled(False)
        btn_row.addWidget(self.unpair_btn)

        layout.addLayout(btn_row)

        # ── Signals ───────────────────────────────────────
        self.device_list.currentItemChanged.connect(self._on_selection_changed)
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.unpair_btn.clicked.connect(self._on_unpair)

    # ── Public API ──────────────────────────────────────

    def update_devices(self, devices: list[BluetoothDevice]) -> None:
        """Replace the list with fresh device data."""
        self.device_list.clear()
        for dev in devices:
            icon = "🔵" if dev.is_connected else "⚪"
            text = f"{icon}  {dev.name}\n    {dev.address}  ·  {dev.codec}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, dev.address)
            item.setData(Qt.UserRole + 1, dev.is_connected)
            self.device_list.addItem(item)

    def show_pairing_dialog(self, req: PairingRequest) -> bool:
        """Show a modal pairing confirmation dialog.  Returns True if accepted."""
        msg = QMessageBox(self)
        msg.setWindowTitle("🔗 Bluetooth Pairing Request")
        msg.setText(
            f"<b>{req.name}</b> wants to pair with your computer.<br><br>"
            f"<b>Address:</b> {req.address}<br>"
            f"<b>Type:</b> A2DP Audio Sink"
        )
        msg.setIcon(QMessageBox.Question)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.Yes)
        return msg.exec() == QMessageBox.Yes

    # ── Slots ───────────────────────────────────────────

    @Slot()
    def _on_selection_changed(self) -> None:
        item = self.device_list.currentItem()
        if item is None:
            self.disconnect_btn.setEnabled(False)
            self.unpair_btn.setEnabled(False)
            return
        is_connected = item.data(Qt.UserRole + 1)
        self.disconnect_btn.setEnabled(bool(is_connected))
        self.unpair_btn.setEnabled(True)

    @Slot()
    def _on_disconnect(self) -> None:
        item = self.device_list.currentItem()
        if item is not None:
            addr = item.data(Qt.UserRole)
            self.disconnect_requested.emit(addr)

    @Slot()
    def _on_unpair(self) -> None:
        item = self.device_list.currentItem()
        if item is not None:
            addr = item.data(Qt.UserRole)
            self.unpair_requested.emit(addr)
