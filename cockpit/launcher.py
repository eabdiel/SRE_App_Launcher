#===============================================================================
#  SRE_Applications_Cockpit | launcher.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Summary
#  -------
#  Launches EXE/LNK/URL and Python apps. Python apps run under shared env; missing deps are detected and installed automatically.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import os
import subprocess
import webbrowser
from pathlib import Path

from .deps_manager import ensure_shared_env, ensure_packages, update_cockpit_requirements
from .import_scanner import discover_imports, to_pip_names
from .models import AppEntry


def _startfile(path: str) -> None:
    # Windows shortcut (.lnk) support uses os.startfile
    if hasattr(os, "startfile"):
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen([path])


def launch_app(entry: AppEntry, base_dir: Path, state: dict) -> None:
    """Launch an app entry.

    kinds:
      - exe: run directly
      - lnk: open via OS (Windows shortcut)
      - url: open in browser
      - py : run main.py using shared env; auto-install missing deps
      - git: placeholder; should be handled by UI (download/install)
    """
    if entry.kind == "url":
        webbrowser.open(entry.launch_target)
        return

    if entry.kind == "urlfile":
        # Windows Internet Shortcut (.url)
        try:
            # Let OS handle it
            if sys.platform.startswith("win"):
                subprocess.Popen(["cmd", "/c", "start", "", entry.launch_target], shell=False)
            else:
                webbrowser.open(Path(entry.launch_target).as_uri())
        except Exception:
            webbrowser.open(Path(entry.launch_target).as_uri())
        return

    if entry.kind == "lnk":
        _startfile(entry.launch_target)
        return

    if entry.kind == "exe":
        subprocess.Popen([entry.launch_target], cwd=str(Path(entry.launch_target).parent))
        return

    if entry.kind == "git":
        raise RuntimeError("Git placeholder tile. Download/install first.")

    # Python app
    app_dir = Path(entry.path)
    main_py = Path(entry.launch_target)

    requirements_path = base_dir / "cockpit-requirements.txt"
    logs_dir = base_dir / ".cockpit" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_setup = logs_dir / "shared_env_setup.log"
    log_deps = logs_dir / "shared_env_deps.log"

    py, req_hash = ensure_shared_env(base_dir, state or {}, requirements_path, log_setup)
    state["shared_env_hash"] = req_hash

    modules = discover_imports(app_dir)
    pip_names = sorted(to_pip_names(modules))

    # Keep cockpit-requirements.txt in sync for packaging / offline installs.
    changed = update_cockpit_requirements(requirements_path, pip_names)
    if changed:
        state.setdefault("app_status", {})[entry.key] = "Dependencies updated in cockpit-requirements.txt"

    newly = ensure_packages(py, pip_names, log_deps)
    if newly:
        state.setdefault("app_status", {})[entry.key] = f"Installed: {', '.join(newly[:6])}" + ("…" if len(newly) > 6 else "")

    subprocess.Popen([str(py), str(main_py)], cwd=str(app_dir))
