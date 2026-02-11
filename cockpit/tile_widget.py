#===============================================================================
#  SRE_Applications_Cockpit | tile_widget.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Summary
#  -------
#  Metro/Windows-Phone style tile widgets (small/wide) for the cockpit UI.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


@dataclass
class TileVisual:
    bg_color: str
    title: str
    subtitle: str = ""
    icon: Optional[QIcon] = None


class TileWidget(QFrame):
    """A flat, Metro-style tile used inside a QListWidget item."""

    def __init__(self, visual: TileVisual, size: QSize, parent=None):
        super().__init__(parent)
        self.setObjectName("MetroTile")
        self.setFixedSize(size)

        self.setStyleSheet(f"""
        QFrame#MetroTile {{
            background: {visual.bg_color};
        }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        icon_label.setFixedHeight(36)
        if visual.icon:
            icon_label.setPixmap(visual.icon.pixmap(28, 28))
        layout.addWidget(icon_label)

        layout.addStretch(1)

        title_label = QLabel(visual.title)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        title_font = QFont("Segoe UI", 11)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: white;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        subtitle_label = QLabel(visual.subtitle)
        subtitle_label.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
        sub_font = QFont("Segoe UI", 9)
        subtitle_label.setFont(sub_font)
        subtitle_label.setStyleSheet("color: rgba(255,255,255,0.85);")
        subtitle_label.setWordWrap(True)
        subtitle_label.setVisible(bool(visual.subtitle.strip()))
        layout.addWidget(subtitle_label)
