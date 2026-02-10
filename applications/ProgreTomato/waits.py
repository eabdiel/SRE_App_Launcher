from __future__ import annotations

import time
from typing import Optional

import psutil
import win32gui

try:
    import pyperclip
except Exception:
    pyperclip = None


def _now_ms() -> int:
    return int(time.time() * 1000)


def wait_seconds(seconds: float) -> bool:
    time.sleep(max(0.0, seconds))
    return True


def wait_window_title_contains(hwnd: int, text: str, timeout_ms: int = 10000, poll_ms: int = 200) -> bool:
    deadline = _now_ms() + max(0, timeout_ms)
    needle = (text or "").lower()

    while _now_ms() <= deadline:
        try:
            title = win32gui.GetWindowText(hwnd) or ""
        except Exception:
            title = ""
        if needle in title.lower():
            return True
        time.sleep(max(0.02, poll_ms / 1000.0))

    return False


def wait_process_exists(process_name: str, timeout_ms: int = 10000, poll_ms: int = 300) -> bool:
    deadline = _now_ms() + max(0, timeout_ms)
    target = (process_name or "").lower()

    while _now_ms() <= deadline:
        try:
            for p in psutil.process_iter(attrs=["name"]):
                name = (p.info.get("name") or "").lower()
                if name == target:
                    return True
        except Exception:
            pass
        time.sleep(max(0.02, poll_ms / 1000.0))

    return False


def get_clipboard_text() -> str:
    if pyperclip is None:
        return ""
    try:
        return pyperclip.paste() or ""
    except Exception:
        return ""


def wait_clipboard_contains(text: str, timeout_ms: int = 10000, poll_ms: int = 200) -> bool:
    deadline = _now_ms() + max(0, timeout_ms)
    needle = (text or "")

    while _now_ms() <= deadline:
        cur = get_clipboard_text()
        if needle in cur:
            return True
        time.sleep(max(0.02, poll_ms / 1000.0))

    return False
