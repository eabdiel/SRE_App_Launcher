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
#  Also provides helpers to keep cockpit-requirements.txt clean and install packages.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from .runtime_manager import resolve_python_command
from .import_scanner import is_stdlib_module


REQ_LINE_RE = re.compile(r"^([A-Za-z0-9_.-]+)")

# Packages that should never be pip-installed because they're stdlib or otherwise wrong for pip.
BAD_PIP_NAMES = {
    "platform",
    "asyncio",
    "tkinter",
    "typing",
    "pathlib",
}


def _sha256_text(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def shared_env_dir(base_dir: Path) -> Path:
    return base_dir / "runtime_env"


def shared_env_python(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _run_logged(
    log_file,
    cmd: List[str],
    cwd: Optional[Path] = None,
) -> None:
    log_file.write(f"\n$ {' '.join(cmd)}\n")
    log_file.flush()
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
    )
    rc = p.wait()
    if rc != 0:
        raise RuntimeError(f"Command failed (rc={rc}).")


def normalize_req_line(line: str) -> str:
    """Normalize a requirement line to a bare package name for comparisons."""
    line = (line or "").strip()
    if not line or line.startswith("#"):
        return ""
    # ignore options we don't want to merge automatically
    if line.startswith(("-", "--")):
        return ""
    m = REQ_LINE_RE.match(line)
    return (m.group(1) if m else "").strip()


def sanitize_requirements_file(req_path: Path) -> bool:
    """Remove obviously bad/stdlib requirement lines from cockpit-requirements.txt.

    This prevents failures like attempting to `pip install platform`.
    Returns True if file changed.
    """
    if not req_path.exists():
        return False

    original = req_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    cleaned: List[str] = []
    changed = False

    for raw in original:
        line = raw.strip()
        if not line or line.startswith("#"):
            cleaned.append(raw.rstrip())
            continue

        name = normalize_req_line(line)
        if not name:
            # drop unsupported lines
            changed = True
            continue

        if name.lower() in BAD_PIP_NAMES or is_stdlib_module(name):
            # drop stdlib and known-bad names
            changed = True
            continue

        cleaned.append(name)

    # de-dup while preserving order
    seen = set()
    deduped: List[str] = []
    for line in cleaned:
        key = line.lower().strip()
        if not key or key.startswith("#"):
            deduped.append(line)
            continue
        if key in seen:
            changed = True
            continue
        seen.add(key)
        deduped.append(line)

    if changed:
        req_path.write_text("\n".join(deduped).rstrip() + "\n", encoding="utf-8")
    return changed


def ensure_shared_env(
    base_dir: Path,
    state: dict,
    requirements_path: Path,
    log_path: Path,
) -> Tuple[Path, str]:
    """Ensure the shared venv exists and is up-to-date."""
    venv_dir = shared_env_dir(base_dir)
    venv_dir.mkdir(parents=True, exist_ok=True)

    # Make sure cockpit-requirements is sane before install.
    sanitize_requirements_file(requirements_path)
    req_hash = _sha256_text(requirements_path)

    py = shared_env_python(venv_dir)
    if py.exists() and (state.get("shared_env_hash") == req_hash):
        return py, req_hash

    python_cmd = resolve_python_command(base_dir, state)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
        # Create venv if missing
        if not py.exists():
            _run_logged(f, python_cmd + ["-m", "venv", str(venv_dir)], cwd=base_dir)

        # Upgrade pip
        _run_logged(f, [str(py), "-m", "pip", "install", "--upgrade", "pip"], cwd=base_dir)

        # Install shared requirements
        cmd = [str(py), "-m", "pip", "install", "-r", str(requirements_path)]
        pip_cache = (state or {}).get("pip_cache_dir") or ""
        if pip_cache.strip():
            cache_dir = Path(pip_cache)
            cache_dir.mkdir(parents=True, exist_ok=True)
            cmd += ["--cache-dir", str(cache_dir)]

        _run_logged(f, cmd, cwd=base_dir)

    return py, req_hash


def ensure_packages(python_exe: Path, pip_names: list[str], log_path: Path) -> list[str]:
    """Install packages into the shared env.

    - Skips bad/stdlib names.
    - Continues on errors (logs them) so one bad package doesn't block everything.
    """
    if not pip_names:
        return []

    log_path.parent.mkdir(parents=True, exist_ok=True)

    newly: list[str] = []
    with open(log_path, "a", encoding="utf-8", errors="ignore") as f:
        for pkg in pip_names:
            name = normalize_req_line(pkg)
            if not name:
                continue
            if name.lower() in BAD_PIP_NAMES or is_stdlib_module(name):
                continue

            # already installed?
            try:
                p = subprocess.run(
                    [str(python_exe), "-m", "pip", "show", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                if p.returncode == 0:
                    continue
            except Exception:
                pass

            f.write(f"\n$ {python_exe} -m pip install {name}\n")
            f.flush()
            p = subprocess.Popen(
                [str(python_exe), "-m", "pip", "install", name],
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
            )
            rc = p.wait()
            if rc == 0:
                newly.append(name)
            else:
                # non-fatal: keep going
                f.write(f"\n[WARN] Failed to install '{name}' (rc={rc}). Continuing.\n")
                f.flush()

    return newly


def update_cockpit_requirements(req_file: Path, pip_names: Iterable[str]) -> bool:
    """Append missing packages to cockpit-requirements.txt. Returns True if changed."""
    req_file.parent.mkdir(parents=True, exist_ok=True)
    existing = set()

    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            name = normalize_req_line(line)
            if name:
                existing.add(name.lower())

    to_add: List[str] = []
    for p in pip_names:
        name = normalize_req_line(str(p))
        if not name:
            continue
        if name.lower() in BAD_PIP_NAMES or is_stdlib_module(name):
            continue
        if name.lower() not in existing:
            to_add.append(name)
            existing.add(name.lower())

    if not to_add:
        return False

    with open(req_file, "a", encoding="utf-8") as f:
        for p in to_add:
            f.write(p + "\n")

    sanitize_requirements_file(req_file)
    return True


def merge_requirements_txt_into_cockpit(cockpit_req: Path, app_requirements: Path) -> bool:
    """Merge an application's requirements.txt into cockpit-requirements.txt (best effort)."""
    if not app_requirements.exists():
        return False

    lines = app_requirements.read_text(encoding="utf-8", errors="ignore").splitlines()
    pkgs: List[str] = []
    for ln in lines:
        name = normalize_req_line(ln)
        if name:
            pkgs.append(name)

    if not pkgs:
        return False

    changed = update_cockpit_requirements(cockpit_req, pkgs)
    return changed
