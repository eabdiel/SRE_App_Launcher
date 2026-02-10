SRE APPLICATION COCKPIT
=======================

NOTE:
-----
This README was generated with AI assistance to ensure clarity, consistency,
and grammar uniformity across documentation. All technical design decisions,
architecture, and implementation reflect the author's intent and ownership.

------------------------------------------------------------------------------

SRE Application Cockpit 🚀
<img width="976" height="752" alt="image" src="https://github.com/user-attachments/assets/0fae80a3-4e08-4bff-b2a7-150aec682b28" />

A Windows-Phone / Metro-style application launcher that acts as a single control
center for:

- Native executables (.exe)
- Windows shortcuts (.lnk)
- Python applications (folders with main.py)
- Public GitHub Python repositories (auto-download & update)
- Website shortcuts (open in browser)

Designed for non-technical users:
No manual virtualenvs, no pip commands, no setup scripts.


------------------------------------------------------------------------------

KEY FEATURES
------------

- Metro / Windows-Phone inspired tile UI
- Favorites, Hidden apps, and tile resizing (Small / Wide)
- Shared Python runtime (one environment for all apps)
- Import Python apps directly from GitHub
- URL tiles for internal tools & websites
- Automatic dependency detection & installation
- Custom icons and renamed tiles
- Scrolling banner for announcements or notes

------------------------------------------------------------------------------

QUICK GUIDE (START HERE)
-----------------------

1) RUN THE COCKPIT

python main.py

Or launch the packaged executable if provided.

------------------------------------------------------------------------------

2) ADD APPLICATIONS

Option A — Local Apps (Drag & Drop)
----------------------------------
Drop any of the following into the ./applications folder:
- .exe
- .lnk (Windows shortcut)
- A Python app folder containing main.py

They appear instantly as tiles.

Option B — GitHub Python Apps
-----------------------------
1. Open ./applications/git-repos
2. Add one repository URL per line:
   https://github.com/eabdiel/ProgreTomato
3. Click "Load from Git"

Requirements:
- Public repo
- main.py at repository root

If requirements.txt exists, it is merged automatically.

Option C — Website Shortcuts
----------------------------
Add any URL to git-repos:
https://github.com
https://internal-dashboard.company.com

These appear as browser-launch tiles.

------------------------------------------------------------------------------

3) SETUP PYTHON RUNTIME (ONE-TIME)

Click "Setup Runtime"

Creates a shared Python environment bundled with the cockpit.
No system Python required for end users.

------------------------------------------------------------------------------

4) INSTALL / UPDATE LIBRARIES

Click "Update Libraries"

This will:
- Scan all .py files under ./applications
- Detect imported modules
- Update cockpit-requirements.txt
- Install missing packages into the shared runtime

This resolves errors such as:
ModuleNotFoundError: No module named 'pynput'

------------------------------------------------------------------------------

FOLDER STRUCTURE
----------------

App24_SRE_Application_Cockpit/
|
|-- main.py
|-- banner.txt
|-- cockpit-requirements.txt
|-- runtime_env/
|
|-- applications/
|   |-- git-repos
|   |-- MyExeApp.exe
|   |-- MyShortcut.lnk
|   |-- MyPythonApp/
|       |-- main.py
|
|-- cockpit/
|-- .cockpit/
    |-- logs/

------------------------------------------------------------------------------

TILE ACTIONS (RIGHT-CLICK)
-------------------------

- Favorite / Unfavorite
- Hide / Unhide
- Small / Wide tile
- Rename tile
- Change icon
- Open file location
- Setup Runtime shortcut

------------------------------------------------------------------------------

BANNER TEXT
-----------

Edit banner.txt to control the scrolling banner:

Welcome to the SRE Application Cockpit
Drop apps into /applications or load them from GitHub

------------------------------------------------------------------------------

DEPENDENCY STRATEGY
-------------------

- One shared Python runtime
- No per-app virtual environments
- No user-run pip commands

Dependencies come from:
- Detected imports
- Repo requirements.txt (if present)
- Manual cockpit-requirements.txt entries

------------------------------------------------------------------------------

LOGS & TROUBLESHOOTING
---------------------

Logs location:
.cockpit/logs/

Useful files:
- shared_env_setup.log
- shared_env_deps.log

------------------------------------------------------------------------------

AUTHOR
------

Edwin A. Rodriguez
SAP COE / SRE / Automation / Risk Engineering

------------------------------------------------------------------------------

LICENSE
-------

MIT License

Use it. Modify it. Ship it. Improve it.

------------------------------------------------------------------------------

“One launcher. One runtime. Zero friction.”
