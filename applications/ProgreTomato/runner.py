from __future__ import annotations

import re
import time
from typing import Dict, Optional

from pynput.keyboard import Controller as KBController, Key
from pynput.mouse import Controller as MouseController, Button

from models import AutomationProject, Step, Action
from win_utils import bring_hwnd_to_front, is_hwnd_valid, client_normalized_to_screen

from win_utils import bring_hwnd_to_front, is_hwnd_valid, client_normalized_to_screen
from waits import wait_seconds, wait_window_title_contains, wait_process_exists, wait_clipboard_contains


HOTKEY_MAP = {
    "ENTER": Key.enter,
    "TAB": Key.tab,
    "BACKSPACE": Key.backspace,
    "ESC": Key.esc,
    "SPACE": Key.space,
    "UP": Key.up,
    "DOWN": Key.down,
    "LEFT": Key.left,
    "RIGHT": Key.right,
    "HOME": Key.home,
    "END": Key.end,
    "PGUP": Key.page_up,
    "PGDN": Key.page_down,
    "DELETE": Key.delete,
}


def _parse_coords(locator: str) -> Optional[tuple[int, int, str]]:
    m = re.search(r"x=(\d+)\s*,\s*y=(\d+)\s*,\s*button=([a-zA-Z]+)", locator)
    if not m:
        return None
    x = int(m.group(1))
    y = int(m.group(2))
    btn = m.group(3).lower()
    return x, y, btn

def _parse_coords_rel(locator: str) -> Optional[tuple[float, float, str]]:
    # locator example: "nx=0.123456,ny=0.456789,button=left"
    m = re.search(r"nx=([0-9.]+)\s*,\s*ny=([0-9.]+)\s*,\s*button=([a-zA-Z]+)", locator)
    if not m:
        return None
    nx = float(m.group(1))
    ny = float(m.group(2))
    btn = m.group(3).lower()
    return nx, ny, btn

def _parse_scroll_rel(locator: str) -> Optional[tuple[float, float]]:
    m = re.search(r"nx=([0-9.]+)\s*,\s*ny=([0-9.]+)", locator)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def _extract_ref(ref: str) -> Optional[tuple[str, str]]:
    m = re.fullmatch(r"\{\{(input|output):([a-zA-Z0-9_\-]+)\}\}", (ref or "").strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def build_data_map(project: AutomationProject) -> Dict[str, str]:
    return {d.key: d.value for d in project.data}


class Runner:
    """
    Runner MVP:
    - Focus: brings hwnd to front
    - Click: replays click by screen coords
    - Type: types literal or resolves {{input:key}} from Data sheet
    - Hotkey: supports ENTER/TAB/BACKSPACE and CTRL+<letter>
    - Wait: uses wait_ms
    """

    def __init__(self, project: AutomationProject, default_hwnd: Optional[int] = None, workbench_hwnd: Optional[int] = None):
        self.project = project
        self.default_hwnd = default_hwnd
        self.workbench_hwnd = workbench_hwnd
        self.kb = KBController()
        self.mouse = MouseController()
        self.data_map = build_data_map(project)

    def run(self, status_cb=None, stop_flag=None, step_delay_ms: int = 80) -> None:
        steps = self.project.steps
        for i, step in enumerate(steps, start=1):
            if stop_flag and stop_flag():
                if status_cb:
                    status_cb(f"Run cancelled at step {i}.")
                return

            if status_cb:
                status_cb(f"Running step {i}/{len(steps)}: {step.action}")

            self.run_step(step)

            if step_delay_ms > 0:
                time.sleep(step_delay_ms / 1000.0)

        if status_cb:
            status_cb("Run completed.")

    def _run_wait_until(self, step: Step) -> None:
        """
        step.meta examples:
          {"kind":"window_title_contains", "text":"Login", "timeout_ms":15000, "poll_ms":200}
          {"kind":"process_exists", "process":"saplogon.exe", "timeout_ms":20000}
          {"kind":"clipboard_contains", "text":"Success", "timeout_ms":10000}
          {"kind":"seconds", "seconds":2.5}
        """
        meta = step.meta or {}
        kind = (meta.get("kind") or "").strip().lower()
        timeout_ms = int(meta.get("timeout_ms", 10000))
        poll_ms = int(meta.get("poll_ms", 200))

        if kind == "seconds":
            seconds = float(meta.get("seconds", 0))
            wait_seconds(seconds)
            return

        if kind == "window_title_contains":
            text = str(meta.get("text", ""))
            hwnd = self._effective_hwnd(step)
            if not hwnd:
                # nothing to wait on
                return
            ok = wait_window_title_contains(hwnd, text, timeout_ms=timeout_ms, poll_ms=poll_ms)
            if not ok:
                raise TimeoutError(f"WAIT_UNTIL window_title_contains timed out: '{text}'")
            return

        if kind == "process_exists":
            proc = str(meta.get("process", ""))
            ok = wait_process_exists(proc, timeout_ms=timeout_ms, poll_ms=poll_ms)
            if not ok:
                raise TimeoutError(f"WAIT_UNTIL process_exists timed out: '{proc}'")
            return

        if kind == "clipboard_contains":
            text = str(meta.get("text", ""))
            ok = wait_clipboard_contains(text, timeout_ms=timeout_ms, poll_ms=poll_ms)
            if not ok:
                raise TimeoutError(f"WAIT_UNTIL clipboard_contains timed out: '{text}'")
            return

        # Unknown kind -> do nothing (for now)
        return

    def run_step(self, step: Step) -> None:
        if step.wait_ms and step.wait_ms > 0:
            time.sleep(step.wait_ms / 1000.0)

        action = (step.action or "").lower()
        if action == Action.WAIT_UNTIL.value:
            self._run_wait_until(step)
            return

        if action == Action.SCROLL.value:
            hwnd = self._effective_hwnd(step)
            if hwnd:
                bring_hwnd_to_front(hwnd)
                time.sleep(0.05)

            dx = int((step.meta or {}).get("dx", 0))
            dy = int((step.meta or {}).get("dy", 0))

            # Move mouse to the scroll point (important for many apps)
            if (step.locator_type or "").lower() == "scroll_rel" and hwnd:
                parsed = _parse_scroll_rel(step.locator or "")
                if parsed:
                    nx, ny = parsed
                    pt = client_normalized_to_screen(hwnd, nx, ny)
                    if pt:
                        self.mouse.position = pt
                        time.sleep(0.02)
            else:
                # best-effort: ignore absolute move if not present
                pass

            self.mouse.scroll(dx, dy)
            return

        if action == Action.FOCUS.value:
            hwnd = self._effective_hwnd(step)
            if hwnd:
                bring_hwnd_to_front(hwnd)
                time.sleep(0.15)
            return

        if action == Action.CLICK.value:
            hwnd = self._effective_hwnd(step)
            if hwnd:
                bring_hwnd_to_front(hwnd)
                time.sleep(0.08)

            # Prefer relative coords if present
            if (step.locator_type or "").lower() == "coords_rel":
                parsed = _parse_coords_rel(step.locator or "")
                if not parsed:
                    return
                nx, ny, btn = parsed

                if not hwnd:
                    return
                pt = client_normalized_to_screen(hwnd, nx, ny)
                if not pt:
                    return
                x, y = pt
            else:
                parsed = _parse_coords(step.locator or "")
                if not parsed:
                    return
                x, y, btn = parsed

            self.mouse.position = (x, y)
            time.sleep(0.02)
            button = Button.left if btn == "left" else Button.right if btn == "right" else Button.left
            self.mouse.click(button, 1)
            return

        if action == Action.TYPE.value:
            hwnd = self._effective_hwnd(step)
            if hwnd:
                bring_hwnd_to_front(hwnd)
                time.sleep(0.05)

            text = self._resolve_type_text(step)
            if text:
                self.kb.type(text)
            return

        if action == Action.HOTKEY.value:
            hwnd = self._effective_hwnd(step)
            if hwnd:
                bring_hwnd_to_front(hwnd)
                time.sleep(0.05)

            self._run_hotkey(step.value or "")
            return

        if action == Action.WAIT.value:
            if step.wait_ms and step.wait_ms > 0:
                time.sleep(step.wait_ms / 1000.0)
            return

        # READ_CLIPBOARD is not replayed
        return

    def _effective_hwnd(self, step: Step) -> Optional[int]:
        """
        Use the step hwnd if valid, otherwise fallback to default_hwnd.
        Also avoid using the workbench hwnd as a target.
        """
        if step.hwnd and is_hwnd_valid(step.hwnd):
            if self.workbench_hwnd and step.hwnd == self.workbench_hwnd:
                return self.default_hwnd if (self.default_hwnd and is_hwnd_valid(self.default_hwnd)) else None
            return step.hwnd

        if self.default_hwnd and is_hwnd_valid(self.default_hwnd):
            return self.default_hwnd

        return None

    def _resolve_type_text(self, step: Step) -> str:
        ref = _extract_ref(step.input_ref)
        if ref and ref[0] == "input":
            key = ref[1]
            return self.data_map.get(key, "")
        return step.value or ""

    def _run_hotkey(self, hotkey: str) -> None:
        hk = (hotkey or "").strip().upper()

        m = re.fullmatch(r"CTRL\+([A-Z0-9])", hk)
        if m:
            ch = m.group(1).lower()
            with self.kb.pressed(Key.ctrl):
                self.kb.press(ch)
                self.kb.release(ch)
            return

        if hk in HOTKEY_MAP:
            keyobj = HOTKEY_MAP[hk]
            self.kb.press(keyobj)
            self.kb.release(keyobj)
            return

        if hk:
            self.kb.type(hk)
