"""
Dark theme QSS for the Open Audio Receiver GUI.
"""

DARK_QSS = """
/* ── Global ─────────────────────────────────────────── */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Noto Sans", system-ui, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1e1e2e;
}

/* ── Buttons ────────────────────────────────────────── */
QPushButton {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 16px;
    color: #cdd6f4;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #45475a;
    border-color: #585b70;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton:disabled {
    background-color: #313244;
    color: #6c7086;
    border-color: #313244;
}

/* ── Primary action button ──────────────────────────── */
QPushButton#primaryButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: 600;
    border: none;
}
QPushButton#primaryButton:hover {
    background-color: #b4d0fb;
}
QPushButton#primaryButton:pressed {
    background-color: #74c7ec;
}
QPushButton#primaryButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}

/* ── Group boxes ────────────────────────────────────── */
QGroupBox {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 20px;
    padding: 16px 12px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 10px;
    color: #a6adc8;
}

/* ── Labels ─────────────────────────────────────────── */
QLabel {
    background: transparent;
    color: #cdd6f4;
}
QLabel#statusLabel {
    color: #a6adc8;
    font-size: 12px;
}

/* ── List widgets ───────────────────────────────────── */
QListWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 6px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    padding: 6px 10px;
    border-radius: 4px;
}
QListWidget::item:selected {
    background-color: #313244;
    color: #cdd6f4;
}
QListWidget::item:hover {
    background-color: #45475a;
}

/* ── Combo boxes ────────────────────────────────────── */
QComboBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px 10px;
    min-height: 28px;
}
QComboBox:hover {
    border-color: #585b70;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background-color: #181825;
    border: 1px solid #45475a;
    selection-background-color: #313244;
}

/* ── Sliders ────────────────────────────────────────── */
QSlider::groove:horizontal {
    background: #313244;
    height: 4px;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #89b4fa;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::handle:horizontal:hover {
    background: #b4d0fb;
}

/* ── Check boxes ────────────────────────────────────── */
QCheckBox {
    spacing: 8px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #585b70;
    border-radius: 3px;
    background: #181825;
}
QCheckBox::indicator:checked {
    background: #89b4fa;
    border-color: #89b4fa;
}

/* ── Scroll bars ────────────────────────────────────── */
QScrollBar:vertical {
    background: #181825;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover {
    background: #585b70;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* ── System tray icon menu ──────────────────────────── */
QMenu {
    background-color: #181825;
    border: 1px solid #313244;
    padding: 4px;
}
QMenu::item {
    padding: 6px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #313244;
}
QMenu::separator {
    height: 1px;
    background: #313244;
    margin: 4px 8px;
}
"""
