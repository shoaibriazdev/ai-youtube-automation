"""Background job queue for the dashboard: one worker thread (renders are CPU-heavy), progress in SQLite."""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from typing import Callable

from . import db

_q: "queue.Queue[tuple[str, Callable]]" = queue.Queue()
_cancel: set[str] = set()
_worker: threading.Thread | None = None
_lock = threading.Lock()


def _update(jid: str, **f) -> None:
    f["updated"] = time.time()
    cols = ", ".join(f"{k}=?" for k in f)
    db.execute(f"UPDATE jobs SET {cols} WHERE id=?", (*f.values(), jid))


def _loop() -> None:
    while True:
        jid, fn = _q.get()
        if jid in _cancel:
            _update(jid, status="cancelled", message="Cancelled before start")
            continue
        _update(jid, status="running", progress=0.0, message="Starting")

        def progress(frac: float, msg: str = "", _jid=jid):
            _update(_jid, progress=round(max(0.0, min(1.0, frac)), 3), message=msg[:500])

        try:
            result = fn(progress, lambda _jid=jid: _jid in _cancel)
            ok = not (isinstance(result, dict) and result.get("ok") is False)
            status = "done" if ok else ("needs_approval" if isinstance(result, dict) and result.get("needs_approval")
                                        else "cancelled" if isinstance(result, dict) and result.get("cancelled") else "failed")
            _update(jid, status=status, progress=1.0 if ok else 0.0, message="Finished" if ok else status,
                    params=json.dumps({"result": result}, default=str)[:20000],
                    error=None if ok else (result.get("error") if isinstance(result, dict) else None))
        except Exception as e:  # noqa: BLE001
            _update(jid, status="failed", error=f"{type(e).__name__}: {e}"[:2000], message="Failed")


def submit(kind: str, fn: Callable, project_id: str | None = None) -> str:
    """fn(progress, cancelled) -> result. Returns job id."""
    global _worker
    jid = uuid.uuid4().hex[:12]
    now = time.time()
    db.execute("INSERT INTO jobs(id,project_id,kind,status,progress,message,created,updated) VALUES(?,?,?,?,?,?,?,?)",
               (jid, project_id, kind, "queued", 0.0, "Queued", now, now))
    with _lock:
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_loop, daemon=True, name="ytauto-jobs")
            _worker.start()
    _q.put((jid, fn))
    return jid


def cancel(jid: str) -> None:
    _cancel.add(jid)


def get(jid: str) -> dict:
    rows = db.query("SELECT * FROM jobs WHERE id=?", (jid,))
    if not rows:
        raise KeyError(jid)
    r = rows[0]
    if r.get("params"):
        try:
            r["result"] = json.loads(r["params"]).get("result")
        except ValueError:
            pass
    return r


def recent(limit: int = 50, project_id: str | None = None) -> list[dict]:
    if project_id:
        return db.query("SELECT id,project_id,kind,status,progress,message,error,created,updated FROM jobs "
                        "WHERE project_id=? ORDER BY created DESC LIMIT ?", (project_id, limit))
    return db.query("SELECT id,project_id,kind,status,progress,message,error,created,updated FROM jobs "
                    "ORDER BY created DESC LIMIT ?", (limit,))


def mark_stale() -> None:
    """Jobs left 'running' by a previous server process can never finish."""
    db.execute("UPDATE jobs SET status='failed', error='Server restarted while running' WHERE status IN ('running','queued')")
