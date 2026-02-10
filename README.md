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

```
App24_SRE_Application_Cockpit/
│
├── main.py
├── launcher_state.json          # auto-generated
│
└── applications/
    ├── MyTool.exe
    ├── MyPythonApp/
    │   └── main.py
    ├── AnotherTool.exe
    └── git-repos                 # optional (no extension)
```

---

## 🔹 Application Discovery Rules

### Executables
- Any `.exe` placed directly under `./applications` is shown as a launchable tile.

### Python Applications
- Any folder under `./applications` that contains a **top-level `main.py`**
- Subfolders are ignored during discovery.
- Python apps are launched using the same Python interpreter that runs the launcher.

---

## 🔄 GitHub Repository Loading

Create a file named:

```
./applications/git-repos
```

Example contents:

```
https://github.com/eabdiel/ProgreTomato
```

Rules:
- One public GitHub repository per line
- Lines starting with `#` are ignored
- Only repositories with:
  - a public repo
  - a `main` branch
  - a root-level `main.py`
  will be downloaded

Behavior:
- Repositories are downloaded into `./applications/<repo_name>/`
- If the folder already exists, it is **replaced** (simple update mechanism)
- A progress dialog is shown during loading

---

## ▶️ Running the Application

### Requirements
- Python 3.8+
- Windows (primary target)

### Install dependencies
```bash
pip install pyside6 requests
```

### Run
```bash
python main.py
```

---

## 💾 Persistent State

The launcher automatically saves UI state to:

```
launcher_state.json
```

This includes:
- Tile order
- Favorites
- Hidden apps
- Custom names
- Custom icons

You can delete this file at any time to reset the UI.

---

## ⚠️ Notes & Limitations

- GitHub API access is unauthenticated (rate-limited by GitHub)
- Git updates currently replace the entire folder (no partial merges)
- App execution errors are surfaced directly to the user
- Icons extracted from `.exe` files are not yet supported (generic icons used)
- Libraries and dependencies need to be pip-installed if your local python environment doesn't have the libraries used by the linked repos

---

## 🧭 Roadmap (Planned / Optional)

- Extract real icons from executables
- Background Git sync (non-blocking thread)
- Search / filter bar
- App launch arguments & environment variables
- Packaging as a single-file executable (PyInstaller)

---

## © Copyright

Copyright © 2026  
**Edwin A. Rodriguez**

This project is currently intended for personal and internal use.  
If open-sourced in the future, an OSI-approved license (e.g., MIT) will be added.

---

*Built as a practical SRE utility - simple, and automation friendly.
