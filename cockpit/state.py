#===============================================================================
#  APP24_SRE_Application_Cockpit | state.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  Load/save and maintenance of persistent cockpit state (tile order, favorites, icons, etc.).
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any


def default_state() -> Dict[str, Any]:
    return {
        "title_overrides": {},  # key -> title
        "favorites": [],        # list of keys (order)
        "hidden": [],           # list of keys (order)
        "order": [],            # main list order of keys
        "icon_overrides": {},   # key -> absolute path to png/ico/jpg
    }


def load_state(state_path: Path) -> Dict[str, Any]:
    """Load state from disk (or create defaults)."""
    d = default_state()
    if not state_path.exists():
        return d
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        for k in d:
            if k not in data:
                data[k] = d[k]
        return data
    except Exception:
        return d


def save_state(state_path: Path, state: Dict[str, Any]) -> None:
    """Persist state to disk."""
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def prune_state_for_existing_keys(state: Dict[str, Any], existing_keys: set) -> None:
    """Remove stale keys from state when apps are removed from disk."""
    state["favorites"] = [k for k in state.get("favorites", []) if k in existing_keys]
    state["hidden"] = [k for k in state.get("hidden", []) if k in existing_keys]
    state["order"] = [k for k in state.get("order", []) if k in existing_keys]
    state["title_overrides"] = {k: v for k, v in state.get("title_overrides", {}).items() if k in existing_keys}
    state["icon_overrides"] = {k: v for k, v in state.get("icon_overrides", {}).items() if k in existing_keys}


def add_new_keys_to_order(state: Dict[str, Any], discovered_keys: list) -> None:
    """Append newly discovered apps to main order if they aren't already tracked."""
    known = set(state.get("favorites", [])) | set(state.get("hidden", [])) | set(state.get("order", []))
    for k in discovered_keys:
        if k not in known:
            state.setdefault("order", []).append(k)
