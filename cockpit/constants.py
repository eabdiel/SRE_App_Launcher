#===============================================================================
#  SRE_Applications_Cockpit | constants.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Summary
#  -------
#  Central place for UI sizing, theme, and file/folder naming conventions.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

from PySide6.QtCore import QSize

APP_TITLE = "SRE Applications Cockpit"
APP_FOLDER_NAME = "applications"
STATE_FILE_NAME = "launcher_state.json"
GIT_REPOS_FILE_NAME = "git-repos"

# --- Metro / Windows Phone style theme ---
METRO_BG = "#101010"

METRO_TILE_COLORS = [
    "#0078D7",  # blue
    "#00B294",  # teal
    "#E81123",  # red
    "#FFB900",  # yellow
    "#8764B8",  # purple
    "#2D7D9A",  # steel
    "#107C10",  # green
    "#5C2D91",  # deep purple
]

# Tile sizes (approximate Windows Phone "small" and "wide")
TILE_SMALL = QSize(150, 110)
TILE_WIDE = QSize(300, 110)

# Grid size should accommodate the widest tile so mixed sizes can coexist
GRID_SIZE = TILE_WIDE
