#===============================================================================
#  SRE_Application_Cockpit  |  Central Application Launcher
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  A central launcher that dynamically discovers applications placed under the
#  ./applications folder and presents them as draggable, reorderable tiles.
#  Supports:
#    - Windows executables (.exe)
#    - Python app folders containing a top-level main.py (no deep recursion)
#    - Favorites and Hidden sections (collapsible)
#    - Optional "Load from Git" to sync public GitHub repos listed in
#      ./applications/git-repos when their main branch contains a root main.py
#    - Per-tile icon overrides + persistent UI state (launcher_state.json)
#
#  Folder Conventions
#  ------------------
#    ./applications/
#      - *.exe                            -> shown as launchable tile
#      - <PythonAppFolder>/main.py         -> shown as launchable tile
#      - git-repos                         -> optional list of public GitHub URLs
#
#  Copyright & License Notes
#  -------------------------
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#
#  This source code is provided "AS IS", without warranty of any kind, express
#  or implied, including but not limited to the warranties of merchantability,
#  fitness for a particular purpose, and noninfringement.
#
#  Permission Notice (Personal/Internal Use)
#  -----------------------------------------
#  You may use, copy, and modify this software for personal or internal use.
#  Redistribution or public release should include this header and credit the
#  author. If you plan to open-source this project, consider replacing this
#  section with an OSI-approved license (e.g., MIT) for clarity.
#
#  Third-Party Components
#  ----------------------
#  This project may use third-party libraries (e.g., PySide6, requests) which
#  are licensed separately by their respective authors. Ensure compliance with
#  their license terms when distributing this software.
#===============================================================================

import sys
from PySide6.QtWidgets import QApplication

from cockpit.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1000, 720)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
