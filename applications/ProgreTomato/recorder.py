from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Set
import time
import threading

from pynput import keyboard, mouse

from models import Step, Action, Channel
from win_utils import get_foreground_window_info
from clipboard_watch import ClipboardWatcher

from win_utils import get_foreground_window_info, screen_to_client_normalized


@dataclass
class RecorderConfig:
    channel: str = Channel.WIN.value
    type_flush_delay_ms: int = 700   # flush typed text after idle gap
    ignore_short_clipboard: int = 0  # set >0 to ignore very short clipboard strings


class Recorder:
    """
    Records user actions into Step objects via a callback.

    Improvements:
    - Typing buffer supports BACKSPACE without emitting a separate hotkey step.
    - Ctrl+L "arms" address bar mode; next TYPE chunk is tagged locator_type="address_bar".
    - ENTER/TAB commit: flushes type chunk then emits hotkey.
    """

    def __init__(self, emit_step: Callable[[Step], None], config: Optional[RecorderConfig] = None):
        self.emit_step = emit_step
        self.config = config or RecorderConfig()

        self._is_running = False
        self._is_paused = False

        self._kb_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None

        self._pressed: Set[keyboard.Key | keyboard.KeyCode] = set()

        # typing aggregation
        self._type_buffer: list[str] = []
        self._type_lock = threading.Lock()
        self._last_type_ts = 0.0
        self._flush_thread: Optional[threading.Thread] = None
        self._stop_flush = threading.Event()

        # typing context (address bar)
        self._addr_armed = False
        self._addr_armed_ts = 0.0

        # clipboard watcher
        self._clip = ClipboardWatcher(on_text=self._on_clipboard_text)

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    def start(self) -> None:
        if self._is_running:
            return
        self._is_running = True
        self._is_paused = False

        self._stop_flush.clear()
        self._flush_thread = threading.Thread(target=self._typing_flush_loop, daemon=True)
        self._flush_thread.start()

        self._clip.start()

        self._kb_listener = keyboard.Listener(on_press=self._on_key_press, on_release=self._on_key_release)
        self._mouse_listener = mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll)

        self._kb_listener.start()
        self._mouse_listener.start()

        self._emit_focus_step("Recording started")

    def pause(self) -> None:
        if not self._is_running:
            return
        self._is_paused = True
        self._emit_focus_step("Paused recording")

    def resume(self) -> None:
        if not self._is_running:
            return
        self._is_paused = False
        self._emit_focus_step("Resumed recording")

    def stop(self) -> None:
        if not self._is_running:
            return

        self._emit_type_flush(force=True)

        self._is_running = False
        self._is_paused = False

        self._clip.stop()

        self._stop_flush.set()
        if self._kb_listener:
            self._kb_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()

        self._emit_focus_step("Recording stopped")

    def _emit_focus_step(self, note: str) -> None:
        wi = get_foreground_window_info()
        step = Step(
            channel=self.config.channel,
            action=Action.FOCUS.value,
            window_title=wi.title,
            process_name=wi.process_name,
            pid=wi.pid,
            hwnd=wi.hwnd,
            notes=note,
            locator_type="window",
            locator=f"hwnd={wi.hwnd}",
        )
        self.emit_step(step)

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        if not self._is_running or self._is_paused:
            return

        # flush typing before scroll
        self._emit_type_flush(force=True)

        wi = get_foreground_window_info()

        # Store scroll with relative coords if possible (same approach as clicks)
        nx_ny = screen_to_client_normalized(wi.hwnd, x, y) if wi.hwnd else None
        if nx_ny:
            nx, ny = nx_ny
            locator_type = "scroll_rel"
            locator = f"nx={nx:.6f},ny={ny:.6f}"
        else:
            locator_type = "scroll"
            locator = f"x={x},y={y}"

        step = Step(
            channel=self.config.channel,
            action=Action.SCROLL.value,
            window_title=wi.title,
            process_name=wi.process_name,
            pid=wi.pid,
            hwnd=wi.hwnd,
            locator_type=locator_type,
            locator=locator,
            meta={"dx": int(dx), "dy": int(dy)},
            notes="Mouse wheel scroll",
        )
        self.emit_step(step)

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if not self._is_running or self._is_paused:
            return
        if not pressed:
            return

        # flush typed buffer before click (often indicates end of typing)
        self._emit_type_flush(force=True)

        wi = get_foreground_window_info()

        # Try to store as client-normalized coords (best replay stability)
        nx_ny = screen_to_client_normalized(wi.hwnd, x, y) if wi.hwnd else None

        if nx_ny:
            nx, ny = nx_ny
            step = Step(
                channel=self.config.channel,
                action=Action.CLICK.value,
                window_title=wi.title,
                process_name=wi.process_name,
                pid=wi.pid,
                hwnd=wi.hwnd,
                locator_type="coords_rel",
                locator=f"nx={nx:.6f},ny={ny:.6f},button={button.name}",
                meta={"screen_x": x, "screen_y": y},
            )
        else:
            # Fallback to raw coords if we couldn't resolve client rect
            step = Step(
                channel=self.config.channel,
                action=Action.CLICK.value,
                window_title=wi.title,
                process_name=wi.process_name,
                pid=wi.pid,
                hwnd=wi.hwnd,
                locator_type="coords",
                locator=f"x={x},y={y},button={button.name}",
            )

        self.emit_step(step)


    def _on_key_press(self, key) -> None:
        if not self._is_running:
            return
        self._pressed.add(key)

        if self._is_paused:
            return

        ctrl_down = any(k in self._pressed for k in (keyboard.Key.ctrl, keyboard.Key.ctrl_l, keyboard.Key.ctrl_r))
        shift_down = any(k in self._pressed for k in (keyboard.Key.shift, keyboard.Key.shift_l, keyboard.Key.shift_r))

        char = getattr(key, "char", None)

        # Ctrl + <char> hotkeys
        if ctrl_down and char:
            hk = f"CTRL+{char.upper()}"

            if ctrl_down and char:
                # Handle control-character cases (Ctrl+C becomes '\x03', etc.)
                mapped = self._ctrl_char_to_letter(char)
                if mapped:
                    hk = f"CTRL+{mapped}"
                else:
                    hk = f"CTRL+{char.upper()}"

            # Ctrl+L is special: address bar mode
            if char.lower() == "l":
                self._emit_type_flush(force=True)
                self._emit_hotkey(hk)
                self._arm_address_bar()
                return

            # Ctrl+C / Ctrl+V etc: record as hotkey (clipboard outputs are separate watcher events)
            self._emit_type_flush(force=True)
            self._emit_hotkey(hk)
            return

        # Typing aggregation
        if isinstance(key, keyboard.KeyCode) and char:
            with self._type_lock:
                self._type_buffer.append(char)
                self._last_type_ts = time.time()
            return

        if key == keyboard.Key.space:
            with self._type_lock:
                self._type_buffer.append(" ")
                self._last_type_ts = time.time()
            return

        if key == keyboard.Key.backspace:
            # Keep backspace inside buffer (don’t spam a separate hotkey step)
            with self._type_lock:
                self._type_buffer.append("\b")
                self._last_type_ts = time.time()
            return

        # Commit keys: flush typed chunk then record key
        if key == keyboard.Key.enter:
            self._emit_type_flush(force=True)
            self._emit_hotkey("ENTER")
            # if we just used address bar, disarm after Enter
            self._disarm_address_bar_if_stale(force=True)
            return

        if key == keyboard.Key.tab:
            self._emit_type_flush(force=True)
            self._emit_hotkey("TAB")
            self._disarm_address_bar_if_stale()
            return

        # Optional: allow a future “mark as input” hotkey
        if ctrl_down and shift_down and char and char.lower() == "i":
            self._emit_type_flush(force=True)
            self._emit_hotkey("CTRL+SHIFT+I (mark input)")

    def _ctrl_char_to_letter(self, ch: str) -> Optional[str]:
        """
        pynput may report Ctrl+<letter> as a control character:
          Ctrl+A => '\x01', Ctrl+C => '\x03', Ctrl+L => '\x0c'
        Convert those back to letters.
        """
        if not ch or len(ch) != 1:
            return None
        code = ord(ch)
        if 1 <= code <= 26:
            # 1->A ... 26->Z
            return chr(ord('A') + code - 1)
        return None


    def _on_key_release(self, key) -> None:
        if key in self._pressed:
            self._pressed.remove(key)

    def _emit_hotkey(self, hotkey: str) -> None:
        if not self._is_running or self._is_paused:
            return
        wi = get_foreground_window_info()
        step = Step(
            channel=self.config.channel,
            action=Action.HOTKEY.value,
            window_title=wi.title,
            process_name=wi.process_name,
            pid=wi.pid,
            hwnd=wi.hwnd,
            value=hotkey,
            locator_type="hotkey",
            locator=hotkey,
        )
        self.emit_step(step)

    def _typing_flush_loop(self) -> None:
        while not self._stop_flush.is_set():
            self._emit_type_flush(force=False)
            time.sleep(0.10)

    def _apply_backspaces(self, text: str) -> str:
        out: list[str] = []
        for ch in text:
            if ch == "\b":
                if out:
                    out.pop()
            else:
                out.append(ch)
        return "".join(out)

    def _arm_address_bar(self) -> None:
        self._addr_armed = True
        self._addr_armed_ts = time.time()

    def _disarm_address_bar_if_stale(self, force: bool = False) -> None:
        if not self._addr_armed:
            return
        if force:
            self._addr_armed = False
            return
        # Auto-disarm after a few seconds if user moved on
        if (time.time() - self._addr_armed_ts) > 5.0:
            self._addr_armed = False

    def _emit_type_flush(self, force: bool) -> None:
        if not self._is_running or self._is_paused:
            return

        now = time.time()
        with self._type_lock:
            if not self._type_buffer:
                return
            idle_ms = (now - self._last_type_ts) * 1000.0
            if not force and idle_ms < self.config.type_flush_delay_ms:
                return

            raw = "".join(self._type_buffer)
            self._type_buffer.clear()

        # Apply backspace semantics and keep spaces
        text = self._apply_backspaces(raw)
        # Remove newlines (avoid accidental multi-line artifacts)
        text = text.replace("\r", "").replace("\n", "")
        if text == "":
            return

        wi = get_foreground_window_info()

        locator_type = "type"
        notes = ""

        # If address bar armed recently, tag this typing chunk as address bar input
        if self._addr_armed and (time.time() - self._addr_armed_ts) <= 5.0:
            locator_type = "address_bar"
            notes = "Address bar input (Ctrl+L)"
            # keep armed until Enter, but if user clicks elsewhere it’ll naturally stale out
            self._addr_armed_ts = time.time()

        step = Step(
            channel=self.config.channel,
            action=Action.TYPE.value,
            window_title=wi.title,
            process_name=wi.process_name,
            pid=wi.pid,
            hwnd=wi.hwnd,
            value=text,
            locator_type=locator_type,
            locator="",
            notes=notes,
        )
        self.emit_step(step)

    def _on_clipboard_text(self, text: str) -> None:
        if not self._is_running or self._is_paused:
            return
        if self.config.ignore_short_clipboard and len(text) < self.config.ignore_short_clipboard:
            return

        wi = get_foreground_window_info()
        step = Step(
            channel=self.config.channel,
            action=Action.READ_CLIPBOARD.value,
            window_title=wi.title,
            process_name=wi.process_name,
            pid=wi.pid,
            hwnd=wi.hwnd,
            value=text,
            locator_type="clipboard",
            locator="CF_UNICODETEXT",
        )
        self.emit_step(step)
