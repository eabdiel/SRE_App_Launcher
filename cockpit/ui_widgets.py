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
#  Reusable UI widgets (tile lists) with Metro-friendly defaults.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

from PySide6.QtWidgets import QListWidget, QListView

from .constants import GRID_SIZE


class TileList(QListWidget):
    """A grid-ish tile view with built-in internal drag/drop reorder."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setFlow(QListView.LeftToRight)
        self.setWrapping(True)
        self.setMovement(QListWidget.Snap)
        self.setResizeMode(QListWidget.Adjust)
        self.setSpacing(6)
        self.setContentsMargins(6, 6, 6, 6)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setSelectionMode(QListWidget.SingleSelection)

        self.setGridSize(GRID_SIZE)
