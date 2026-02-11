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
