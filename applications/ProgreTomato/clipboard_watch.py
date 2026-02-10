from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import win32clipboard
import win32con


class ClipboardWatcher:
    """
    Poll-based clipboard watcher for robustness.
    Calls `on_text(text)` whenever clipboard text changes.
    """

    def __init__(self, on_text: Callable[[str], None], poll_interval: float = 0.20):
        self._on_text = on_text
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_text: str = ""

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _get_clipboard_text(self) -> str:
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    data = win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
                    return data if isinstance(data, str) else ""
                return ""
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            return ""

    def _run(self) -> None:
        while not self._stop.is_set():
            text = self._get_clipboard_text()
            if text and text != self._last_text:
                self._last_text = text
                self._on_text(text)
            time.sleep(self._poll_interval)
