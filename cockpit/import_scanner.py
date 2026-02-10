#===============================================================================
#  APP24_SRE_Application_Cockpit | import_scanner.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  Scans a Python app folder to detect imported modules (best-effort) for auto-install into shared env.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Iterable, Set


# Common cases where import name != pip package name
PIP_NAME_OVERRIDES = {
    "PIL": "Pillow",
    "yaml": "PyYAML",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "Crypto": "pycryptodome",
}


def _stdlib_modules() -> Set[str]:
    """Return a set of stdlib module names for the current interpreter (best effort)."""
    try:
        return set(sys.stdlib_module_names)  # py3.10+
    except Exception:
        # Fallback minimal set; still ok because we also validate via shared env import checks.
        return {
            "os", "sys", "re", "json", "time", "datetime", "pathlib", "typing", "subprocess",
            "threading", "multiprocessing", "itertools", "functools", "math", "random", "logging",
            "collections", "dataclasses", "shutil", "glob", "tempfile", "hashlib", "base64",
        }


def discover_imports(app_dir: Path) -> Set[str]:
    """Scan .py files recursively to discover imported *top-level* module names.

    - Recurses into subfolders (dependency imports can live anywhere).
    - Ignores __pycache__ and hidden folders.
    - Returns module names like: 'requests', 'pynput', 'openpyxl'
    """
    app_dir = Path(app_dir)
    stdlib = _stdlib_modules()
    found: Set[str] = set()

    for py in app_dir.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        if any(part.startswith(".") for part in py.parts):
            continue
        try:
            src = py.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src, filename=str(py))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = (alias.name or "").split(".")[0]
                    if top and top not in stdlib:
                        found.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top and top not in stdlib:
                        found.add(top)

    # Remove obvious local modules (files/folders in the app root)
    local = {p.stem for p in app_dir.glob("*.py")}
    local |= {p.name for p in app_dir.iterdir() if p.is_dir() and not p.name.startswith(".")}

    return {m for m in found if m not in local}


def to_pip_names(modules: Iterable[str]) -> Set[str]:
    out = set()
    for m in modules:
        out.add(PIP_NAME_OVERRIDES.get(m, m))
    return out


def discover_imports_in_tree(root: Path) -> Set[str]:
    """Scan all *.py under root (recursively) for imported top-level module names, excluding stdlib."""
    root = Path(root)
    stdlib = _stdlib_modules()
    found: Set[str] = set()

    for py in root.rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        if any(part.startswith(".") for part in py.parts):
            continue
        try:
            src = py.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src, filename=str(py))
        except Exception:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = (alias.name or "").split(".")[0]
                    if top and top not in stdlib:
                        found.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    if top and top not in stdlib:
                        found.add(top)

    return found
