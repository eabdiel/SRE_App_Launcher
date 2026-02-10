#===============================================================================
#  APP24_SRE_Application_Cockpit | launcher.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  Process launching utilities (EXE and Python apps). Option-D hooks will live here.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from .models import AppEntry


def launch_app(entry: AppEntry) -> None:
    """Launch an AppEntry.

    NOTE (Option D roadmap):
    - For python apps, we'll eventually route through an isolated per-app runtime.
    - For now, we use sys.executable (the current python interpreter).
    """
    if entry.kind == "exe":
        subprocess.Popen([entry.launch_target], cwd=str(Path(entry.launch_target).parent))
        return

    # Python folder app
    folder = Path(entry.path)
    main_py = Path(entry.launch_target)
    subprocess.Popen([sys.executable, str(main_py)], cwd=str(folder))
