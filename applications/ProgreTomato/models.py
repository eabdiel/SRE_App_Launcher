from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, Optional, List
import time
import uuid


class Channel(str, Enum):
    WEB = "web"
    SAP = "sap"
    WIN = "win"


class Action(str, Enum):
    CLICK = "click"
    TYPE = "type"
    HOTKEY = "hotkey"
    WAIT = "wait"
    WAIT_UNTIL = "wait_until"
    FOCUS = "focus"
    READ_CLIPBOARD = "read_clipboard"
    SCROLL = "scroll"

@dataclass
class Step:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    ts: float = field(default_factory=lambda: time.time())
    channel: str = Channel.WIN.value
    action: str = Action.CLICK.value

    # window/app context
    window_title: str = ""
    process_name: str = ""
    pid: Optional[int] = None
    hwnd: Optional[int] = None

    # targeting
    locator_type: str = ""     # e.g., "coords", "uia", "sap", "dom"
    locator: str = ""          # e.g., "x=123,y=456" or UIA selector

    # payload / IO mapping
    value: str = ""            # typed text, key, clipboard text (optional)
    input_ref: str = ""        # e.g., {{input:username}}
    output_ref: str = ""       # e.g., {{output:invoice_id}}

    # execution controls
    wait_ms: int = 0
    notes: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "Step":
        return Step(**d)


@dataclass
class DataItem:
    key: str
    value: str = ""
    type: str = "text"          # text/secret/number/date
    prompt_on_run: bool = False
    default_value: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "DataItem":
        return DataItem(**d)


@dataclass
class AutomationProject:
    name: str = "ProgreTomato"
    created_ts: float = field(default_factory=lambda: time.time())
    updated_ts: float = field(default_factory=lambda: time.time())
    steps: List[Step] = field(default_factory=list)
    data: List[DataItem] = field(default_factory=list)

    def touch(self) -> None:
        self.updated_ts = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "created_ts": self.created_ts,
            "updated_ts": self.updated_ts,
            "steps": [s.to_dict() for s in self.steps],
            "data": [x.to_dict() for x in self.data],
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> "AutomationProject":
        proj = AutomationProject(
            name=d.get("name", "Imported Automation"),
            created_ts=d.get("created_ts", time.time()),
            updated_ts=d.get("updated_ts", time.time()),
        )
        proj.steps = [Step.from_dict(s) for s in d.get("steps", [])]
        proj.data = [DataItem.from_dict(x) for x in d.get("data", [])]
        return proj
