# ProgreTomato 🍅 (Alpha)

**ProgreTomato** is a Windows-only automation workbench that records user actions (mouse, keyboard, clipboard) into a step list, lets you edit/debug them, and replays them reliably using a target-window “lock” and window-relative coordinates.

This is an **early alpha** focused on recording/replay for internal tools (browser, SAP GUI, and Windows apps).


## How to Use
- Launch ProgreTomato
- Click Pick Target (click next window)
Then click the target app (browser / SAP GUI / Windows app)
- Ensure Target Lock is ON
- Click Start Recording
- Perform your workflow in the target app
- Click Stop
- Edit steps as needed
- Use:
-- Run for full replay
-- F10 to Step
-- F8 to Reset Step

---

## Key Features (Alpha)

- **Record** mouse clicks, typing, hotkeys, and clipboard copies
- **Target Lock** so the recorder ignores ProgreTomato UI interactions and records only the selected app
- **Pick Target (next click)**: click the button, then click your target app window to select it
- **Replay**
  - **Run** full automation
  - **Step** through one action at a time (F10)
  - **Reset Step** (F8)
- **Window-relative click recording** (normalized client coords) for better reliability when windows move
- **Project persistence**
  - Save/Load JSON
  - Export XLSX template (Inputs/Outputs + steps)

---

## Supported (Current)

- Windows 10/11
- Python 3.10+ recommended
- Tested with:
  - PySide6 (UI)
  - pynput (input capture/replay)
  - pywin32 (window introspection)
  - psutil (process info)

> Note: “Enterprise” apps (SAP GUI, internal portals) often require waits and robust locators (future roadmap).

---

## Setup (Dev)

```bash
git clone <your-repo-url>
cd ProgreTomato

python -m venv .venv
.venv\Scripts\activate

pip install -r requirements.txt
python main.py

