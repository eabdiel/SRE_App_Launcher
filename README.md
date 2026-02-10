# SRE Application Cockpit

A lightweight, centralized **application launcher** that dynamically discovers and launches local executables and Python applications from a single folder.

Designed for engineers, SREs, and power users who want a **simple, visual cockpit** for their internal tools without hard-coding paths or maintaining a static config.

---

## ✨ Key Features

- **Drop-in discovery**
  - Place apps inside `./applications`
  - No registration, no config files per app

- **Supported application types**
  - Windows executables (`.exe`)
  - Python applications stored in folders containing a top-level `main.py`
    - Only the first directory level is scanned (no deep recursion)

- **Tile-based UI**
  - Square tiles with app name and icon
  - Drag & drop to reorder
  - Double-click to launch

- **Organization**
  - ⭐ Favorites (pinned at the top)
  - 🙈 Hidden apps (collapsible section)
  - Persistent layout and state

- **GitHub integration**
  - Optional `git-repos` manifest file
  - Download or update public GitHub repositories automatically
  - Repos are imported only if the `main` branch contains a root-level `main.py`
  - Imported repos become normal launchable apps

- **Customization**
  - Rename tiles
  - Change tile icons (PNG / ICO / JPG)
  - State persisted in `launcher_state.json`

---

## 📁 Folder Structure

