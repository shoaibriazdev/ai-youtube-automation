"""Autopilot: every day at a set time, create a video and upload it - no clicks needed.

Enabling autopilot is your standing approval for the videos it makes. You choose what the upload does:
  private    upload privately (default) - nothing becomes public by itself
  scheduled  upload private + publishAt at the channel's best hour (YouTube makes it public then)
  public     publish immediately
Spending is capped per run (`max_cost_usd`, default $0 = free providers only). If a run would cost more,
it is skipped and logged instead of spending.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from . import db, jobs, pipeline, projects

DEFAULT = {
    "enabled": False,
    "run_at": "10:00",                 # local time in `timezone`
    "timezone": "Asia/Karachi",
    "format": "short",
    "upload": True,
    "privacy_mode": "private",         # private | scheduled | public
    "public_confirmed": False,         # must be True for scheduled/public (set in the dashboard)
    "max_cost_usd": 0.0,
    "last_run_date": None,
    "last_result": None,
}
_started = False
_lock = threading.Lock()


def settings() -> dict:
    stored = db.get_setting("autopilot") or {}
    return {**DEFAULT, **(stored if isinstance(stored, dict) else {})}


def save(values: dict) -> dict:
    cfg = settings()
    allowed = {"enabled", "run_at", "timezone", "format", "upload", "privacy_mode", "public_confirmed", "max_cost_usd"}
    cfg.update({k: v for k, v in values.items() if k in allowed})
    if cfg["privacy_mode"] not in ("private", "scheduled", "public"):
        raise ValueError("privacy_mode must be private, scheduled or public")
    if cfg["format"] not in ("short", "long"):
        raise ValueError("format must be short or long")
    try:
        datetime.strptime(cfg["run_at"], "%H:%M")
        ZoneInfo(cfg["timezone"])
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"invalid time or timezone: {e}") from e
    if cfg["privacy_mode"] != "private" and not cfg["public_confirmed"]:
        raise ValueError("Scheduled/public autopilot uploads need public_confirmed=true "
                         "(you agree videos go public without review).")
    cfg["max_cost_usd"] = max(0.0, float(cfg["max_cost_usd"]))
    db.set_setting("autopilot", cfg)
    return status()


def due(cfg: dict, now_utc: datetime | None = None) -> bool:
    if not cfg.get("enabled"):
        return False
    tz = ZoneInfo(cfg["timezone"])
    now = (now_utc or datetime.now(tz=ZoneInfo("UTC"))).astimezone(tz)
    h, m = map(int, cfg["run_at"].split(":"))
    return now.strftime("%Y-%m-%d") != cfg.get("last_run_date") and (now.hour, now.minute) >= (h, m)


def next_run(cfg: dict) -> str | None:
    if not cfg.get("enabled"):
        return None
    tz = ZoneInfo(cfg["timezone"])
    now = datetime.now(tz)
    h, m = map(int, cfg["run_at"].split(":"))
    t = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if t <= now or cfg.get("last_run_date") == now.strftime("%Y-%m-%d"):
        t += timedelta(days=1)
    return t.isoformat()


def publish_time() -> str:
    """Next occurrence of the channel's best publish hour (in the channel timezone), at least 1 hour away."""
    ch = db.get_setting("channel")
    tz = ZoneInfo(ch.get("upload_timezone") or "America/New_York")
    now = datetime.now(tz)
    t = now.replace(hour=int(ch.get("best_publish_hour", 17)), minute=0, second=0, microsecond=0)
    if t < now + timedelta(hours=1):
        t += timedelta(days=1)
    return t.isoformat()


def run_once(progress=None, cancel=None, force_date: bool = True) -> dict:
    """Create today's video and (optionally) upload it according to the autopilot settings."""
    from . import youtube
    cfg = settings()
    say = progress or (lambda *_: None)
    if force_date:
        cfg["last_run_date"] = datetime.now(ZoneInfo(cfg["timezone"])).strftime("%Y-%m-%d")
        db.set_setting("autopilot", cfg)
    p = projects.create("Autopilot video", cfg["format"])
    pid = p["id"]
    db.log_event(pid, "autopilot", "Autopilot started today's video")
    pipeline.approve_cost(pid, float(cfg["max_cost_usd"]))
    res = pipeline.run(pid, pipeline.STAGES, progress=lambda f, m: say(f * 0.85, m), cancel=cancel)
    result = {"project": pid, "created": bool(res.get("ok"))}
    if res.get("needs_approval"):
        result.update(ok=False, error=f"Skipped: estimated ${res['estimate']['total_usd']:.2f} is above the autopilot "
                                      f"limit ${cfg['max_cost_usd']:.2f}. Raise the limit or use free providers.")
    elif not res.get("ok"):
        result.update(ok=False, error="Video creation failed - see Production History.")
    else:
        projects.update_row(pid, approved=1, status="approved")
        db.log_event(pid, "review", "Approved automatically by Autopilot (your standing approval)")
        result["ok"] = True
        if cfg["upload"]:
            if not youtube.status().get("connected"):
                result["upload"] = "skipped: YouTube not connected"
                db.log_event(pid, "autopilot", "Upload skipped: connect YouTube in the Upload Manager", "warning")
            else:
                mode = cfg["privacy_mode"]
                confirmed = bool(cfg["public_confirmed"])
                try:
                    say(0.9, "Uploading to YouTube")
                    if mode == "scheduled" and confirmed:
                        yt = youtube.upload(pid, "private", publish_time(), confirm_public=True)
                    elif mode == "public" and confirmed:
                        yt = youtube.upload(pid, "public", confirm_public=True)
                    else:
                        yt = youtube.upload(pid, "private")
                    result["upload"] = yt
                except Exception as e:  # noqa: BLE001
                    result.update(ok=False, upload=f"failed: {e}")
    cfg = settings()
    cfg["last_result"] = {"time": time.time(), **{k: (v if isinstance(v, (str, bool, int, float, type(None))) else str(v))
                                                  for k, v in result.items()}}
    db.set_setting("autopilot", cfg)
    db.log_event(pid, "autopilot", f"Autopilot finished: {result.get('error') or result.get('upload') or 'video ready'}",
                 "info" if result.get("ok") else "warning")
    say(1.0, "Autopilot done")
    return result


def status() -> dict:
    cfg = settings()
    return {**cfg, "next_run": next_run(cfg), "scheduler_running": _started}


def _loop() -> None:
    while True:
        try:
            cfg = settings()
            if due(cfg):
                with _lock:
                    cfg = settings()
                    if due(cfg):
                        cfg["last_run_date"] = datetime.now(ZoneInfo(cfg["timezone"])).strftime("%Y-%m-%d")
                        db.set_setting("autopilot", cfg)
                        jobs.submit("autopilot", lambda progress, cancel: run_once(progress, cancel, force_date=False))
        except Exception as e:  # noqa: BLE001
            db.log_event(None, "autopilot", f"Scheduler error: {e}", "error")
        time.sleep(30)


def start_scheduler() -> None:
    global _started
    if _started:
        return
    _started = True
    threading.Thread(target=_loop, daemon=True, name="ytauto-autopilot").start()
