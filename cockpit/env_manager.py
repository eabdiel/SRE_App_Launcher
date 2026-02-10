#===============================================================================
#  APP24_SRE_Application_Cockpit | env_manager.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  Creates and manages per-application virtual environments and dependency installation.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Optional


def venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_dirs(app_dir: Path) -> Path:
    logs_dir = app_dir / ".cockpit" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def run_logged(cmd: List[str], cwd: Path, log_file: Path, env: Optional[dict] = None) -> None:
    """Run a subprocess and append stdout/stderr to a log file."""
    with open(log_file, "a", encoding="utf-8", errors="ignore") as f:
        f.write(f"\n$ {' '.join(cmd)}\n")
        f.flush()
        p = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdout=f,
            stderr=subprocess.STDOUT,
            env=env,
            text=True,
        )
        rc = p.wait()
        if rc != 0:
            raise RuntimeError(f"Command failed (rc={rc}). See log: {log_file}")


def ensure_venv(app_dir: Path, python_cmd: List[str], pip_cache_dir: Optional[Path] = None) -> Path:
    """Ensure a per-app venv exists at <app_dir>/.venv and return venv python path."""
    venv_dir = app_dir / ".venv"
    logs_dir = ensure_dirs(app_dir)
    log_file = logs_dir / "setup_env.log"

    # Create venv if needed
    if not venv_dir.exists():
        run_logged(python_cmd + ["-m", "venv", str(venv_dir)], cwd=app_dir, log_file=log_file)

    py = venv_python_path(venv_dir)
    if not py.exists():
        raise RuntimeError(f"Virtualenv created but python not found at {py}. See log: {log_file}")

    # Upgrade pip (helps avoid weird old pip behavior)
    run_logged([str(py), "-m", "pip", "install", "--upgrade", "pip"], cwd=app_dir, log_file=log_file)

    # Install requirements if present
    req = app_dir / "requirements.txt"
    if req.exists():
        cmd = [str(py), "-m", "pip", "install", "-r", str(req)]
        if pip_cache_dir and str(pip_cache_dir).strip():
            pip_cache_dir.mkdir(parents=True, exist_ok=True)
            cmd += ["--cache-dir", str(pip_cache_dir)]
        run_logged(cmd, cwd=app_dir, log_file=log_file)

    return py
