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



def parse_import_args(argv: list[str]) -> tuple[Path | None, bool]:
    """Parse command-line args for SendTo / import usage.

    Supported:
      - SRE_Application_Cockpit.exe --import "<path>" [--prompt]
      - SRE_Application_Cockpit.exe "<path>"   (legacy/simple)
    """
    path: Path | None = None
    prompt = False

    args = argv[1:]
    if not args:
        return None, False

    # flags
    if "--prompt" in args:
        prompt = True
        args = [a for a in args if a != "--prompt"]

    if "--import" in args:
        try:
            i = args.index("--import")
            if i + 1 < len(args):
                path = Path(args[i + 1]).expanduser()
        except ValueError:
            pass
    else:
        # If launched with a single positional argument, treat it as a path.
        if len(args) == 1 and not args[0].startswith("-"):
            path = Path(args[0]).expanduser()

    if path is not None:
        try:
            path = path.resolve()
        except Exception:
            pass
    return path, prompt


def main() -> int:
    # Let cockpit modules know where the "real" runtime folder is.
    os.environ["SRE_COCKPIT_BASE_DIR"] = str(BASE_DIR)

    app = QApplication(sys.argv)

    import_path, prompt = parse_import_args(sys.argv)
    w = MainWindow(import_path=import_path, prompt_import=prompt)
    w.resize(1000, 720)
    w.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
