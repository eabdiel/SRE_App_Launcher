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
#  Main UI controller/window for the cockpit. Wires state + discovery + launching + git sync.
#
#  Copyright (c) 2026 Edwin A. Rodriguez. All rights reserved.
#  Provided "AS IS", without warranty of any kind.
#===============================================================================

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Dict, Any

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
    QStyle,
)

from .constants import APP_TITLE, APP_FOLDER_NAME, STATE_FILE_NAME, GIT_REPOS_FILE_NAME, TILE_SIZE
from .fs_discovery import scan_applications_folder
from .git_sync import (
    parse_github_repo_url,
    github_repo_is_public,
    github_has_root_main_py_on_main,
    download_and_extract_main_branch,
    read_git_repos_file,
)
from .launcher import launch_app
from .state import load_state, save_state, prune_state_for_existing_keys, add_new_keys_to_order
from .ui_widgets import TileList


class MainWindow(QMainWindow):
    """Primary window for the App24 launcher."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)

        self.base_dir = Path(__file__).resolve().parent.parent  # project root
        self.apps_dir = self.base_dir / APP_FOLDER_NAME
        self.state_path = self.base_dir / STATE_FILE_NAME

        self.state = load_state(self.state_path)

        # --- UI ----------------------------------------------------------------
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

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.fav_list)
        splitter.addWidget(self.main_list)
        splitter.addWidget(self.hidden_list)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)
        layout.addWidget(splitter)

        # Persist ordering after drag/drop
        self.fav_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())
        self.main_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())
        self.hidden_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())

        # Auto-refresh polling
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1500)
        self.refresh_timer.timeout.connect(self.refresh_silent)
        self.refresh_timer.start()

        self.refresh()

    # ----------------------------
    # UI population / refresh
    # ----------------------------
    def refresh_silent(self):
        apps = scan_applications_folder(self.apps_dir)
        scanned_keys = sorted([a.key for a in apps])
        last_keys = sorted(self.state.get("_last_scan_keys", []))
        if scanned_keys != last_keys:
            self.refresh()

    def refresh(self):
        apps = scan_applications_folder(self.apps_dir)
        self.apps_by_key = {a.key: a for a in apps}
        self.state["_last_scan_keys"] = sorted(list(self.apps_by_key.keys()))

        existing = set(self.apps_by_key.keys())
        prune_state_for_existing_keys(self.state, existing)
        add_new_keys_to_order(self.state, list(self.apps_by_key.keys()))

        self.rebuild_lists()
        save_state(self.state_path, self.state)

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

            # Icon override
            custom_icon_path = self.state.get("icon_overrides", {}).get(key)
            if custom_icon_path and Path(custom_icon_path).exists():
                item.setIcon(QIcon(custom_icon_path))
            else:
                if app.kind == "exe":
                    item.setIcon(self.style().standardIcon(QStyle.SP_DesktopIcon))
                else:
                    item.setIcon(self.style().standardIcon(QStyle.SP_DirIcon))

            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
            item.setSizeHint(TILE_SIZE)
            list_widget.addItem(item)

        for k in self.state.get("favorites", []):
            add_item(self.fav_list, k)

        for k in self.state.get("order", []):
            if k not in self.state.get("hidden", []) and k not in self.state.get("favorites", []):
                add_item(self.main_list, k)

        for k in self.state.get("hidden", []):
            add_item(self.hidden_list, k)

    # ----------------------------
    # Git sync (Load from Git)
    # ----------------------------
    def _git_repos_file_path(self) -> Path:
        return self.apps_dir / GIT_REPOS_FILE_NAME

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

        urls = read_git_repos_file(repos_file)
        if not urls:
            QMessageBox.information(self, "No repos", "Your git-repos file has no repo URLs yet.")
            return

        prog = QProgressDialog("Loading repositories from GitHub...", "Cancel", 0, len(urls), self)
        prog.setWindowTitle("Load from Git")
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)
        prog.setValue(0)

        ok_downloaded, skipped, failed = [], [], []
        self.statusBar().showMessage("Loading repositories from GitHub...")

        for i, url in enumerate(urls, start=1):
            if prog.wasCanceled():
                skipped.append(("(Canceled)", "User canceled operation"))
                break

            prog.setLabelText(f"Processing {i}/{len(urls)}:\n{url}")
            prog.setValue(i - 1)
            QApplication.processEvents()

            parsed = parse_github_repo_url(url)
            if not parsed:
                skipped.append((url, "Not a valid GitHub repo URL"))
                continue

            owner, repo = parsed
            dest = self.apps_dir / repo

            try:
                if not github_repo_is_public(owner, repo):
                    skipped.append((url, "Repo not found or not public"))
                    continue
                if not github_has_root_main_py_on_main(owner, repo):
                    skipped.append((url, "No root main.py on branch 'main'"))
                    continue

                download_and_extract_main_branch(owner, repo, dest)
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
        entry = self.apps_by_key.get(key)
        if not entry:
            return
        try:
            launch_app(entry)
        except Exception as e:
            QMessageBox.critical(self, "Launch failed", str(e))

    # ----------------------------
    # Context menu
    # ----------------------------
    def open_context_menu(self, which_list: TileList, pos):
        item = which_list.itemAt(pos)
        if not item:
            return
        key = item.data(Qt.UserRole)

        menu = QMenu(self)

        is_fav = key in self.state.get("favorites", [])
        is_hidden = key in self.state.get("hidden", [])

        act_reset_icon = QAction("Reset icon", self)
        act_fav = QAction("Unfavorite" if is_fav else "Favorite", self)
        act_hide = QAction("Unhide" if is_hidden else "Hide", self)
        act_rename = QAction("Rename tile…", self)
        act_icon = QAction("Change icon…", self)
        act_open = QAction("Open location…", self)

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
                self.state["favorites"].insert(0, key)
                self.state["hidden"] = [k for k in self.state["hidden"] if k != key]

        elif chosen == act_hide:
            if is_hidden:
                self.state["hidden"] = [k for k in self.state["hidden"] if k != key]
            else:
                self.state["hidden"].insert(0, key)
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

        elif chosen == act_reset_icon:
            self.state.get("icon_overrides", {}).pop(key, None)

        elif chosen == act_open:
            entry = self.apps_by_key.get(key)
            if entry:
                target = Path(entry.path)
                folder = target.parent if target.is_file() else target
                self.open_in_explorer(folder)

        self.rebuild_lists()
        save_state(self.state_path, self.state)

    # ----------------------------
    # Order persistence
    # ----------------------------
    def persist_order_from_ui(self):
        self.state["favorites"] = [self.fav_list.item(i).data(Qt.UserRole) for i in range(self.fav_list.count())]
        self.state["hidden"] = [self.hidden_list.item(i).data(Qt.UserRole) for i in range(self.hidden_list.count())]

        visible_main = [self.main_list.item(i).data(Qt.UserRole) for i in range(self.main_list.count())]
        existing = set(self.apps_by_key.keys())
        excluded = set(self.state["favorites"]) | set(self.state["hidden"])
        leftovers = [k for k in self.state["order"] if k in existing and k not in excluded and k not in set(visible_main)]

        self.state["order"] = visible_main + leftovers
        save_state(self.state_path, self.state)

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
