#===============================================================================
#  SRE_Applications_Cockpit | main.py (entrypoint)
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Summary
#  -------
#  Thin entrypoint that boots the Qt application and shows the MainWindow.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from cockpit.main_window import MainWindow


def app_root() -> Path:
    """
    Resolve the runtime folder that should hold banner.txt, applications/, and state files.

    - In dev: folder containing main.py
    - In PyInstaller onefile: folder containing the .exe
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


BASE_DIR = app_root()


def main() -> int:
    # Let cockpit modules know where the "real" runtime folder is.
    os.environ["SRE_COCKPIT_BASE_DIR"] = str(BASE_DIR)

    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1000, 720)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
