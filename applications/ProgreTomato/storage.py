from __future__ import annotations

import json
from pathlib import Path
from models import AutomationProject


def save_project_json(project: AutomationProject, path: str) -> None:
    p = Path(path)
    p.write_text(json.dumps(project.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")


def load_project_json(path: str) -> AutomationProject:
    p = Path(path)
    data = json.loads(p.read_text(encoding="utf-8"))
    return AutomationProject.from_dict(data)
