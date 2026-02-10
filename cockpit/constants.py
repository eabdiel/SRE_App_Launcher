#===============================================================================
#  APP24_SRE_Application_Cockpit | constants.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  Central place for UI sizing and file/folder naming conventions.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

from PySide6.QtCore import QSize

APP_TITLE = "App Launcher"
APP_FOLDER_NAME = "applications"
STATE_FILE_NAME = "launcher_state.json"
GIT_REPOS_FILE_NAME = "git-repos"

TILE_SIZE = QSize(110, 110)     # square tile footprint
ICON_SIZE = QSize(48, 48)
