#===============================================================================
#  SRE Applications Cockpit | cockpit/main_window.py
#===============================================================================
#  Author      : Edwin A. Rodriguez
#  Created     : 2026-02-10
#  Last Update : 2026-02-11
#
#  Copyright
#  ---------
#  (c) 2026 Edwin A. Rodriguez. All rights reserved.
#
#  Description
#  -----------
#  Main Metro/Windows-Phone style UI for the cockpit:
#    - Tile lists: Favorites, Main, Hidden (collapsible)
#    - Drag & drop ordering (persisted in launcher_state.json)
#    - Drag & drop import into ./applications:
#         * drop .exe -> creates .lnk in ./applications
#         * drop .lnk/.url -> copies into ./applications
#         * drop URL text -> creates .url in ./applications
#         * drop folder -> copies into ./applications (python app folder)
#    - GitHub import via applications/git-repos (plus URL shortcuts)
#    - Shared Python runtime setup + dependency update (shared env)
#    - Right-click actions: favorite, hide, rename, icon, tile size, remove
#
#  Styling
#  -------
#  - Dark gray main window background
#  - Tile canvases (list backgrounds) are dark to avoid “white noise”
#  - Dialogs/menus use dark background + white text via global QSS
#
#  IMPORTANT
#  ---------
#  Keep indentation consistent. Do NOT nest "def ..." blocks inside other methods.
#===============================================================================

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QSplitter,
    QToolButton,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QLabel,
    QComboBox,
)

from .banner_widget import BannerWidget
from .constants import (
    APP_TITLE,
    APP_FOLDER_NAME,
    STATE_FILE_NAME,
    GIT_REPOS_FILE_NAME,
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


# ----------------------------
# Dark Theme (Global)
# ----------------------------
DARK_QSS = """
/* =========================
   APP SURFACES / CONTAINERS
   ========================= */
QMainWindow {
    background-color: #2b2b2b;
    color: #ffffff;
    font-family: "Segoe UI";
}

QSplitter::handle { background: #2b2b2b; }

/* Tile canvases */
QListWidget {
    background-color: #1f1f1f;
    border: 1px solid #3a3a3a;
    outline: none;
}
QListWidget::item { border: none; }

/* =========================
   CONTROLS
   ========================= */
QPushButton, QToolButton {
    background-color: #1f1f1f;
    color: #ffffff;
    border: 1px solid #3a3a3a;
    padding: 6px 10px;
}
QPushButton:hover, QToolButton:hover { background-color: #2a2a2a; }
QPushButton:pressed, QToolButton:pressed { background-color: #333333; }

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #141414;
    color: #ffffff;
    border: 1px solid #3a3a3a;
    selection-background-color: #2d5b8a;
    selection-color: #ffffff;
}

QComboBox {
    background-color: #141414;
    color: #ffffff;
    border: 1px solid #3a3a3a;
    padding: 4px 8px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e1e;
    color: #ffffff;
    selection-background-color: #2d5b8a;
    selection-color: #ffffff;
    border: 1px solid #3a3a3a;
}

/* =========================
   POPUPS / MENUS
   ========================= */
QMenu {
    background-color: #1e1e1e;
    color: #ffffff;
    border: 1px solid #3a3a3a;
}
QMenu::item:selected {
    background-color: #2d5b8a;
    color: #ffffff;
}

QDialog, QMessageBox, QInputDialog, QProgressDialog {
    background-color: #1e1e1e;
    color: #ffffff;
}

/* Force readable text inside popups */
QDialog QLabel,
QMessageBox QLabel,
QInputDialog QLabel,
QProgressDialog QLabel {
    color: #ffffff;
    background: transparent;
}

/* Buttons inside popups */
QDialog QPushButton,
QMessageBox QPushButton,
QInputDialog QPushButton,
QProgressDialog QPushButton {
    color: #ffffff;
}

QProgressBar {
    border: 1px solid #3a3a3a;
    background-color: #141414;
    color: #ffffff;
    text-align: center;
}
QProgressBar::chunk { background-color: #2d5b8a; }

/* =========================
   SCROLLBARS
   ========================= */
QScrollBar:vertical {
    background: #1e1e1e;
    width: 12px;
    margin: 0px;
}
QScrollBar::handle:vertical {
    background: #3a3a3a;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover { background: #4a4a4a; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }

/* =========================
   TILE SAFE ZONE (prevents
   global styling from painting
   behind text inside tiles)
   ========================= */
TileWidget, TileWidget * {
    background: transparent;
}
"""



class MainWindow(QMainWindow):
    # -------------------------------------------------------------------------
    # Initialization / UI Layout
    # -------------------------------------------------------------------------
    def __init__(self):
        super().__init__()

        # Apply global dark theme at the app level (covers dialogs, menus, etc.)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(DARK_QSS)

        self.setWindowTitle(APP_TITLE)

        self.base_dir = Path(__file__).resolve().parent.parent
        self.apps_dir = self.base_dir / APP_FOLDER_NAME
        self.state_path = self.base_dir / STATE_FILE_NAME
        self.state = load_state(self.state_path)

        self._runtime_installing = False
        self.setAcceptDrops(True)

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # -------------------------
        # Header
        # -------------------------
        header = QHBoxLayout()
        title = QLabel(
            f"<b>{APP_TITLE}</b> — drop EXEs/LNKs/URLs or Python app folders into <code>./{APP_FOLDER_NAME}</code>"
        )
        title.setStyleSheet("color: #ffffff; background: transparent;")
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

        # -------------------------
        # Banner (edit ./banner.txt)
        # -------------------------
        self.banner = BannerWidget(self.base_dir / "banner.txt")
        # Keep banner dark but distinct
        self.banner.setStyleSheet(
            "QFrame#BannerWidget{background:#1f1f1f;border:1px solid #3a3a3a;} QLabel{color:white;}"
        )
        layout.addWidget(self.banner)

        # -------------------------
        # Quick controls (sorting + filtering)
        # -------------------------
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        self.btn_sort_alpha = QToolButton()
        self.btn_sort_alpha.setText("A→Z")
        self.btn_sort_alpha.setToolTip("Sort applications alphabetically")
        self.btn_sort_alpha.clicked.connect(lambda: self.apply_sort_mode("alpha"))
        controls_row.addWidget(self.btn_sort_alpha)

        self.btn_sort_type = QToolButton()
        self.btn_sort_type.setText("Type")
        self.btn_sort_type.setToolTip("Sort applications by type (Python / URL / Shortcut / Executable)")
        self.btn_sort_type.clicked.connect(lambda: self.apply_sort_mode("type"))
        controls_row.addWidget(self.btn_sort_type)

        controls_row.addSpacing(12)

        self.cbo_filter = QComboBox()
        self.cbo_filter.addItems(["All Types", "Python", "URL", "Executable", "Shortcut"])
        self.cbo_filter.setToolTip("Filter the main list by application type")
        self.cbo_filter.currentIndexChanged.connect(self.on_filter_changed)
        controls_row.addWidget(self.cbo_filter)

        controls_row.addStretch(1)
        layout.addLayout(controls_row)

        # -------------------------
        # Lists
        # -------------------------
        self.fav_list = TileList()
        self.fav_list.itemDoubleClicked.connect(self.launch_item)
        self.fav_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.fav_list.customContextMenuRequested.connect(lambda pos: self.open_context_menu(self.fav_list, pos))

        self.main_list = TileList()
        self.main_list.itemDoubleClicked.connect(self.launch_item)
        self.main_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.main_list.customContextMenuRequested.connect(lambda pos: self.open_context_menu(self.main_list, pos))

        # Ensure list canvases are dark (even if TileList sets its own)
        for lst in (self.fav_list, self.main_list):
            lst.setStyleSheet("QListWidget{background:#1f1f1f;border:1px solid #3a3a3a;}")

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
        self.hidden_list.setStyleSheet("QListWidget{background:#1f1f1f;border:1px solid #3a3a3a;}")

        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.fav_list)
        splitter.addWidget(self.main_list)
        splitter.addWidget(self.hidden_list)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 1)

        # Splitter handle styling helps reduce visual noise
        splitter.setStyleSheet("QSplitter::handle{background:#2b2b2b;}")

        layout.addWidget(splitter)

        # Reorder persistence
        self.fav_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())
        self.main_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())
        self.hidden_list.model().rowsMoved.connect(lambda *_: self.persist_order_from_ui())

        # Periodic refresh (detect filesystem changes)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1500)
        self.refresh_timer.timeout.connect(self.refresh_silent)
        self.refresh_timer.start()

        # Restore persisted filter selection
        bucket = self._current_filter_bucket()
        mapping = {"all": 0, "python": 1, "url": 2, "executable": 3, "shortcut": 4}
        self.cbo_filter.setCurrentIndex(mapping.get(bucket, 0))
        self._apply_drag_rules_for_filter()

        self.refresh()

    # -------------------------------------------------------------------------
    # Drag & Drop (pin tiles quickly)
    # -------------------------------------------------------------------------
    def dragEnterEvent(self, event):
        md = event.mimeData()
        if md.hasUrls() or md.hasText():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
        added_any = False

        if md.hasUrls():
            for u in md.urls():
                try:
                    if u.isLocalFile():
                        p = Path(u.toLocalFile())
                        if not p.exists():
                            continue
                        if p.is_file() and p.suffix.lower() in (".exe", ".lnk", ".url"):
                            self._import_file_as_tile(p)
                            added_any = True
                        elif p.is_dir():
                            self._import_folder_as_tile(p)
                            added_any = True
                    else:
                        url = u.toString().strip()
                        if url.lower().startswith(("http://", "https://")):
                            self._create_url_shortcut(url)
                            added_any = True
                except Exception:
                    continue

        if md.hasText():
            t = (md.text() or "").strip()
            if t.lower().startswith(("http://", "https://")):
                try:
                    self._create_url_shortcut(t)
                    added_any = True
                except Exception:
                    pass

        if added_any:
            self.refresh()

        event.acceptProposedAction()

    def _import_file_as_tile(self, src: Path):
        self.apps_dir.mkdir(parents=True, exist_ok=True)

        if src.suffix.lower() in (".lnk", ".url"):
            dest = self.apps_dir / src.name
            if dest.exists():
                return
            shutil.copy2(src, dest)
            return

        if src.suffix.lower() == ".exe":
            dest = self.apps_dir / f"{src.stem}.lnk"
            if dest.exists():
                return
            self._create_windows_shortcut(target=src, link_path=dest)

    def _import_folder_as_tile(self, folder: Path):
        self.apps_dir.mkdir(parents=True, exist_ok=True)
        dest = self.apps_dir / folder.name
        if dest.exists():
            return
        shutil.copytree(folder, dest)

    def _create_url_shortcut(self, url: str):
        self.apps_dir.mkdir(parents=True, exist_ok=True)
        safe = url.replace("https://", "").replace("http://", "")
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", safe).strip("_")
        if not safe:
            safe = "website"
        dest = self.apps_dir / f"{safe}.url"
        if dest.exists():
            return
        dest.write_text(f"[InternetShortcut]\nURL={url}\n", encoding="utf-8")

    def _create_windows_shortcut(self, target: Path, link_path: Path):
        if not sys.platform.startswith("win"):
            shutil.copy2(target, link_path)
            return
        ps = (
            "$WshShell = New-Object -ComObject WScript.Shell; "
            f"$Shortcut = $WshShell.CreateShortcut('{str(link_path)}'); "
            f"$Shortcut.TargetPath = '{str(target)}'; "
            "$Shortcut.WorkingDirectory = (Split-Path $Shortcut.TargetPath); "
            "$Shortcut.Save();"
        )
        subprocess.check_call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps])

    # -------------------------------------------------------------------------
    # Git file parsing + placeholders
    # -------------------------------------------------------------------------
    def _entries_from_git_file(self) -> list[tuple[str, str, str]]:
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
        existing_names = {Path(a.path).name for a in apps if a.path}
        for kind, display, value in self._entries_from_git_file():
            if kind == "git":
                if display in existing_names:
                    continue
                apps.append(AppEntry(key=f"git:{display}", kind="git", display_name=display, path=value, launch_target=value))
            elif kind == "url":
                apps.append(AppEntry(key=f"url:{value}", kind="url", display_name=display, path=value, launch_target=value))
        return apps

    def _merge_repo_requirements_if_present(self, repo_folder: Path) -> bool:
        repo_req = repo_folder / "requirements.txt"
        if not repo_req.exists():
            return False
        cockpit_req = self.base_dir / "cockpit-requirements.txt"
        try:
            pkgs: list[str] = []
            for line in repo_req.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith(("-e ", "--")):
                    continue
                pkgs.append(line)
            if not pkgs:
                return False
            return update_cockpit_requirements(cockpit_req, pkgs)
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Refresh / rebuild
    # -------------------------------------------------------------------------
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

        # If user previously chose a sort mode, re-apply it after refresh.
        sort_mode = str(self.state.get("ui_sort_mode", "manual")).lower()
        if sort_mode in ("alpha", "type"):
            self.apply_sort_mode(sort_mode)
            save_state(self.state_path, self.state)
            return

        self.rebuild_lists()
        save_state(self.state_path, self.state)

    def rebuild_lists(self):
        """Rebuild Favorites, Main, and Hidden lists respecting filter state."""
        self.fav_list.clear()
        self.main_list.clear()
        self.hidden_list.clear()

        filter_bucket = self._current_filter_bucket()

        def add_item(list_widget: TileList, key: str):
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
            elif app.kind == "urlfile":
                subtitle = "Website"
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

            size_mode = self.state.get("tile_sizes", {}).get(key, "wide")
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
            if k in self.state.get("hidden", []) or k in self.state.get("favorites", []):
                continue
            app = self.apps_by_key.get(k)
            bucket = self._kind_bucket(app.kind if app else "")
            if filter_bucket != "all" and bucket != filter_bucket:
                continue
            add_item(self.main_list, k)

        for k in self.state.get("hidden", []):
            app = self.apps_by_key.get(k)
            bucket = self._kind_bucket(app.kind if app else "")
            if filter_bucket != "all" and bucket != filter_bucket:
                continue
            add_item(self.hidden_list, k)

    def _tile_color_for_key(self, k: str) -> str:
        h = hashlib.sha1(k.encode("utf-8")).hexdigest()
        idx = int(h[:2], 16) % len(METRO_TILE_COLORS)
        return METRO_TILE_COLORS[idx]

    def _runtime_ready(self) -> bool:
        req = self.base_dir / "cockpit-requirements.txt"
        venv_py = self.base_dir / "runtime_env" / "Scripts" / "python.exe"
        return venv_py.exists() and req.exists() and bool(self.state.get("shared_env_hash"))

    # -------------------------------------------------------------------------
    # Sorting & filtering helpers
    # -------------------------------------------------------------------------
    def _kind_bucket(self, kind: str) -> str:
        """Normalize internal kinds to user-facing buckets."""
        if kind in ("py", "git"):
            return "python"
        if kind in ("urlfile", "url"):
            return "url"
        if kind == "lnk":
            return "shortcut"
        if kind == "exe":
            return "executable"
        return kind

    def _current_filter_bucket(self) -> str:
        return str(self.state.get("ui_filter_bucket", "all")).lower()

    def _set_filter_bucket(self, bucket: str) -> None:
        self.state["ui_filter_bucket"] = bucket
        save_state(self.state_path, self.state)

    def _set_sort_mode(self, mode: str) -> None:
        # mode: manual | alpha | type
        self.state["ui_sort_mode"] = mode
        save_state(self.state_path, self.state)

    def on_filter_changed(self) -> None:
        text = (self.cbo_filter.currentText() or "").strip().lower()
        if text.startswith("all"):
            bucket = "all"
        elif text.startswith("python"):
            bucket = "python"
        elif text.startswith("url"):
            bucket = "url"
        elif text.startswith("exe"):
            bucket = "executable"
        elif text.startswith("shortcut"):
            bucket = "shortcut"
        else:
            bucket = "all"

        self._set_filter_bucket(bucket)
        self._apply_drag_rules_for_filter()
        self.rebuild_lists()

    def _apply_drag_rules_for_filter(self) -> None:
        # If the list is filtered, dragging only affects the subset and can be confusing.
        # Disable drag/drop on the main list while filtered to keep state consistent.
        bucket = self._current_filter_bucket()
        drag_ok = bucket == "all"
        self.main_list.setDragEnabled(drag_ok)
        self.main_list.setAcceptDrops(drag_ok)
        self.main_list.setDropIndicatorShown(drag_ok)

    def apply_sort_mode(self, mode: str) -> None:
        """Apply a sort to the main list and persist the resulting order."""
        mode = (mode or "").lower().strip()
        if mode not in ("alpha", "type"):
            return

        existing = set(self.apps_by_key.keys())
        excluded = set(self.state.get("favorites", [])) | set(self.state.get("hidden", []))
        main_keys = [k for k in self.state.get("order", []) if k in existing and k not in excluded]

        def title_for_key(k: str) -> str:
            app = self.apps_by_key.get(k)
            if not app:
                return k
            return str(self.state.get("title_overrides", {}).get(k, app.display_name)).lower()

        def sort_key_alpha(k: str):
            return (title_for_key(k), k)

        def sort_key_type(k: str):
            app = self.apps_by_key.get(k)
            bucket = self._kind_bucket(app.kind if app else "")
            order = {"python": 0, "url": 1, "shortcut": 2, "executable": 3}
            return (order.get(bucket, 99), title_for_key(k), k)

        if mode == "alpha":
            main_keys = sorted(main_keys, key=sort_key_alpha)
        else:
            main_keys = sorted(main_keys, key=sort_key_type)

        # Persist back into state["order"] while keeping any non-main keys intact.
        leftovers = [
            k for k in self.state.get("order", [])
            if k in existing and k not in set(main_keys)
        ]
        self.state["order"] = main_keys + leftovers
        self._set_sort_mode(mode)

        self._apply_drag_rules_for_filter()
        self.rebuild_lists()
        save_state(self.state_path, self.state)

    # -------------------------------------------------------------------------
    # Runtime setup
    # -------------------------------------------------------------------------
    def setup_runtime(self):
        req = self.base_dir / "cockpit-requirements.txt"
        if not req.exists():
            QMessageBox.warning(self, "Missing file", f"Missing: {req}")
            return

        self._runtime_installing = True
        self.rebuild_lists()
        QApplication.processEvents()

        prog = QProgressDialog("Setting up shared Python environment…", "Close", 0, 0, self)
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

    # -------------------------------------------------------------------------
    # Dependency maintenance
    # -------------------------------------------------------------------------
    def update_libraries(self):
        req = self.base_dir / "cockpit-requirements.txt"
        if not req.exists():
            QMessageBox.warning(self, "Missing file", f"Missing: {req}")
            return

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

    # -------------------------------------------------------------------------
    # Git sync button (bulk)
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Launch behavior
    # -------------------------------------------------------------------------
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
                    self._merge_repo_requirements_if_present(dest)
                finally:
                    prog.close()

                self.refresh()
                return

            launch_app(entry, self.base_dir, self.state)
            save_state(self.state_path, self.state)

        except Exception as e:
            if entry.kind == "py" and not self._runtime_ready():
                QMessageBox.critical(self, "Launch failed", f"{e}\n\nTip: Click 'Setup Runtime' first.")
            else:
                QMessageBox.critical(self, "Launch failed", str(e))

    # -------------------------------------------------------------------------
    # Context menu
    # -------------------------------------------------------------------------
    def open_context_menu(self, which_list: TileList, pos):
        item = which_list.itemAt(pos)
        if not item:
            return
        key = item.data(Qt.UserRole)

        is_fav = key in self.state.get("favorites", [])
        is_hidden = key in self.state.get("hidden", [])
        size_mode = self.state.get("tile_sizes", {}).get(key, "wide")

        menu = QMenu(self)

        act_fav = QAction("Unfavorite" if is_fav else "Favorite", self)
        act_hide = QAction("Unhide" if is_hidden else "Hide", self)
        act_toggle_size = QAction("Make Small Tile" if size_mode == "wide" else "Make Wide Tile", self)
        act_rename = QAction("Rename tile…", self)
        act_icon = QAction("Change icon…", self)
        act_reset_icon = QAction("Reset icon", self)
        act_setup_runtime = QAction("Setup Runtime (Shared)", self)
        act_open = QAction("Open location…", self)
        act_remove = QAction("Uninstall / Remove…", self)

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
        menu.addSeparator()
        menu.addAction(act_remove)

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
            # Native dialogs may ignore QSS on Windows; but keep native by default.
            # If you want fully dark file dialog, switch to DontUseNativeDialog.
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

        elif chosen == act_remove:
            entry = self.apps_by_key.get(key)
            if not entry:
                return

            label = self.state.get("title_overrides", {}).get(key, entry.display_name)
            res = QMessageBox.question(
                self,
                "Uninstall / Remove",
                f"Remove '{label}'?\n\nThis will delete the shortcut/app from the applications folder.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return

            try:
                p = Path(entry.path)

                if entry.kind == "git":
                    repos_file = self.apps_dir / GIT_REPOS_FILE_NAME
                    if repos_file.exists():
                        lines = repos_file.read_text(encoding="utf-8", errors="ignore").splitlines()
                        kept = [ln for ln in lines if ln.strip() != entry.path]
                        repos_file.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
                else:
                    if p.exists():
                        if p.is_dir():
                            shutil.rmtree(p)
                        else:
                            p.unlink()

                self.state["favorites"] = [k for k in self.state.get("favorites", []) if k != key]
                self.state["hidden"] = [k for k in self.state.get("hidden", []) if k != key]
                self.state["order"] = [k for k in self.state.get("order", []) if k != key]
                self.state.get("title_overrides", {}).pop(key, None)
                self.state.get("icon_overrides", {}).pop(key, None)
                self.state.get("tile_sizes", {}).pop(key, None)

            except Exception as e:
                QMessageBox.critical(self, "Remove failed", str(e))

            self.refresh()
            return

        self.rebuild_lists()
        save_state(self.state_path, self.state)

    def persist_order_from_ui(self):
        """Persist ordering after drag/drop. Also switches sort mode to manual."""
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
        self._set_sort_mode("manual")
        save_state(self.state_path, self.state)

    def toggle_hidden(self, checked: bool):
        self.hidden_list.setVisible(checked)
        self.hidden_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)

    # -------------------------------------------------------------------------
    # Explorer helpers
    # -------------------------------------------------------------------------
    def open_apps_folder(self):
        """Open the ./applications folder in the OS file explorer."""
        self.open_in_explorer(self.apps_dir)

    def open_in_explorer(self, folder: Path):
        """Open a folder in the system file explorer (Windows/Mac/Linux)."""
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(folder)])
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except Exception as e:
            QMessageBox.warning(self, "Open failed", str(e))
