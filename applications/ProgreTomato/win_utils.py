from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
import win32gui
import win32process
import win32api
import win32con
import psutil  # comes with some envs; if missing, install psutil
# If psutil isn't available, we'll fallback gracefully.


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    pid: Optional[int]
    process_name: str


def get_foreground_window_info() -> WindowInfo:
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd) or ""
    pid = None
    proc_name = ""

    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            p = psutil.Process(pid)
            proc_name = p.name()
        except Exception:
            proc_name = ""
    except Exception:
        pid = None
        proc_name = ""

    return WindowInfo(hwnd=hwnd, title=title, pid=pid, process_name=proc_name)


def bring_hwnd_to_front(hwnd: int) -> None:
    # Basic attempt to focus a window; Windows can be picky about foreground changes.
    try:
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass


def is_hwnd_valid(hwnd: Optional[int]) -> bool:
    if not hwnd:
        return False
    try:
        return bool(win32gui.IsWindow(hwnd))
    except Exception:
        return False

def get_window_info_from_point(x: int, y: int) -> WindowInfo:
    """
    Returns the top-level window info under the given screen coordinates.
    """
    hwnd = win32gui.WindowFromPoint((x, y))

    # Resolve to top-level root window (avoids child controls)
    try:
        hwnd = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
    except Exception:
        pass

    title = win32gui.GetWindowText(hwnd) or ""
    pid = None
    proc_name = ""

    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        try:
            p = psutil.Process(pid)
            proc_name = p.name()
        except Exception:
            proc_name = ""
    except Exception:
        pid = None
        proc_name = ""

    return WindowInfo(hwnd=hwnd, title=title, pid=pid, process_name=proc_name)

def get_client_area_screen(hwnd: int) -> Optional[tuple[int, int, int, int]]:
    """
    Returns (left, top, width, height) of the *client* area in screen coordinates.
    This excludes title bar/borders, which is what you want for stable relative clicking.
    """
    if not is_hwnd_valid(hwnd):
        return None

    try:
        # Client rect in client coords
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        w = max(0, right - left)
        h = max(0, bottom - top)
        if w == 0 or h == 0:
            return None

        # Convert client origin (0,0) to screen coords
        origin = win32gui.ClientToScreen(hwnd, (0, 0))
        sx, sy = origin[0], origin[1]
        return (sx, sy, w, h)
    except Exception:
        return None


def screen_to_client_normalized(hwnd: int, x: int, y: int) -> Optional[tuple[float, float]]:
    """
    Converts a screen (x,y) into normalized client coords (nx, ny) in [0..1].
    """
    area = get_client_area_screen(hwnd)
    if not area:
        return None
    cl, ct, cw, ch = area
    nx = (x - cl) / float(cw)
    ny = (y - ct) / float(ch)
    return nx, ny


def client_normalized_to_screen(hwnd: int, nx: float, ny: float) -> Optional[tuple[int, int]]:
    """
    Converts normalized client coords into screen (x,y) using current client area.
    """
    area = get_client_area_screen(hwnd)
    if not area:
        return None
    cl, ct, cw, ch = area

    # Clamp a bit to avoid clicking outside due to rounding/window changes
    nx = max(0.0, min(1.0, nx))
    ny = max(0.0, min(1.0, ny))

    x = int(cl + nx * cw)
    y = int(ct + ny * ch)
    return x, y
