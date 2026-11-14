"""Video projects: one folder per video under projects/<id>/ with a project.json manifest."""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from . import config, db

_LOCK = threading.RLock()

STATUSES = ["draft", "running", "awaiting_cost_approval", "ready_for_review", "approved",
            "uploading", "uploaded", "scheduled", "failed"]


def slugify(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "video").lower()).strip("-")
    return (s[:n].strip("-")) or "video"


def project_dir(pid: str) -> Path:
    return config.PROJECTS_DIR / pid


def create(title: str = "Untitled video", fmt: str | None = None, idea: dict | None = None) -> dict:
    fmt = fmt or db.get_setting("channel")["default_format"]
    if fmt not in ("short", "long"):
        raise ValueError("format must be 'short' (9:16) or 'long' (16:9)")
    pid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    d = project_dir(pid)
    for sub in ("images", "video", "audio", "render", "thumbnail"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    now = time.time()
    data = {"id": pid, "title": title, "format": fmt, "created": now, "idea": idea or {},
            "script": None, "assets": {"images": {}, "clips": {}, "voice": {}},
            "render": {}, "thumbnail": {}, "seo": {}, "stages": {}, "estimate": None}
    save(data)
    db.execute("INSERT INTO projects(id,title,status,stage,format,created,updated) VALUES(?,?,?,?,?,?,?)",
               (pid, title, "draft", "created", fmt, now, now))
    db.log_event(pid, "project", f"Created project '{title}' ({fmt})")
    return data


def load(pid: str) -> dict:
    f = project_dir(pid) / "project.json"
    if not f.exists():
        raise KeyError(f"Project not found: {pid}")
    with _LOCK:
        return json.loads(f.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    d = project_dir(data["id"])
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "project.json.tmp"
    with _LOCK:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(d / "project.json")


def update_row(pid: str, **fields: Any) -> None:
    if not fields:
        return
    fields["updated"] = time.time()
    cols = ", ".join(f"{k}=?" for k in fields)
    db.execute(f"UPDATE projects SET {cols} WHERE id=?", (*fields.values(), pid))


def row(pid: str) -> dict:
    rows = db.query("SELECT * FROM projects WHERE id=?", (pid,))
    if not rows:
        raise KeyError(f"Project not found: {pid}")
    return rows[0]


def list_all(limit: int = 200) -> list[dict]:
    return db.query("SELECT * FROM projects ORDER BY created DESC LIMIT ?", (limit,))


def delete(pid: str) -> None:
    d = project_dir(pid)
    if d.exists():
        shutil.rmtree(d)
    db.execute("DELETE FROM projects WHERE id=?", (pid,))


def rel(pid: str, path: Path | str) -> str:
    """Path relative to the project folder (stored in project.json so folders can move)."""
    return str(Path(path).resolve().relative_to(project_dir(pid).resolve())).replace("\\", "/")


def abspath(pid: str, relpath: str) -> Path:
    return project_dir(pid) / relpath
