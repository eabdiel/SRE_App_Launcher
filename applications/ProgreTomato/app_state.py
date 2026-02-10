from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from models import AutomationProject


@dataclass
class AppState:
    project: AutomationProject = field(default_factory=AutomationProject)
    selected_hwnd: Optional[int] = None
    selected_window_title: str = ""
    selected_process_name: str = ""
    selected_pid: Optional[int] = None

    def set_selected_target(self, hwnd: int, title: str, proc: str, pid: Optional[int]) -> None:
        self.selected_hwnd = hwnd
        self.selected_window_title = title
        self.selected_process_name = proc
        self.selected_pid = pid
