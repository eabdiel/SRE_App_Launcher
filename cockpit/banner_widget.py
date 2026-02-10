from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout


class BannerWidget(QFrame):
    """A simple horizontal scrolling banner.

    Text is loaded from a plain text file so non-technical users can update it.
    """

    def __init__(self, banner_file: Path, parent=None):
        super().__init__(parent)
        self.banner_file = Path(banner_file)
        self.setObjectName("BannerWidget")
        self.setFixedHeight(34)

        self._text = ""
        self._offset = 0

        self.label = QLabel("")
        self.label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        f = QFont("Segoe UI", 10)
        f.setBold(True)
        self.label.setFont(f)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 4, 10, 4)
        lay.addWidget(self.label)

        self._marquee_timer = QTimer(self)
        self._marquee_timer.setInterval(30)
        self._marquee_timer.timeout.connect(self._tick)

        self._reload_timer = QTimer(self)
        self._reload_timer.setInterval(2000)
        self._reload_timer.timeout.connect(self.load_text)

        self.load_text()
        self._marquee_timer.start()
        self._reload_timer.start()

    def load_text(self):
        try:
            txt = self.banner_file.read_text(encoding="utf-8", errors="ignore").strip()
        except Exception:
            txt = ""
        if not txt:
            txt = "Tip: edit banner.txt to change this message."
        if txt != self._text:
            self._text = txt
            self._offset = 0

    def _tick(self):
        # Basic marquee: rotate string with padding
        pad = "   •   "
        s = self._text + pad
        if len(s) < 10:
            self.label.setText(s)
            return
        self._offset = (self._offset + 1) % len(s)
        shown = s[self._offset:] + s[:self._offset]
        self.label.setText(shown)
