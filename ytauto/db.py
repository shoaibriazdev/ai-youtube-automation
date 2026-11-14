"""SQLite storage (stdlib sqlite3, one file in data/ytauto.db).

Tables: settings, characters, projects, events, jobs, uploads, cost_log, ideas.
Project detail (script, assets, SEO...) lives in projects/<id>/project.json; the DB is the index.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any

from . import config

_LOCK = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS characters (id TEXT PRIMARY KEY, data TEXT NOT NULL, updated REAL);
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, title TEXT, status TEXT, stage TEXT, format TEXT,
  created REAL, updated REAL, error TEXT, approved INTEGER DEFAULT 0,
  cost_approved REAL DEFAULT 0, est_cost REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, ts REAL, level TEXT, stage TEXT, message TEXT);
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY, project_id TEXT, kind TEXT, status TEXT, progress REAL,
  message TEXT, error TEXT, created REAL, updated REAL, params TEXT);
CREATE TABLE IF NOT EXISTS uploads (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, video_id TEXT, privacy TEXT,
  publish_at TEXT, status TEXT, error TEXT, ts REAL, title TEXT, url TEXT, thumbnail_status TEXT);
CREATE TABLE IF NOT EXISTS cost_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT, ts REAL, provider TEXT, kind TEXT,
  units REAL, usd REAL, note TEXT);
CREATE TABLE IF NOT EXISTS ideas (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, batch TEXT, data TEXT, used INTEGER DEFAULT 0);
"""

DEFAULT_SETTINGS: dict[str, Any] = {
    "channel": {
        "name": "My AI Comedy Channel",
        "niche": "Funny AI animated comedy",
        "audience": "USA and other English-speaking countries, family-friendly, ages 13+",
        "themes": ["funny talking cats and dogs", "crazy animal conversations", "funny office situations",
                   "relatable everyday comedy", "unexpected plot twists", "original animated characters",
                   "funny short stories", "family-friendly comedy"],
        "tone": "Warm, silly, fast-paced, clean jokes, a twist ending every time",
        "default_format": "short",
        "made_for_kids": False,
        "contains_synthetic_media": True,
        "default_privacy": "private",
        "category_id": "23",
        "default_language": "en",
        "upload_timezone": "America/New_York",
        "best_publish_hour": 17,
    },
    "providers": {
        "llm": "auto",          # auto | anthropic | offline
        "image": "storyboard",  # storyboard | pollinations | openai | stability | replicate
        "video": "kenburns",    # kenburns | runway | luma | replicate
        "tts": "edge",          # edge | elevenlabs | openai | sapi | silent
    },
    "provider_options": {
        "openai_image_model": "gpt-image-1",
        "openai_image_quality": "medium",
        "replicate_image_model": "black-forest-labs/flux-schnell",
        "replicate_video_model": "minimax/video-01",
        "replicate_video_image_field": "first_frame_image",
        "runway_model": "gen4_turbo",
        "luma_model": "ray-2",
        "elevenlabs_model": "eleven_multilingual_v2",
        "openai_tts_model": "gpt-4o-mini-tts",
        "pollinations_model": "flux",
        "video_clip_seconds": 5,
        "max_ai_video_scenes": 6,
    },
    "style": {
        "art_style": ("original stylized 3D cartoon animation, bright saturated colors, soft studio lighting, "
                      "big expressive eyes, clean shapes, family-friendly, high detail"),
        "negative": "text, watermark, logo, signature, gore, scary, photorealistic human faces",
    },
    "render": {
        "quality": "hd",            # draft (720p/24fps) | hd (1080p/30fps)
        "transition": "fade",       # fade | slideleft | circleopen | wipeleft | none
        "transition_seconds": 0.4,
        "music_volume": 0.16,
        "sfx_volume": 0.7,
        "subtitles": True,
        "subtitle_words_per_caption": 4,
        "scene_padding_seconds": 0.6,
        "min_scene_seconds": 2.2,
    },
    "costs": {"require_approval_above_usd": 0.0, "monthly_budget_usd": 10.0},
}


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


_conn: sqlite3.Connection | None = None


def conn() -> sqlite3.Connection:
    global _conn
    with _LOCK:
        if _conn is None:
            _conn = _connect()
            _conn.executescript(SCHEMA)
            _conn.commit()
        return _conn


def reset_connection() -> None:
    """Used by tests that point YTAUTO_DATA_DIR somewhere else."""
    global _conn
    with _LOCK:
        if _conn is not None:
            _conn.close()
        _conn = None


@contextmanager
def tx():
    with _LOCK:
        c = conn()
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise


def query(sql: str, args: tuple = ()) -> list[dict]:
    with _LOCK:
        return [dict(r) for r in conn().execute(sql, args).fetchall()]


def execute(sql: str, args: tuple = ()) -> int:
    with tx() as c:
        cur = c.execute(sql, args)
        return cur.lastrowid


# ---------- settings ----------
def _merge(default: Any, stored: Any) -> Any:
    if isinstance(default, dict) and isinstance(stored, dict):
        out = dict(default)
        for k, v in stored.items():
            out[k] = _merge(default.get(k), v) if k in default else v
        return out
    return default if stored is None else stored


def get_setting(key: str) -> Any:
    rows = query("SELECT value FROM settings WHERE key=?", (key,))
    stored = json.loads(rows[0]["value"]) if rows else None
    return _merge(DEFAULT_SETTINGS.get(key), stored)


def set_setting(key: str, value: Any) -> Any:
    merged = _merge(DEFAULT_SETTINGS.get(key), value) if key in DEFAULT_SETTINGS else value
    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(merged)))
    return merged


def all_settings() -> dict:
    return {k: get_setting(k) for k in DEFAULT_SETTINGS}


# ---------- events / costs ----------
def log_event(project_id: str | None, stage: str, message: str, level: str = "info") -> None:
    execute("INSERT INTO events(project_id,ts,level,stage,message) VALUES(?,?,?,?,?)",
            (project_id, time.time(), level, stage, message[:4000]))


def events(project_id: str | None = None, limit: int = 200) -> list[dict]:
    if project_id:
        return query("SELECT * FROM events WHERE project_id=? ORDER BY id DESC LIMIT ?", (project_id, limit))
    return query("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))


def log_cost(project_id: str | None, provider: str, kind: str, units: float, usd: float, note: str = "") -> None:
    execute("INSERT INTO cost_log(project_id,ts,provider,kind,units,usd,note) VALUES(?,?,?,?,?,?,?)",
            (project_id, time.time(), provider, kind, units, usd, note))


def month_spend() -> float:
    start = time.time() - 31 * 86400
    rows = query("SELECT COALESCE(SUM(usd),0) AS s FROM cost_log WHERE ts>=?", (start,))
    return float(rows[0]["s"])
