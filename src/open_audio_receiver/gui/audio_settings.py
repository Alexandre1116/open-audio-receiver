"""
Audio settings panel — output device selector, volume slider, codec preference.
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGroupBox, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget)
from ..audio import AudioDevice

class AudioSettingsPanel(QWidget):
    output_device_changed = Signal(str)
    volume_changed = Signal(float)
    codec_changed = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        group = QGroupBox("🔊 Audio Output")
        group_layout = QVBoxLayout(group)
        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(220)
        dev_row.addWidget(self.device_combo, stretch=1)
        group_layout.addLayout(dev_row)
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
        codec_row = QHBoxLayout()
        codec_row.addWidget(QLabel("Codec:"))
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["Auto", "SBC", "AAC", "aptX", "LDAC"])
        codec_row.addWidget(self.codec_combo, stretch=1)
        group_layout.addLayout(codec_row)
        self.auto_accept_cb = QCheckBox("Auto-accept pairing requests")
        group_layout.addWidget(self.auto_accept_cb)
        layout.addWidget(group)
        self.device_combo.currentIndexChanged.connect(self._on_device_changed)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.codec_combo.currentIndexChanged.connect(self._on_codec_changed)

    def populate_devices(self, devices: list[AudioDevice], default_id: str = "default"):
        self.device_combo.blockSignals(True)
        self.device_combo.clear()
        for dev in devices:
            self.device_combo.addItem(dev.name, dev.id)
        idx = self.device_combo.findData(default_id)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        self.device_combo.blockSignals(False)

    @property
    def auto_accept(self) -> bool:
        return self.auto_accept_cb.isChecked()

    @auto_accept.setter
    def auto_accept(self, val: bool):
        self.auto_accept_cb.setChecked(val)

    def set_volume(self, value: float):
        self.volume_slider.setValue(int(value * 100))

    def set_codec(self, codec: str):
        idx = self.codec_combo.findText(codec, Qt.MatchFixedString)
        if idx >= 0:
            self.codec_combo.setCurrentIndex(idx)

    @Slot(int)
    def _on_device_changed(self, index: int):
        device_id = self.device_combo.itemData(index)
        if device_id:
            self.output_device_changed.emit(device_id)

    @Slot(int)
    def _on_volume_changed(self, value: int):
        pct = value / 100.0
        self.volume_label.setText(f"{value}%")
        self.volume_changed.emit(pct)

    @Slot(int)
    def _on_codec_changed(self, index: int):
        codec = self.codec_combo.itemText(index)
        self.codec_changed.emit(codec)
