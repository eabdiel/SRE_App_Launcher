#===============================================================================
#  APP24_SRE_Application_Cockpit | ui_widgets.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  Reusable UI widgets (tile list). Keeps the main window/controller smaller.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

from PySide6.QtWidgets import QListWidget
from PySide6.QtCore import QSize

from .constants import ICON_SIZE, TILE_SIZE


class TileList(QListWidget):
    """A grid-ish tile view with built-in internal drag/drop reorder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setMovement(QListWidget.Snap)
        self.setResizeMode(QListWidget.Adjust)
        self.setUniformItemSizes(True)
        self.setIconSize(ICON_SIZE)
        self.setGridSize(TILE_SIZE)
        self.setSpacing(10)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setSelectionMode(QListWidget.SingleSelection)
