#===============================================================================
#  APP24_SRE_Application_Cockpit | deps_manager.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  Creates/updates a single shared Python environment used to run all Python apps.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from .runtime_manager import resolve_python_command


def _sha256_text(path: Path) -> str:
    h = hashlib.sha256()
    data = path.read_bytes()
    h.update(data)
    return h.hexdigest()


def shared_env_dir(base_dir: Path) -> Path:
    """Where the shared venv lives."""
    return base_dir / "runtime_env"


def shared_env_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def ensure_shared_env(
    base_dir: Path,
    state: dict,
    requirements_path: Path,
    log_path: Path,
) -> Tuple[Path, str]:
    """Ensure the shared venv exists and is up-to-date.

    Returns:
      (python_exe_path, requirements_hash)

    Behavior:
      - Creates venv at ./runtime_env if missing
      - Installs/updates packages from cockpit-requirements.txt
      - Uses state['shared_env_hash'] to skip work if unchanged
    """
    venv_dir = shared_env_dir(base_dir)
    venv_dir.mkdir(parents=True, exist_ok=True)

    req_hash = _sha256_text(requirements_path)

    # Skip install if unchanged and python exists
    py = shared_env_python(venv_dir)
    if py.exists() and (state.get("shared_env_hash") == req_hash):
        return py, req_hash

    python_cmd = resolve_python_command(base_dir, state)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
        def run(cmd: List[str], cwd: Optional[Path] = None):
            f.write(f"\n$ {' '.join(cmd)}\n")
            f.flush()
            p = subprocess.Popen(
                cmd,
                cwd=str(cwd or base_dir),
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
            )
            rc = p.wait()
            if rc != 0:
                raise RuntimeError(f"Command failed (rc={rc}). See log: {log_path}")

        # Create venv if missing
        if not py.exists():
            run(python_cmd + ["-m", "venv", str(venv_dir)])

        # Upgrade pip
        run([str(py), "-m", "pip", "install", "--upgrade", "pip"])

        # Install shared requirements
        cmd = [str(py), "-m", "pip", "install", "-r", str(requirements_path)]
        pip_cache = (state or {}).get("pip_cache_dir") or ""
        if pip_cache.strip():
            cache_dir = Path(pip_cache)
            cache_dir.mkdir(parents=True, exist_ok=True)
            cmd += ["--cache-dir", str(cache_dir)]

        run(cmd)

    return py, req_hash


def ensure_packages(python_exe: Path, pip_names: list[str], log_path: Path) -> list[str]:
    """Ensure the given pip packages are installed into the shared env.

    Returns:
      list of packages that were newly installed.
    """
    if not pip_names:
        return []

    log_path.parent.mkdir(parents=True, exist_ok=True)

    newly = []
    with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
        def run(cmd: list[str]):
            f.write(f"\n$ {' '.join(cmd)}\n")
            f.flush()
            p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)
            rc = p.wait()
            if rc != 0:
                raise RuntimeError(f"Command failed (rc={rc}). See log: {log_path}")

        # Determine which are missing by trying import. We validate using module import name where possible.
        for pkg in pip_names:
            # Fast path: ask pip if it's installed
            try:
                p = subprocess.run([str(python_exe), "-m", "pip", "show", pkg],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if p.returncode == 0:
                    continue
            except Exception:
                # If pip show fails for any reason, we'll just attempt install.
                pass

            run([str(python_exe), "-m", "pip", "install", pkg])
            newly.append(pkg)

    return newly

def ensure_packages(python_exe: Path, pip_names: list[str], log_path: Path) -> list[str]:
    """Ensure pip packages are installed into the shared env; return newly installed packages."""
    if not pip_names:
        return []
    log_path.parent.mkdir(parents=True, exist_ok=True)

    newly: list[str] = []
    with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
        def run(cmd: list[str]):
            f.write(f"\n$ {' '.join(cmd)}\n")
            f.flush()
            p = subprocess.Popen(cmd, stdout=f, stderr=subprocess.STDOUT, text=True)
            rc = p.wait()
            if rc != 0:
                raise RuntimeError(f"Command failed (rc={rc}). See log: {log_path}")

        for pkg in pip_names:
            try:
                p = subprocess.run([str(python_exe), "-m", "pip", "show", pkg],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if p.returncode == 0:
                    continue
            except Exception:
                pass

            run([str(python_exe), "-m", "pip", "install", pkg])
            newly.append(pkg)

    return newly


def update_cockpit_requirements(req_file: Path, pip_names: list[str]) -> bool:
    """Append missing packages to cockpit-requirements.txt.

    Returns True if file changed.
    """
    req_file.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            existing.add(line.lower())

    to_add = []
    for p in pip_names:
        if p.lower() not in existing:
            to_add.append(p)

    if not to_add:
        return False

    with open(req_file, "a", encoding="utf-8") as f:
        for p in to_add:
            f.write(p + "\n")
    return True
