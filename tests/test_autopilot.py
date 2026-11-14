"""Autopilot: schedule logic, safety rules, and a real unattended run."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from ytauto import autopilot, db, projects


def test_due_logic():
    cfg = {**autopilot.DEFAULT, "enabled": True, "run_at": "10:00", "timezone": "Asia/Karachi", "last_run_date": None}
    before = datetime(2026, 11, 8, 4, 59, tzinfo=ZoneInfo("UTC"))   # 09:59 Karachi
    after = datetime(2026, 11, 8, 5, 1, tzinfo=ZoneInfo("UTC"))     # 10:01 Karachi
    assert not autopilot.due(cfg, before) and autopilot.due(cfg, after)
    assert not autopilot.due({**cfg, "last_run_date": "2026-11-08"}, after)   # once per day
    assert not autopilot.due({**cfg, "enabled": False}, after)


def test_public_needs_explicit_confirmation():
    with pytest.raises(ValueError, match="public_confirmed"):
        autopilot.save({"privacy_mode": "public", "public_confirmed": False})
    with pytest.raises(ValueError):
        autopilot.save({"run_at": "25:99"})
    st = autopilot.save({"enabled": True, "run_at": "09:30", "privacy_mode": "private"})
    assert st["enabled"] and st["next_run"]
    autopilot.save({"enabled": False})


def test_unattended_run_free(free_providers):
    autopilot.save({"enabled": False, "max_cost_usd": 0, "upload": True, "privacy_mode": "private"})
    r = autopilot.run_once()
    assert r["ok"] and r["created"]
    assert r["upload"].startswith("skipped")          # YouTube not connected in tests -> honest skip
    row = projects.row(r["project"])
    assert row["approved"] == 1
    assert projects.load(r["project"])["render"]["outputs"]
    assert autopilot.settings()["last_result"]["ok"] is True


def test_paid_run_over_limit_is_skipped(free_providers):
    db.set_setting("providers", {"llm": "offline", "image": "openai", "video": "kenburns", "tts": "silent"})
    autopilot.save({"max_cost_usd": 0})
    r = autopilot.run_once()
    assert r["ok"] is False and "limit" in r["error"]
    assert not projects.load(r["project"])["assets"]["images"]   # nothing paid was attempted
