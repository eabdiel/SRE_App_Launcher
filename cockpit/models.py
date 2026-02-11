#===============================================================================
#  SRE_Applications_Cockpit | models.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Summary
#  -------
#  Shared data models used across the cockpit application.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppEntry:
    """Represents a launchable application discovered under ./applications."""
    key: str            # stable key for state (path-based)
    display_name: str   # default title (can be overridden by state)
    kind: str           # "py" | "exe" | "lnk" | "urlfile" | "git" | "url"
    path: str           # exe path OR folder path
    launch_target: str  # exe path OR main.py path
