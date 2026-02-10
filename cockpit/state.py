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
#  Load/save and maintenance of persistent cockpit state (layout, icons, runtime, tile sizes, status).
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
        "title_overrides": {},
        "favorites": [],
        "hidden": [],
        "order": [],
        "icon_overrides": {},
        "tile_sizes": {},   # key -> "small" | "wide"
        "app_status": {},   # key -> message

        "python_runtime_path": "",
        "pip_cache_dir": "",
        "shared_env_hash": "",
    }


def load_state(state_path: Path) -> Dict[str, Any]:
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
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def prune_state_for_existing_keys(state: Dict[str, Any], existing_keys: set) -> None:
    state["favorites"] = [k for k in state.get("favorites", []) if k in existing_keys]
    state["hidden"] = [k for k in state.get("hidden", []) if k in existing_keys]
    state["order"] = [k for k in state.get("order", []) if k in existing_keys]
    state["title_overrides"] = {k: v for k, v in state.get("title_overrides", {}).items() if k in existing_keys}
    state["icon_overrides"] = {k: v for k, v in state.get("icon_overrides", {}).items() if k in existing_keys}
    state["tile_sizes"] = {k: v for k, v in state.get("tile_sizes", {}).items() if k in existing_keys}
    state["app_status"] = {k: v for k, v in state.get("app_status", {}).items() if k in existing_keys}


def add_new_keys_to_order(state: Dict[str, Any], discovered_keys: list) -> None:
    known = set(state.get("favorites", [])) | set(state.get("hidden", [])) | set(state.get("order", []))
    for k in discovered_keys:
        if k not in known:
            state.setdefault("order", []).append(k)
