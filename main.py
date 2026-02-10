#===============================================================================
#  APP24_SRE_Application_Cockpit  |  Central Application Launcher
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  A central launcher that dynamically discovers applications placed under the
#  ./applications folder and presents them as draggable, reorderable tiles.
#  Supports:
#    - Windows executables (.exe)
#    - Python app folders containing a top-level main.py (no deep recursion)
#    - Favorites and Hidden sections (collapsible)
#    - Optional "Load from Git" to sync public GitHub repos listed in
#      ./applications/git-repos when their main branch contains a root main.py
#    - Per-tile icon overrides + persistent UI state (launcher_state.json)
#
#  Folder Conventions
#  ------------------
#    ./applications/
#      - *.exe                            -> shown as launchable tile
#      - <PythonAppFolder>/main.py         -> shown as launchable tile
#      - git-repos                         -> optional list of public GitHub URLs
#
#  Copyright & License Notes
#  -------------------------
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#
#  This source code is provided "AS IS", without warranty of any kind, express
#  or implied, including but not limited to the warranties of merchantability,
#  fitness for a particular purpose, and noninfringement.
#
#  Permission Notice (Personal/Internal Use)
#  -----------------------------------------
#  You may use, copy, and modify this software for personal or internal use.
#  Redistribution or public release should include this header and credit the
#  author. If you plan to open-source this project, consider replacing this
#  section with an OSI-approved license (e.g., MIT) for clarity.
#
#  Third-Party Components
#  ----------------------
#  This project may use third-party libraries (e.g., PySide6, requests) which
#  are licensed separately by their respective authors. Ensure compliance with
#  their license terms when distributing this software.
#===============================================================================


import json
import os
import sys
import subprocess
import re
import shutil
import tempfile
import zipfile
import requests
from PySide6.QtCore import QUrl

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from typing import Tuple
from PySide6.QtWidgets import QStyle

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QProgressDialog,
    QStyle,
)

APP_TITLE = "App Launcher"
APP_FOLDER_NAME = "applications"
STATE_FILE_NAME = "launcher_state.json"

TILE_SIZE = QSize(110, 110)     # square tile footprint
ICON_SIZE = QSize(48, 48)


@dataclass(frozen=True)
class AppEntry:
    key: str            # stable key for state (path-based)
    display_name: str   # default title (can be overridden by state)
    kind: str           # "exe" | "py"
    path: str           # exe path OR folder path
    launch_target: str  # exe path OR main.py path


def safe_key(p: Path) -> str:
    # Use normalized absolute path as stable key
    try:
        return str(p.resolve()).lower()
    except Exception:
        return str(p.absolute()).lower()


def find_python_main(folder: Path) -> Optional[Path]:
    """
    Per your rule: only check the first level of the folder.
    Prefer main.py, otherwise the first file that starts with 'main' and ends with .py.
    """
    if not folder.is_dir():
        return None

    main_py = folder / "main.py"
    if main_py.exists() and main_py.is_file():
        return main_py

    # Fallback: main*.py at the top level (still no recursion)
    candidates = sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".py" and p.name.lower().startswith("main")])
    return candidates[0] if candidates else None


def scan_applications_folder(apps_dir: Path) -> list[AppEntry]:
    apps: list[AppEntry] = []
    if not apps_dir.exists():
        apps_dir.mkdir(parents=True, exist_ok=True)

    for item in sorted(apps_dir.iterdir(), key=lambda p: p.name.lower()):
        # EXE
        if item.is_file() and item.suffix.lower() == ".exe":
            key = safe_key(item)
            apps.append(
                AppEntry(
                    key=key,
                    display_name=item.stem,
                    kind="exe",
                    path=str(item),
                    launch_target=str(item),
                )
            )
            continue

        # Python folder app
        if item.is_dir():
            main_file = find_python_main(item)
            if main_file:
                key = safe_key(item)
                apps.append(
                    AppEntry(
                        key=key,
                        display_name=item.name,
                        kind="py",
                        path=str(item),
                        launch_target=str(main_file),
                    )
                )

    return apps


class TileList(QListWidget):
    """
    A grid-ish tile view with built-in internal drag/drop reorder.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.IconMode)
        self.setMovement(QListWidget.Snap)
        self.setResizeMode(QListWidget.Adjust)
        self.setUniformItemSizes(True)
        self.setIconSize(ICON_SIZE)
        self.setGridSize(TILE_SIZE)
        self.setSpacing(10)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setSelectionMode(QListWidget.SingleSelection)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)

        self.base_dir = Path(__file__).parent
        self.apps_dir = self.base_dir / APP_FOLDER_NAME
        self.state_path = self.base_dir / STATE_FILE_NAME

        self.state = self.load_state()

        # UI
        root = QWidget()
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(f"<b>{APP_TITLE}</b> — drop EXEs or Python app folders into <code>./{APP_FOLDER_NAME}</code>")
        header.addWidget(title)

        header.addStretch(1)

        self.btn_open_folder = QPushButton("Open applications folder")
        self.btn_open_folder.clicked.connect(self.open_apps_folder)
        header.addWidget(self.btn_open_folder)

        self.btn_load_git = QPushButton("Load from Git")
        self.btn_load_git.clicked.connect(self.load_from_git)
        header.addWidget(self.btn_load_git)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        layout.addLayout(header)

        # Favorites
        fav_header = QHBoxLayout()
        fav_header.addWidget(QLabel("<b>Favorites</b>"))
        fav_header.addStretch(1)
        layout.addLayout(fav_header)

        self.fav_list = TileList()
        self.fav_list.itemDoubleClicked.connect(self.launch_item)
        self.fav_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fav_list.customContextMenuRequested.connect(lambda pos: self.open_context_menu(self.fav_list, pos))

        # Main
        main_header = QHBoxLayout()
        main_header.addWidget(QLabel("<b>Apps</b>"))
        main_header.addStretch(1)
        layout.addLayout(main_header)

        self.main_list = TileList()
        self.main_list.itemDoubleClicked.connect(self.launch_item)
        self.main_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.main_list.customContextMenuRequested.connect(lambda pos: self.open_context_menu(self.main_list, pos))

        # Hidden collapsible section
        hidden_header = QHBoxLayout()
        self.hidden_toggle = QToolButton()
        self.hidden_toggle.setText("Hidden")
        self.hidden_toggle.setCheckable(True)
        self.hidden_toggle.setChecked(False)
        self.hidden_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.hidden_toggle.setArrowType(Qt.RightArrow)
        self.hidden_toggle.toggled.connect(self.toggle_hidden)
        hidden_header.addWidget(self.hidden_toggle)
        hidden_header.addStretch(1)
        layout.addLayout(hidden_header)

        self.hidden_list = TileList()
        self.hidden_list.itemDoubleClicked.connect(self.launch_item)
        self.hidden_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.hidden_list.customContextMenuRequested.connect(lambda pos: self.open_context_menu(self.hidden_list, pos))
        self.hidden_list.setVisible(False)

        # Splitter for nicer resizing behavior
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.fav_list)
        splitter.addWidget(self.main_list)
        splitter.addWidget(self.hidden_list)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        layout.addWidget(splitter)

        # Save state after drag/drop reorder (cheap + effective)
        self.fav_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())
        self.main_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())
        self.hidden_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())

        # Auto-refresh polling (simple & reliable). If you want QFileSystemWatcher later, easy swap.
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1500)
        self.refresh_timer.timeout.connect(self.refresh_silent)
        self.refresh_timer.start()

        self.refresh()

    def _git_repos_file_path(self) -> Path:
        return self.apps_dir / "git-repos"  # exactly as you requested

    def _parse_github_repo_url(self, url: str) -> Optional[Tuple[str, str]]:
        """
        Accepts:
          https://github.com/owner/repo
          https://github.com/owner/repo/
          https://github.com/owner/repo.git
        Returns (owner, repo) or None.
        """
        url = url.strip()
        if not url or url.startswith("#"):
            return None

        m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$", url)
        if not m:
            return None
        owner, repo = m.group(1), m.group(2)
        return owner, repo

    def _github_has_main_py_on_main(self, owner: str, repo: str) -> bool:
        """
        Checks if main.py exists at repo root on the 'main' branch.
        Uses GitHub contents API.
        """
        api = f"https://api.github.com/repos/{owner}/{repo}/contents/main.py?ref=main"
        r = requests.get(api, timeout=20, headers={"Accept": "application/vnd.github+json"})
        if r.status_code == 200:
            return True
        if r.status_code in (404, 403):
            return False
        # For other weird statuses, treat as failure
        return False

    def _github_repo_is_public(self, owner: str, repo: str) -> bool:
        """
        Verifies repo exists and is public.
        """
        api = f"https://api.github.com/repos/{owner}/{repo}"
        r = requests.get(api, timeout=20, headers={"Accept": "application/vnd.github+json"})
        if r.status_code != 200:
            return False
        data = r.json()
        return bool(data) and (data.get("private") is False)

    def _download_and_extract_main_branch(self, owner: str, repo: str, dest_folder: Path):
        """
        Downloads main branch zip and extracts into dest_folder (replacing it).
        Uses the public GitHub zip URL (no auth required).
        """
        zip_url = f"https://github.com/{owner}/{repo}/archive/refs/heads/main.zip"

        with tempfile.TemporaryDirectory() as td:
            td_path = Path(td)
            zip_path = td_path / "repo.zip"

            # Download zip
            with requests.get(zip_url, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(zip_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if chunk:
                            f.write(chunk)

            # Extract
            extract_root = td_path / "extract"
            extract_root.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as z:
                z.extractall(extract_root)

            # GitHub zips contain a single top-level folder like repo-main-<hash>/
            top_dirs = [p for p in extract_root.iterdir() if p.is_dir()]
            if not top_dirs:
                raise RuntimeError("Zip extracted but no folder found.")
            extracted_repo_root = top_dirs[0]

            # Replace target
            if dest_folder.exists():
                shutil.rmtree(dest_folder)

            dest_folder.mkdir(parents=True, exist_ok=True)

            # Copy extracted content into dest_folder
            for child in extracted_repo_root.iterdir():
                target = dest_folder / child.name
                if child.is_dir():
                    shutil.copytree(child, target)
                else:
                    shutil.copy2(child, target)

    # ----------------------------
    # State
    # ----------------------------
    def load_state(self) -> dict:
        default = {
            "title_overrides": {},  # key -> title
            "favorites": [],        # list of keys (order)
            "hidden": [],           # list of keys (order)
            "order": [],            # main list order of keys
            "icon_overrides": {},  # key -> absolute path to png/ico/jpg
        }
        if not self.state_path.exists():
            return default
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            for k in default:
                if k not in data:
                    data[k] = default[k]
            return data
        except Exception:
            return default

    def save_state(self):
        try:
            self.state_path.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "Save failed", str(e))

    # ----------------------------
    # UI population
    # ----------------------------
    def refresh_silent(self):
        # Only repopulate if the scanned set of keys changed.
        apps = scan_applications_folder(self.apps_dir)
        scanned_keys = sorted([a.key for a in apps])
        last_keys = sorted(self.state.get("_last_scan_keys", []))
        if scanned_keys != last_keys:
            self.refresh()

    def refresh(self):
        apps = scan_applications_folder(self.apps_dir)
        self.apps_by_key = {a.key: a for a in apps}
        self.state["_last_scan_keys"] = sorted(list(self.apps_by_key.keys()))

        # Prune state entries for deleted apps
        existing = set(self.apps_by_key.keys())
        self.state["favorites"] = [k for k in self.state["favorites"] if k in existing]
        self.state["hidden"] = [k for k in self.state["hidden"] if k in existing]
        self.state["order"] = [k for k in self.state["order"] if k in existing]
        self.state["title_overrides"] = {k: v for k, v in self.state["title_overrides"].items() if k in existing}
        self.state["icon_overrides"] = {k: v for k, v in self.state["icon_overrides"].items() if k in existing}

        # Add new apps to main order at the end
        known = set(self.state["favorites"]) | set(self.state["hidden"]) | set(self.state["order"])
        for k in self.apps_by_key.keys():
            if k not in known:
                self.state["order"].append(k)

        self.rebuild_lists()
        self.save_state()

    def rebuild_lists(self):
        self.fav_list.clear()
        self.main_list.clear()
        self.hidden_list.clear()

        def add_item(list_widget: QListWidget, key: str):
            app = self.apps_by_key.get(key)
            if not app:
                return
            title = self.state["title_overrides"].get(key, app.display_name)

            item = QListWidgetItem(title)
            item.setData(Qt.UserRole, key)

            # Simple icon logic; you can improve later (extract exe icon, read app icon.png, etc.)
            # Custom icon override (if any)
            custom_icon_path = self.state.get("icon_overrides", {}).get(key)
            if custom_icon_path and Path(custom_icon_path).exists():
                item.setIcon(QIcon(custom_icon_path))
            else:
                if app.kind == "exe":
                    item.setIcon(self.style().standardIcon(QStyle.SP_DesktopIcon))
                else:
                    item.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))

            # Make tiles nicer
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            item.setSizeHint(TILE_SIZE)
            list_widget.addItem(item)

        for k in self.state["favorites"]:
            add_item(self.fav_list, k)

        for k in self.state["order"]:
            if k not in self.state["hidden"] and k not in self.state["favorites"]:
                add_item(self.main_list, k)

        for k in self.state["hidden"]:
            add_item(self.hidden_list, k)

    def load_from_git(self):
        repos_file = self._git_repos_file_path()

        if not repos_file.exists():
            repos_file.write_text(
                "# Put one public GitHub repo per line\n"
                "# Example:\n"
                "https://github.com/eabdiel/ProgreTomato\n",
                encoding="utf-8"
            )
            QMessageBox.information(
                self,
                "git-repos created",
                f"I created:\n{repos_file}\n\nAdd repo URLs (one per line), then click 'Load from Git' again."
            )
            return

        lines = repos_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        urls = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]

        if not urls:
            QMessageBox.information(self, "No repos", "Your git-repos file has no repo URLs yet.")
            return

        # Progress dialog
        prog = QProgressDialog("Loading repositories from GitHub...", "Cancel", 0, len(urls), self)
        prog.setWindowTitle("Load from Git")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)  # show immediately
        prog.setValue(0)

        ok_downloaded = []
        skipped = []
        failed = []

        self.statusBar().showMessage("Loading repositories from GitHub...")

        for i, url in enumerate(urls, start=1):
            if prog.wasCanceled():
                skipped.append(("(Canceled)", "User canceled operation"))
                break

            prog.setLabelText(f"Processing {i}/{len(urls)}:\n{url}")
            prog.setValue(i - 1)
            QApplication.processEvents()

            parsed = self._parse_github_repo_url(url)
            if not parsed:
                skipped.append((url, "Not a valid GitHub repo URL"))
                continue

            owner, repo = parsed
            dest = self.apps_dir / repo  # folder named like repo

            try:
                if not self._github_repo_is_public(owner, repo):
                    skipped.append((url, "Repo not found or not public"))
                    continue

                if not self._github_has_main_py_on_main(owner, repo):
                    skipped.append((url, "No root main.py on branch 'main'"))
                    continue

                self._download_and_extract_main_branch(owner, repo, dest)
                ok_downloaded.append(f"{owner}/{repo}")

            except requests.exceptions.HTTPError as e:
                failed.append((url, f"HTTP error: {e}"))
            except requests.exceptions.RequestException as e:
                failed.append((url, f"Network error: {e}"))
            except Exception as e:
                failed.append((url, f"Error: {e}"))

        prog.setValue(len(urls))
        prog.close()

        self.refresh()

        msg = []
        if ok_downloaded:
            msg.append("Downloaded/Updated:\n- " + "\n- ".join(ok_downloaded))
        if skipped:
            msg.append("\nSkipped:\n- " + "\n- ".join([f"{u} ({why})" for u, why in skipped]))
        if failed:
            msg.append("\nFailed:\n- " + "\n- ".join([f"{u} ({why})" for u, why in failed]))

        final_msg = "\n".join(msg).strip() if msg else "Nothing to do."
        QMessageBox.information(self, "Load from Git — results", final_msg)
        self.statusBar().showMessage("Ready", 3000)

    # ----------------------------
    # Launching
    # ----------------------------
    def launch_item(self, item: QListWidgetItem):
        key = item.data(Qt.UserRole)
        app = self.apps_by_key.get(key)
        if not app:
            return

        try:
            if app.kind == "exe":
                subprocess.Popen([app.launch_target], cwd=str(Path(app.launch_target).parent))
            else:
                folder = Path(app.path)
                main_py = Path(app.launch_target)
                subprocess.Popen([sys.executable, str(main_py)], cwd=str(folder))
        except Exception as e:
            QMessageBox.critical(self, "Launch failed", str(e))

    # ----------------------------
    # Context menu actions
    # ----------------------------
    def open_context_menu(self, which_list: TileList, pos):
        item = which_list.itemAt(pos)
        if not item:
            return
        key = item.data(Qt.UserRole)

        menu = QMenu(self)

        is_fav = key in self.state["favorites"]
        is_hidden = key in self.state["hidden"]

        act_fav = QAction("Unfavorite" if is_fav else "Favorite", self)
        act_hide = QAction("Unhide" if is_hidden else "Hide", self)
        act_rename = QAction("Rename tile…", self)
        act_open = QAction("Open location…", self)
        act_icon = QAction("Change icon…", self)
        act_reset_icon = QAction("Reset icon", self)

        menu.addAction(act_reset_icon)
        menu.addAction(act_fav)
        menu.addAction(act_hide)
        menu.addSeparator()
        menu.addAction(act_rename)
        menu.addAction(act_icon)
        menu.addAction(act_open)

        chosen = menu.exec(which_list.mapToGlobal(pos))
        if not chosen:
            return

        if chosen == act_fav:
            if is_fav:
                self.state["favorites"] = [k for k in self.state["favorites"] if k != key]
            else:
                # Add to top of favorites
                self.state["favorites"].insert(0, key)
                # Ensure it’s not hidden
                self.state["hidden"] = [k for k in self.state["hidden"] if k != key]

        elif chosen == act_hide:
            if is_hidden:
                self.state["hidden"] = [k for k in self.state["hidden"] if k != key]
            else:
                # Move to hidden section (top)
                self.state["hidden"].insert(0, key)
                # If it was favorite, remove
                self.state["favorites"] = [k for k in self.state["favorites"] if k != key]

        elif chosen == act_rename:
            current = self.state["title_overrides"].get(key, item.text())
            text, ok = QInputDialog.getText(self, "Rename tile", "Title:", text=current)
            if ok:
                cleaned = text.strip()
                if cleaned:
                    self.state["title_overrides"][key] = cleaned
                else:
                    self.state["title_overrides"].pop(key, None)

        elif chosen == act_icon:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Choose icon image",
                str(self.base_dir),
                "Images (*.png *.ico *.jpg *.jpeg *.bmp *.webp)"
            )
            if file_path:
                self.state.setdefault("icon_overrides", {})[key] = file_path
            else:
                # If user cancels, do nothing
                pass

        elif chosen == act_reset_icon:
            self.state.get("icon_overrides", {}).pop(key, None)

        elif chosen == act_open:
            app = self.apps_by_key.get(key)
            if app:
                target = Path(app.path)
                # open folder for exe; open the folder itself for py apps
                folder = target.parent if target.is_file() else target
                self.open_in_explorer(folder)

        self.rebuild_lists()
        self.save_state()

    # ----------------------------
    # Order persistence
    # ----------------------------
    def persist_order_from_ui(self):
        # Favorites list order
        self.state["favorites"] = [self.fav_list.item(i).data(Qt.UserRole) for i in range(self.fav_list.count())]

        # Hidden list order
        self.state["hidden"] = [self.hidden_list.item(i).data(Qt.UserRole) for i in range(self.hidden_list.count())]

        # Main list order: rebuild from UI-visible main items plus any non-visible ones
        visible_main = [self.main_list.item(i).data(Qt.UserRole) for i in range(self.main_list.count())]

        # Keep items that are neither hidden nor favorite but not currently visible (rare)
        existing = set(self.apps_by_key.keys())
        excluded = set(self.state["favorites"]) | set(self.state["hidden"])
        leftovers = [k for k in self.state["order"] if k in existing and k not in excluded and k not in set(visible_main)]

        self.state["order"] = visible_main + leftovers
        self.save_state()

    # ----------------------------
    # Hidden toggle
    # ----------------------------
    def toggle_hidden(self, checked: bool):
        self.hidden_list.setVisible(checked)
        self.hidden_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    # ----------------------------
    # Helpers
    # ----------------------------
    def open_apps_folder(self):
        self.open_in_explorer(self.apps_dir)

    def open_in_explorer(self, folder: Path):
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(folder)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as e:
            QMessageBox.warning(self, "Open failed", str(e))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.resize(1000, 720)
    w.show()
    sys.exit(app.exec())
