"""
Audio settings panel — output device selector, volume slider, codec preference.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..audio import AudioDevice


class AudioSettingsPanel(QWidget):
    """Panel for audio output configuration."""

    output_device_changed = Signal(str)  # device_id
    volume_changed = Signal(float)  # 0.0 - 1.0

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Output device selection ───────────────────────
        group = QGroupBox("🔊 Audio Output")
        group_layout = QVBoxLayout(group)

        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(220)
        dev_row.addWidget(self.device_combo, stretch=1)
        group_layout.addLayout(dev_row)

        # ── Volume ─────────────────────────────────────────
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("🔉"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(100)
        vol_row.addWidget(self.volume_slider, stretch=1)
        self.volume_label = QLabel("100%")
        self.volume_label.setMinimumWidth(40)
        self.volume_label.setAlignment(Qt.AlignRight)
        vol_row.addWidget(self.volume_label)
        group_layout.addLayout(vol_row)

        # ── Codec preference ───────────────────────────────
        codec_row = QHBoxLayout()
        codec_row.addWidget(QLabel("Codec:"))
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["Auto", "SBC", "AAC", "aptX", "LDAC"])
        codec_row.addWidget(self.codec_combo, stretch=1)
        group_layout.addLayout(codec_row)

        # ── Auto-accept pairing ───────────────────────────
        self.auto_accept_cb = QCheckBox("Auto-accept pairing requests")
        group_layout.addWidget(self.auto_accept_cb)

        layout.addWidget(group)

        # ── Signals ───────────────────────────────────────
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)

    # ── Public API ──────────────────────────────────────

    def populate_devices(self, devices: list[AudioDevice], default_id: str = "default") -> None:
        """Fill the device combo box."""
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for dev in devices:
            self.device_combo.addItem(dev.name, dev.id)
        # Find default
        idx = self.device_combo.findData(default_id)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        self.device_combo.blockSignals(False)

    @property
    def auto_accept(self) -> bool:
        return self.auto_accept_cb.isChecked()

    @auto_accept.setter
    def auto_accept(self, val: bool) -> None:
        self.auto_accept_cb.setChecked(val)

    def set_volume(self, value: float) -> None:
        """Set volume from 0.0 - 1.0."""
        self.volume_slider.setValue(int(value * 100))

    # ── Slots ───────────────────────────────────────────

    @Slot(int)
    def _on_device_changed(self, index: int) -> None:
        device_id = self.device_combo.itemData(index)
        if device_id:
            self.output_device_changed.emit(device_id)

    @Slot(int)
    def _on_volume_changed(self, value: int) -> None:
        pct = value / 100.0
        self.volume_label.setText(f"{value}%")
        self.volume_changed.emit(pct)
