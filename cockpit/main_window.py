#===============================================================================
#  APP24_SRE_Application_Cockpit | main_window.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Role/Team   : SAP COE / SAP SRE (GRM-Testing-Automation & Governance)
#  Created     : 2026-02-10
#  Last Update : 2026-02-10
#
#  Summary
#  -------
#  Main Metro/Windows-Phone style UI for the cockpit:
#    - Favorites / Hidden sections + main app list
#    - Drag/drop ordering (persisted)
#    - GitHub import via applications/git-repos (plus URL shortcuts)
#    - Shared Python runtime setup button
#    - Right-click actions: favorite, hide, rename, icon, tile size
#    - Update Libraries button (scan ./applications and install into shared runtime)
#===============================================================================

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import requests
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .banner_widget import BannerWidget
from .constants import (
    APP_TITLE,
    APP_FOLDER_NAME,
    STATE_FILE_NAME,
    GIT_REPOS_FILE_NAME,
    METRO_BG,
    METRO_TILE_COLORS,
    TILE_SMALL,
    TILE_WIDE,
)
from .deps_manager import ensure_shared_env, ensure_packages, update_cockpit_requirements
from .fs_discovery import scan_applications_folder
from .git_sync import (
    parse_github_repo_url,
    github_repo_is_public,
    github_has_root_main_py_on_main,
    download_and_extract_main_branch,
    read_git_repos_file,
)
from .import_scanner import discover_imports_in_tree, to_pip_names
from .launcher import launch_app
from .models import AppEntry
from .state import load_state, save_state, prune_state_for_existing_keys, add_new_keys_to_order
from .tile_widget import TileWidget, TileVisual
from .ui_widgets import TileList


PROGRESS_STYLE = (
    "QProgressDialog{background:#1a1a1a;color:white;}"
    " QLabel{color:white;}"
    " QPushButton{color:white;background:#222;border:1px solid #2a2a2a;padding:6px;}"
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)

        self.base_dir = Path(__file__).resolve().parent.parent
        self.apps_dir = self.base_dir / APP_FOLDER_NAME
        self.state_path = self.base_dir / STATE_FILE_NAME
        self.state = load_state(self.state_path)

        self._runtime_installing = False

        self.setStyleSheet(f"""
        QMainWindow {{ background: {METRO_BG}; }}
        QLabel {{ color: white; font-family: "Segoe UI"; }}
        QToolButton, QPushButton {{
            font-family: "Segoe UI";
            color: white;
            background: #1a1a1a;
            border: 1px solid #2a2a2a;
            padding: 6px 10px;
        }}
        QToolButton:hover, QPushButton:hover {{ background: #222; }}
        QToolButton:pressed, QPushButton:pressed {{ background: #2a2a2a; }}
        """)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(
            f"<b>{APP_TITLE}</b> — drop EXEs/LNKs or Python app folders into <code>./{APP_FOLDER_NAME}</code>"
        )
        header.addWidget(title)
        header.addStretch(1)

        self.btn_open_folder = QPushButton("Open apps folder")
        self.btn_open_folder.clicked.connect(self.open_apps_folder)
        header.addWidget(self.btn_open_folder)

        self.btn_load_git = QPushButton("Load from Git")
        self.btn_load_git.clicked.connect(self.load_from_git)
        header.addWidget(self.btn_load_git)

        self.btn_setup_runtime = QPushButton("Setup Runtime")
        self.btn_setup_runtime.clicked.connect(self.setup_runtime)
        header.addWidget(self.btn_setup_runtime)

        self.btn_update_libs = QPushButton("Update Libraries")
        self.btn_update_libs.clicked.connect(self.update_libraries)
        header.addWidget(self.btn_update_libs)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        layout.addLayout(header)

        # Scrolling banner (edit ./banner.txt to change)
        self.banner = BannerWidget(self.base_dir / "banner.txt")
        self.banner.setStyleSheet(
            "QFrame#BannerWidget{background:#1a1a1a;border:1px solid #2a2a2a;} QLabel{color:white;}"
        )
        layout.addWidget(self.banner)

        self.fav_list = TileList()
        self.fav_list.itemDoubleClicked.connect(self.launch_item)
        self.fav_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fav_list.customContextMenuRequested.connect(lambda pos: self.open_context_menu(self.fav_list, pos))

        self.main_list = TileList()
        self.main_list.itemDoubleClicked.connect(self.launch_item)
        self.main_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.main_list.customContextMenuRequested.connect(lambda pos: self.open_context_menu(self.main_list, pos))

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

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.fav_list)
        splitter.addWidget(self.main_list)
        splitter.addWidget(self.hidden_list)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        layout.addWidget(splitter)

        self.fav_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())
        self.main_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())
        self.hidden_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1500)
        self.refresh_timer.timeout.connect(self.refresh_silent)
        self.refresh_timer.start()

        self.refresh()

    # ----------------------------
    # Git file parsing + placeholders
    # ----------------------------
    def _entries_from_git_file(self) -> list[tuple[str, str, str]]:
        """Return list of (kind, display, value) from applications/git-repos.

        - GitHub repos (https://github.com/<owner>/<repo>) => kind='git', display=repo, value=url
        - Other http(s) URLs => kind='url', display=host/path, value=url
        """
        repos_file = self.apps_dir / GIT_REPOS_FILE_NAME
        if not repos_file.exists():
            return []

        urls = read_git_repos_file(repos_file)
        out: list[tuple[str, str, str]] = []
        for u in urls:
            parsed = parse_github_repo_url(u)
            if parsed:
                _owner, repo = parsed
                out.append(("git", repo, u))
            else:
                if u.lower().startswith(("http://", "https://")):
                    disp = u.replace("https://", "").replace("http://", "")
                    out.append(("url", disp, u))
        return out

    def _augment_with_git_placeholders(self, apps: list[AppEntry]) -> list[AppEntry]:
        existing_names = {Path(a.path).name for a in apps}

        for kind, display, value in self._entries_from_git_file():
            if kind == "git":
                if display in existing_names:
                    continue
                apps.append(
                    AppEntry(
                        key=f"git:{display}",
                        kind="git",
                        display_name=display,
                        path=value,
                        launch_target=value,
                    )
                )
            elif kind == "url":
                apps.append(
                    AppEntry(
                        key=f"url:{value}",
                        kind="url",
                        display_name=display,
                        path=value,
                        launch_target=value,
                    )
                )
        return apps

    def _merge_repo_requirements_if_present(self, repo_folder: Path) -> bool:
        """If repo has requirements.txt, merge it into cockpit-requirements.txt."""
        repo_req = repo_folder / "requirements.txt"
        if not repo_req.exists():
            return False

        cockpit_req = self.base_dir / "cockpit-requirements.txt"
        try:
            lines = []
            for line in repo_req.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # Ignore editable installs and local paths for now
                if line.startswith(("-e ", "--")):
                    continue
                lines.append(line)

            if not lines:
                return False

            return update_cockpit_requirements(cockpit_req, lines)
        except Exception:
            return False

    # ----------------------------
    # Refresh / rebuild
    # ----------------------------
    def refresh_silent(self):
        apps = scan_applications_folder(self.apps_dir)
        apps = self._augment_with_git_placeholders(apps)
        scanned_keys = sorted([a.key for a in apps])
        last_keys = sorted(self.state.get("_last_scan_keys", []))
        if scanned_keys != last_keys:
            self.refresh()

    def refresh(self):
        apps = scan_applications_folder(self.apps_dir)
        apps = self._augment_with_git_placeholders(apps)

        self.apps_by_key = {a.key: a for a in apps}
        self.state["_last_scan_keys"] = sorted(list(self.apps_by_key.keys()))

        existing = set(self.apps_by_key.keys())
        prune_state_for_existing_keys(self.state, existing)
        add_new_keys_to_order(self.state, list(self.apps_by_key.keys()))

        self.rebuild_lists()
        save_state(self.state_path, self.state)

    def _tile_color_for_key(self, k: str) -> str:
        h = hashlib.sha1(k.encode("utf-8")).hexdigest()
        idx = int(h[:2], 16) % len(METRO_TILE_COLORS)
        return METRO_TILE_COLORS[idx]

    def _runtime_ready(self) -> bool:
        req = self.base_dir / "cockpit-requirements.txt"
        venv_py = self.base_dir / "runtime_env" / "Scripts" / "python.exe"
        return venv_py.exists() and req.exists() and bool(self.state.get("shared_env_hash"))

    def rebuild_lists(self):
        self.fav_list.clear()
        self.main_list.clear()
        self.hidden_list.clear()

        def add_item(list_widget: QListWidget, key: str):
            app = self.apps_by_key.get(key)
            if not app:
                return

            title = self.state.get("title_overrides", {}).get(key, app.display_name)

            if app.kind == "url":
                subtitle = "Open in browser"
            elif app.kind == "git":
                subtitle = "Download and install"
            elif app.kind == "exe":
                subtitle = "Executable"
            elif app.kind == "lnk":
                subtitle = "Shortcut"
            else:
                if self._runtime_installing:
                    subtitle = "Python • Installing…"
                elif self._runtime_ready():
                    subtitle = "Python • Ready"
                else:
                    subtitle = "Python • Needs runtime"

            icon = None
            icon_path = self.state.get("icon_overrides", {}).get(key)
            if icon_path and Path(icon_path).exists():
                icon = QIcon(icon_path)

            size_mode = self.state.get("tile_sizes", {}).get(key, "small")
            tile_size = TILE_WIDE if size_mode == "wide" else TILE_SMALL

            item = QListWidgetItem()
            item.setData(Qt.UserRole, key)
            item.setSizeHint(tile_size)
            list_widget.addItem(item)

            tile = TileWidget(
                TileVisual(
                    bg_color=self._tile_color_for_key(key),
                    title=title,
                    subtitle=subtitle,
                    icon=icon,
                ),
                size=tile_size,
            )
            list_widget.setItemWidget(item, tile)

        for k in self.state.get("favorites", []):
            add_item(self.fav_list, k)

        for k in self.state.get("order", []):
            if k not in self.state.get("hidden", []) and k not in self.state.get("favorites", []):
                add_item(self.main_list, k)

        for k in self.state.get("hidden", []):
            add_item(self.hidden_list, k)

    # ----------------------------
    # Runtime setup
    # ----------------------------
    def setup_runtime(self):
        req = self.base_dir / "cockpit-requirements.txt"
        if not req.exists():
            QMessageBox.warning(self, "Missing file", f"Missing: {req}")
            return

        self._runtime_installing = True
        self.rebuild_lists()
        QApplication.processEvents()

        prog = QProgressDialog("Setting up shared Python environment…", "Close", 0, 0, self)
        prog.setStyleSheet(PROGRESS_STYLE)
        prog.setWindowTitle("Setup Runtime")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)

        try:
            log_path = self.base_dir / ".cockpit" / "logs" / "shared_env_setup.log"
            py, req_hash = ensure_shared_env(self.base_dir, self.state, req, log_path)
            self.state["shared_env_hash"] = req_hash
            save_state(self.state_path, self.state)
            QMessageBox.information(self, "Runtime ready", f"Python: {py}\nLog: {log_path}")
        except Exception as e:
            log_path = self.base_dir / ".cockpit" / "logs" / "shared_env_setup.log"
            QMessageBox.critical(self, "Setup failed", f"{e}\n\nSee log:\n{log_path}")
        finally:
            self._runtime_installing = False
            prog.close()
            self.rebuild_lists()

    # ----------------------------
    # Dependency maintenance
    # ----------------------------
    def update_libraries(self):
        """Scan ./applications for Python imports and ensure shared env has them installed."""
        req = self.base_dir / "cockpit-requirements.txt"
        if not req.exists():
            QMessageBox.warning(self, "Missing file", f"Missing: {req}")
            return

        # Ensure shared env exists first
        try:
            log_setup = self.base_dir / ".cockpit" / "logs" / "shared_env_setup.log"
            py, _ = ensure_shared_env(self.base_dir, self.state, req, log_setup)
        except Exception as e:
            QMessageBox.critical(self, "Runtime not ready", f"{e}\n\nTip: Click 'Setup Runtime' first.")
            return

        prog = QProgressDialog("Scanning applications and updating libraries…", "Close", 0, 0, self)
        prog.setWindowTitle("Update Libraries")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)
        prog.setStyleSheet(PROGRESS_STYLE)

        try:
            modules = discover_imports_in_tree(self.apps_dir)
            pip_names = sorted(to_pip_names(modules))

            changed = update_cockpit_requirements(req, pip_names)

            log_deps = self.base_dir / ".cockpit" / "logs" / "shared_env_deps.log"
            newly = ensure_packages(py, pip_names, log_deps)

            msg = []
            if changed:
                msg.append("Updated cockpit-requirements.txt")
            if newly:
                msg.append("Installed: " + ", ".join(newly[:10]) + ("…" if len(newly) > 10 else ""))
            if not msg:
                msg.append("No changes needed. Environment already up to date.")

            QMessageBox.information(self, "Update Libraries", "\n".join(msg))
        except Exception as e:
            log_deps = self.base_dir / ".cockpit" / "logs" / "shared_env_deps.log"
            QMessageBox.critical(self, "Update failed", f"{e}\n\nSee log:\n{log_deps}")
        finally:
            prog.close()
            self.refresh()

    # ----------------------------
    # Git sync button (bulk)
    # ----------------------------
    def load_from_git(self):
        repos_file = self.apps_dir / GIT_REPOS_FILE_NAME

        if not repos_file.exists():
            repos_file.parent.mkdir(parents=True, exist_ok=True)
            repos_file.write_text(
                "# One entry per line.\n"
                "# GitHub repo example:\n"
                "https://github.com/eabdiel/ProgreTomato\n"
                "# URL shortcut example:\n"
                "https://github.com\n",
                encoding="utf-8",
            )
            QMessageBox.information(self, "git-repos created", f"Created:\n{repos_file}")
            self.refresh()
            return

        urls = read_git_repos_file(repos_file)
        if not urls:
            QMessageBox.information(self, "No entries", "Your git-repos file has no entries yet.")
            return

        repo_urls = [u for u in urls if parse_github_repo_url(u)]
        if not repo_urls:
            QMessageBox.information(self, "No GitHub repos", "No GitHub repo URLs found to download.")
            self.refresh()
            return

        prog = QProgressDialog("Loading repositories from GitHub…", "Cancel", 0, len(repo_urls), self)
        prog.setStyleSheet(PROGRESS_STYLE)
        prog.setWindowTitle("Load from Git")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)

        ok_downloaded, skipped, failed = [], [], []

        for i, url in enumerate(repo_urls, start=1):
            if prog.wasCanceled():
                skipped.append(("(Canceled)", "User canceled operation"))
                break

            prog.setLabelText(f"Processing {i}/{len(repo_urls)}:\n{url}")
            prog.setValue(i - 1)
            QApplication.processEvents()

            owner, repo = parse_github_repo_url(url)  # type: ignore[misc]
            dest = self.apps_dir / repo

            try:
                if not github_repo_is_public(owner, repo):
                    skipped.append((url, "Repo not found or not public"))
                    continue
                if not github_has_root_main_py_on_main(owner, repo):
                    skipped.append((url, "No root main.py on branch 'main'"))
                    continue

                download_and_extract_main_branch(owner, repo, dest)

                # QoL: merge repo requirements.txt into cockpit-requirements.txt if present
                self._merge_repo_requirements_if_present(dest)

                ok_downloaded.append(f"{owner}/{repo}")

            except requests.exceptions.HTTPError as e:
                failed.append((url, f"HTTP error: {e}"))
            except requests.exceptions.RequestException as e:
                failed.append((url, f"Network error: {e}"))
            except Exception as e:
                failed.append((url, f"Error: {e}"))

        prog.setValue(len(repo_urls))
        prog.close()

        self.refresh()

        msg = []
        if ok_downloaded:
            msg.append("Downloaded/Updated:\n- " + "\n- ".join(ok_downloaded))
        if skipped:
            msg.append("\nSkipped:\n- " + "\n- ".join([f"{u} ({why})" for u, why in skipped]))
        if failed:
            msg.append("\nFailed:\n- " + "\n- ".join([f"{u} ({why})" for u, why in failed]))

        QMessageBox.information(self, "Load from Git — results", "\n".join(msg) if msg else "Nothing to do.")

    # ----------------------------
    # Launch behavior
    # ----------------------------
    def launch_item(self, item: QListWidgetItem):
        key = item.data(Qt.UserRole)
        entry = self.apps_by_key.get(key)
        if not entry:
            return

        try:
            if entry.kind == "git":
                parsed = parse_github_repo_url(entry.path)
                if not parsed:
                    raise RuntimeError("Invalid GitHub repo URL")
                owner, repo = parsed
                dest = self.apps_dir / repo

                prog = QProgressDialog(f"Downloading {owner}/{repo}…", "Cancel", 0, 0, self)
                prog.setStyleSheet(PROGRESS_STYLE)
                prog.setWindowTitle("Download and install")
                prog.setWindowModality(Qt.WindowModal)
                prog.setMinimumDuration(0)
                prog.setValue(0)
                QApplication.processEvents()
                try:
                    if not github_repo_is_public(owner, repo):
                        raise RuntimeError("Repo not found or not public")
                    if not github_has_root_main_py_on_main(owner, repo):
                        raise RuntimeError("No root main.py on branch 'main'")
                    download_and_extract_main_branch(owner, repo, dest)

                    # QoL: merge repo requirements.txt into cockpit-requirements.txt if present
                    self._merge_repo_requirements_if_present(dest)
                finally:
                    prog.close()

                self.refresh()
                return

            launch_app(entry, self.base_dir, self.state)
            save_state(self.state_path, self.state)

        except Exception as e:
            if entry and entry.kind == "py" and not self._runtime_ready():
                QMessageBox.critical(self, "Launch failed", f"{e}\n\nTip: Click 'Setup Runtime' first.")
            else:
                QMessageBox.critical(self, "Launch failed", str(e))

    # ----------------------------
    # Context menu
    # ----------------------------
    def open_context_menu(self, which_list: TileList, pos):
        item = which_list.itemAt(pos)
        if not item:
            return
        key = item.data(Qt.UserRole)

        is_fav = key in self.state.get("favorites", [])
        is_hidden = key in self.state.get("hidden", [])
        size_mode = self.state.get("tile_sizes", {}).get(key, "small")

        menu = QMenu(self)

        act_fav = QAction("Unfavorite" if is_fav else "Favorite", self)
        act_hide = QAction("Unhide" if is_hidden else "Hide", self)
        act_toggle_size = QAction("Make Small Tile" if size_mode == "wide" else "Make Wide Tile", self)
        act_rename = QAction("Rename tile…", self)
        act_icon = QAction("Change icon…", self)
        act_reset_icon = QAction("Reset icon", self)
        act_setup_runtime = QAction("Setup Runtime (Shared)", self)
        act_open = QAction("Open location…", self)

        menu.addAction(act_fav)
        menu.addAction(act_hide)
        menu.addSeparator()
        menu.addAction(act_toggle_size)
        menu.addSeparator()
        menu.addAction(act_rename)
        menu.addAction(act_icon)
        menu.addAction(act_reset_icon)
        menu.addSeparator()
        menu.addAction(act_setup_runtime)
        menu.addSeparator()
        menu.addAction(act_open)

        chosen = menu.exec(which_list.mapToGlobal(pos))
        if not chosen:
            return

        if chosen == act_fav:
            if is_fav:
                self.state["favorites"] = [k for k in self.state["favorites"] if k != key]
            else:
                self.state.setdefault("favorites", []).insert(0, key)
                self.state["hidden"] = [k for k in self.state.get("hidden", []) if k != key]

        elif chosen == act_hide:
            if is_hidden:
                self.state["hidden"] = [k for k in self.state["hidden"] if k != key]
            else:
                self.state.setdefault("hidden", []).insert(0, key)
                self.state["favorites"] = [k for k in self.state.get("favorites", []) if k != key]

        elif chosen == act_toggle_size:
            self.state.setdefault("tile_sizes", {})
            self.state["tile_sizes"][key] = "small" if size_mode == "wide" else "wide"

        elif chosen == act_rename:
            current = self.state.get("title_overrides", {}).get(key, "")
            if not current:
                entry = self.apps_by_key.get(key)
                current = entry.display_name if entry else ""
            text, ok = QInputDialog.getText(self, "Rename tile", "Title:", text=current)
            if ok:
                cleaned = text.strip()
                if cleaned:
                    self.state.setdefault("title_overrides", {})[key] = cleaned
                else:
                    self.state.get("title_overrides", {}).pop(key, None)

        elif chosen == act_icon:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Choose icon image",
                str(self.base_dir),
                "Images (*.png *.ico *.jpg *.jpeg *.bmp *.webp)",
            )
            if file_path:
                self.state.setdefault("icon_overrides", {})[key] = file_path

        elif chosen == act_reset_icon:
            self.state.get("icon_overrides", {}).pop(key, None)

        elif chosen == act_setup_runtime:
            self.setup_runtime()

        elif chosen == act_open:
            entry = self.apps_by_key.get(key)
            if entry:
                target = Path(entry.path)
                folder = target.parent if target.is_file() else target
                self.open_in_explorer(folder)

        self.rebuild_lists()
        save_state(self.state_path, self.state)

    def persist_order_from_ui(self):
        self.state["favorites"] = [self.fav_list.item(i).data(Qt.UserRole) for i in range(self.fav_list.count())]
        self.state["hidden"] = [self.hidden_list.item(i).data(Qt.UserRole) for i in range(self.hidden_list.count())]

        visible_main = [self.main_list.item(i).data(Qt.UserRole) for i in range(self.main_list.count())]
        existing = set(self.apps_by_key.keys())
        excluded = set(self.state.get("favorites", [])) | set(self.state.get("hidden", []))
        leftovers = [
            k for k in self.state.get("order", [])
            if k in existing and k not in excluded and k not in set(visible_main)
        ]
        self.state["order"] = visible_main + leftovers
        save_state(self.state_path, self.state)

    def toggle_hidden(self, checked: bool):
        self.hidden_list.setVisible(checked)
        self.hidden_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    # ----------------------------
    # Explorer helpers
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
