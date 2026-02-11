#===============================================================================
#  SRE_Applications_Cockpit | runtime_manager.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Summary
#  -------
#  Resolves a usable Python interpreter. Primary target is a bundled runtime under ./runtime/python.exe.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import List


def resolve_python_command(base_dir: Path, state: dict) -> List[str]:
    """Return a command list to invoke Python.

    Resolution order:
      1) state['python_runtime_path'] if set + exists
      2) bundled runtime at <base_dir>/runtime/python.exe (recommended)
      3) current interpreter if running under python.exe (dev mode)
      4) system 'py -3' (Windows)
      5) system 'python' in PATH

    Notes:
      - In your packaged EXE distribution, you'll ship ./runtime/python.exe
        and this will be the primary source of truth.
    """
    configured = (state or {}).get("python_runtime_path") or ""
    if configured:
        p = Path(configured)
        if p.exists():
            return [str(p)]

    bundled = base_dir / "runtime" / "python.exe"
    if bundled.exists():
        return [str(bundled)]

    try:
        cur = Path(sys.executable)
        if cur.exists() and cur.name.lower().startswith("python"):
            return [str(cur)]
    except Exception:
        pass

    if shutil.which("py"):
        return ["py", "-3"]

    if shutil.which("python"):
        return ["python"]

    raise RuntimeError(
        "No Python interpreter found. Bundle one at ./runtime/python.exe or configure python_runtime_path in launcher_state.json."
    )
