#===============================================================================
#  SRE_Applications_Cockpit | fs_discovery.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Summary
#  -------
#  Filesystem discovery utilities for executables and Python folder apps.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from .models import AppEntry


def safe_key(p: Path) -> str:
    """Stable key for state, derived from absolute normalized path."""
    try:
        return str(p.resolve()).lower()
    except Exception:
        return str(p.absolute()).lower()


def find_python_main(folder: Path) -> Optional[Path]:
    """Find a launchable python entrypoint within *one* folder level.

    Rules:
    - Prefer ./main.py
    - Otherwise use the first file matching main*.py at the top level
    - Do not recurse into subfolders
    """
    if not folder.is_dir():
        return None

    main_py = folder / "main.py"
    if main_py.exists() and main_py.is_file():
        return main_py

    candidates = sorted([
        p for p in folder.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".py"
        and p.name.lower().startswith("main")
    ])
    return candidates[0] if candidates else None


def scan_applications_folder(apps_dir: Path) -> List[AppEntry]:
    """Scan ./applications and return launchable app entries.

    Supports:
      - .exe
      - .lnk (Windows shortcut)
      - Python app folders containing a main.py at top-level (no deep search)
    """
    apps: List[AppEntry] = []
    if not apps_dir.exists():
        apps_dir.mkdir(parents=True, exist_ok=True)

    for item in sorted(apps_dir.iterdir(), key=lambda p: p.name.lower()):
        # EXE
        if item.is_file() and item.suffix.lower() == ".exe":
            key = safe_key(item)
            apps.append(
                AppEntry(
                    key=key,
                    display_name=item.stem,
                    kind="exe",
                    path=str(item),
                    launch_target=str(item),
                )
            )
            continue

        # Windows shortcut (.lnk) - treat as launchable
        if item.is_file() and item.suffix.lower() == ".lnk":
            key = safe_key(item)
            apps.append(
                AppEntry(
                    key=key,
                    display_name=item.stem,
                    kind="lnk",
                    path=str(item),
                    launch_target=str(item),
                )
            )
            continue


        # Website shortcut (.url)
        if item.is_file() and item.suffix.lower() == ".url":
            key = safe_key(item)
            apps.append(
                AppEntry(
                    key=key,
                    display_name=item.stem,
                    kind="urlfile",
                    path=str(item),
                    launch_target=str(item),
                )
            )
            continue

        # Python folder app
        if item.is_dir():
            main_file = find_python_main(item)
            if main_file:
                key = safe_key(item)
                apps.append(
                    AppEntry(
                        key=key,
                        display_name=item.name,
                        kind="py",
                        path=str(item),
                        launch_target=str(main_file),
                    )
                )

    return apps

