"""
+--------------------------------------------------------------------------------------+
|  ProgreTomato - Automation Workbench (Windows)                                        |
+--------------------------------------------------------------------------------------+
|  Author: Edwin A. Rodriguez                                                          |
|  Title : Software Reliability Engineer / SAP SRE                                      |
|                                                                                      |
|  Solution Summary:                                                                   |
|    ProgreTomato is a Windows-only automation workbench that records user actions     |
|    (clicks, typing, hotkeys, clipboard outputs) and replays them as a runnable        |
|    automation. It supports editing steps, exporting to Excel, and saving/loading      |
|    projects to JSON, serving as a center-console for building reusable automations.  |
|                                                                                      |
|  Notes:                                                                              |
|    - Current runner replays by coords + keystrokes (MVP).                             |
|    - Next upgrades: target lock filtering, better typing model, UIA locators,         |
|      and a step debugger.                                                            |
+--------------------------------------------------------------------------------------+
"""

from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication
from ui_main import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
