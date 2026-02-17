# SRE Application Cockpit – Installer (No Admin)

This project includes an **Inno Setup** script that installs the cockpit **per-user** (no admin/UAC prompt).

## What the installer does
- Installs to: `%LOCALAPPDATA%\Programs\SRE_Cockpit\`
- Creates:
  - Desktop shortcut: **SRE Application Cockpit**
  - Start Menu folder: **SRE Cockpit**
  - Right-click menu: **Send to → SRE Application Cockpit**
- Configures SendTo so Windows calls:
  - `SRE_Application_Cockpit.exe --import "<selected file>"`

## What you need to build
1. **Build the cockpit EXE** with PyInstaller
   - onefile or onefolder are both supported (see comments in the .iss file)
2. Install **Inno Setup** (compiler)
3. Compile the installer by opening:
   - `SRE_Cockpit_Installer_NoAdmin.iss`
   - Click **Compile**

## Cockpit requirement
The cockpit must support the CLI arguments:
- `--import "<path>"`
- optional: `--prompt`

This repo version includes that support in `main.py` + `cockpit/main_window.py`.

## Quick test (after install)
1. Install the cockpit
2. Right-click any file (EXE, PDF, TXT, etc.)
3. Send to → **SRE Application Cockpit**
4. Open the cockpit and confirm the tile was added under Applications

## Notes
- If your cockpit EXE name differs, update the .iss file shortcuts accordingly.
- If your build is **onefolder**, uncomment the onefolder line in `[Files]`.
