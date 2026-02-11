#===============================================================================
#  SRE_Applications_Cockpit | import_scanner.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Summary
#  -------
#  Best-effort scanning of Python source trees to detect imported third‑party modules.
#  Used by the cockpit to keep its shared runtime environment up to date automatically.
#
#  Notes
#  -----
#  - We must run on Python 3.9+ (your bundled runtime is 3.9 in current builds),
#    so we cannot rely on sys.stdlib_module_names (3.10+).
#  - Instead, we detect stdlib by looking up import specs and checking if the
#    resolved origin lives under the interpreter's stdlib folder.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import ast
import importlib.util
import os
import sys
import sysconfig
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

# Hard skip list (things that are stdlib or cockpit-internal but can appear as imports)
ALWAYS_SKIP = {
    "__future__",
    "typing",
    "pathlib",
    "platform",
    "asyncio",
}


def _stdlib_root() -> str:
    """Return stdlib root path for the current interpreter (best effort)."""
    try:
        p = sysconfig.get_paths().get("stdlib") or ""
        return os.path.normcase(os.path.abspath(p))
    except Exception:
        return ""


def is_stdlib_module(name: str) -> bool:
    """True if `name` appears to be part of the standard library for this interpreter."""
    if not name:
        return True
    top = name.split(".")[0]
    if top in ALWAYS_SKIP:
        return True
    if top in sys.builtin_module_names:
        return True

    stdlib_root = _stdlib_root()
    try:
        spec = importlib.util.find_spec(top)
    except Exception:
        spec = None

    if not spec:
        return False

    origin = getattr(spec, "origin", None) or ""
    if origin in ("built-in", "frozen"):
        return True

    if not stdlib_root or not origin:
        return False

    origin_norm = os.path.normcase(os.path.abspath(origin))
    # site-packages check: if it lives under site-packages, it is *not* stdlib
    if "site-packages" in origin_norm or "dist-packages" in origin_norm:
        return False
    # stdlib check
    return origin_norm.startswith(stdlib_root)


def _iter_py_files(root: Path):
    for py in Path(root).rglob("*.py"):
        if "__pycache__" in py.parts:
            continue
        if any(part.startswith(".") for part in py.parts):
            continue
        yield py


def _scan_imports_in_file(py: Path) -> Set[str]:
    found: Set[str] = set()
    try:
        src = py.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src, filename=str(py))
    except Exception:
        return found

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = (alias.name or "").split(".")[0]
                if top and not is_stdlib_module(top):
                    found.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top and not is_stdlib_module(top):
                    found.add(top)

    return found


def discover_imports(app_dir: Path) -> Set[str]:
    """Scan an app folder recursively to discover imported *top-level* module names."""
    app_dir = Path(app_dir)
    found: Set[str] = set()

    for py in _iter_py_files(app_dir):
        found |= _scan_imports_in_file(py)

    # Remove obvious local modules (files/folders in the app root)
    local = {p.stem for p in app_dir.glob("*.py")}
    local |= {p.name for p in app_dir.iterdir() if p.is_dir() and not p.name.startswith(".")}

    return {m for m in found if m not in local and m not in ALWAYS_SKIP}


def discover_imports_in_tree(root: Path) -> Set[str]:
    """Scan all *.py under root recursively for imported top-level module names (excluding stdlib)."""
    root = Path(root)
    found: Set[str] = set()
    for py in _iter_py_files(root):
        found |= _scan_imports_in_file(py)
    return {m for m in found if m not in ALWAYS_SKIP}


def to_pip_names(modules: Iterable[str]) -> Set[str]:
    """Map import names to pip names (best effort)."""
    out = set()
    for m in modules:
        top = (m or "").split(".")[0]
        if not top or top in ALWAYS_SKIP:
            continue
        out.add(PIP_NAME_OVERRIDES.get(top, top))
    return out
