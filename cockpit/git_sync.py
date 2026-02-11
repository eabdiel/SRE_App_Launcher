#===============================================================================
#  SRE_Applications_Cockpit | git_sync.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Summary
#  -------
#  GitHub public-repo sync logic used by the 'Load from Git' feature.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

import requests

# NOTE:
# - We intentionally keep this module focused on GitHub I/O.
# - UI concerns (progress dialogs, message boxes) live in the window/controller layer.


def parse_github_repo_url(url: str) -> Optional[Tuple[str, str]]:
    """Parse GitHub repo URLs and return (owner, repo) or None."""
    url = url.strip()
    if not url or url.startswith("#"):
        return None
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    return owner, repo


def github_repo_is_public(owner: str, repo: str) -> bool:
    api = f"https://api.github.com/repos/{owner}/{repo}"
    r = requests.get(api, timeout=20, headers={"Accept": "application/vnd.github+json"})
    if r.status_code != 200:
        return False
    data = r.json()
    return bool(data) and (data.get("private") is False)


def github_has_root_main_py_on_main(owner: str, repo: str) -> bool:
    api = f"https://api.github.com/repos/{owner}/{repo}/contents/main.py?ref=main"
    r = requests.get(api, timeout=20, headers={"Accept": "application/vnd.github+json"})
    return r.status_code == 200

def github_has_root_requirements_on_main(owner: str, repo: str) -> bool:
    """Checks if requirements.txt exists at repo root on the 'main' branch."""
    api = f"https://api.github.com/repos/{owner}/{repo}/contents/requirements.txt?ref=main"
    r = requests.get(api, timeout=20, headers={"Accept": "application/vnd.github+json"})
    return r.status_code == 200


def download_and_extract_main_branch(owner: str, repo: str, dest_folder: Path) -> None:
    """Download main branch zip and extract into dest_folder (replacing it)."""
    zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        zip_path = td_path / "repo.zip"

        with requests.get(zip_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)

        extract_root = td_path / "extract"
        extract_root.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_root)

        top_dirs = [p for p in extract_root.iterdir() if p.is_dir()]
        if not top_dirs:
            raise RuntimeError("Zip extracted but no folder found.")
        extracted_repo_root = top_dirs[0]

        if dest_folder.exists():
            shutil.rmtree(dest_folder)

        dest_folder.mkdir(parents=True, exist_ok=True)

        for child in extracted_repo_root.iterdir():
            target = dest_folder / child.name
            if child.is_dir():
                shutil.copytree(child, target)
            else:
                shutil.copy2(child, target)


def read_git_repos_file(repos_file: Path) -> List[str]:
    lines = repos_file.read_text(encoding="utf-8", errors="ignore").splitlines()
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]
