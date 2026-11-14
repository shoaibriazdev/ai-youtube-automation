"""Cost estimation and the spend gate.

Prices below are ESTIMATES for planning only (checked against public price pages in 2026; providers
change them). Override any of them in data/pricing.json, e.g. {"image": {"openai": 0.05}}.
Nothing paid runs until the estimate has been approved for that project (see pipeline.py).
"""
from __future__ import annotations

import json
from typing import Any

from . import config, db

# USD. llm: per million tokens (input, output). image: per image. video: per second of output.
# tts: per 1,000 characters. 0 means free.
PRICING: dict[str, Any] = {
    "llm": {
        "claude-opus-5-5": (4.00, 20.00),
        "claude-sonnet-5-5": (2.00, 10.00),
        "claude-haiku-5-5": (0.10, 0.50),
        "claude-fable-5-1": (10.00, 50.00),
        "offline": (0.0, 0.0),
    },
    "image": {"storyboard": 0.0, "pollinations": 0.0, "openai": 0.06, "stability": 0.03, "replicate": 0.003},
    "video": {"kenburns": 0.0, "runway": 0.05, "luma": 0.08, "replicate": 0.10},
    "tts": {"edge": 0.0, "sapi": 0.0, "silent": 0.0, "elevenlabs": 0.20, "openai": 0.015},
}

FREE_NOTES = {
    "storyboard": "Free, offline. Simple cartoon storyboard frames drawn locally (preview quality).",
    "pollinations": "Free community API, no key needed. Rate-limited, no uptime guarantee.",
    "kenburns": "Free, offline. Animates still images with pan/zoom using FFmpeg.",
    "edge": "Free Microsoft Edge online voices (unofficial endpoint, needs internet).",
    "sapi": "Free, offline system voices (Windows SAPI / espeak on Linux). Robotic quality.",
    "silent": "Free. No audio; timing-only placeholder for testing the pipeline.",
    "offline": "Free, offline template writer. Works without any API key, but quality is far below Claude.",
}

PAID_NOTES = {
    "anthropic": "Anthropic API credits (pay-as-you-go). Not included in Claude Pro/Max subscriptions.",
    "openai": "OpenAI API (pay-as-you-go).",
    "stability": "Stability AI credits.",
    "replicate": "Replicate (pay per prediction).",
    "runway": "Runway API credits (pre-paid).",
    "luma": "Luma API credits.",
    "elevenlabs": "ElevenLabs plan (free tier ~10k characters/month, then paid).",
}


def pricing() -> dict:
    p = json.loads(json.dumps(PRICING))
    f = config.DATA_DIR / "pricing.json"
    if f.exists():
        try:
            over = json.loads(f.read_text(encoding="utf-8"))
            for k, v in over.items():
                if isinstance(v, dict):
                    p.setdefault(k, {}).update(v)
        except (ValueError, OSError):
            pass
    return p


def llm_model() -> str:
    from . import llm
    return llm.active_model()


def estimate(project: dict | None = None, providers: dict | None = None, n_scenes: int | None = None,
             chars: int | None = None, stages: list[str] | None = None) -> dict:
    """Estimate the USD cost of producing one video with the selected providers."""
    providers = providers or db.get_setting("providers")
    opts = db.get_setting("provider_options")
    p = pricing()
    script = (project or {}).get("script") or {}
    scenes = script.get("scenes") or []
    n_scenes = n_scenes or len(scenes) or 6
    if chars is None:
        chars = sum(len(l.get("line", "")) for s in scenes for l in s.get("dialogue", [])) or 900
    stages = stages or ["research", "script", "images", "video", "voice", "thumbnail", "seo"]
    model = llm_model()
    lin, lout = p["llm"].get(model, p["llm"]["claude-opus-5-5"]) if model != "offline" else (0, 0)
    items = []

    def add(stage, provider, units, unit, price, per):
        usd = round(units * price / per, 4)
        items.append({"stage": stage, "provider": provider, "units": units, "unit": unit, "usd": usd,
                      "free": price == 0})

    llm_calls = {"research": (6000, 5000), "script": (5000, 6000), "seo": (3000, 2000), "thumbnail": (1000, 300)}
    for st, (i, o) in llm_calls.items():
        if st in stages:
            usd = round((i * lin + o * lout) / 1e6, 4)
            items.append({"stage": st, "provider": model, "units": i + o, "unit": "tokens (approx)",
                          "usd": usd, "free": usd == 0})
    if "images" in stages:
        ip = providers.get("image", "storyboard")
        add("images", ip, n_scenes + 1, "images", p["image"].get(ip, 0), 1)
    if "video" in stages:
        vp = providers.get("video", "kenburns")
        if vp == "kenburns":
            add("video", vp, n_scenes, "clips", 0, 1)
        else:
            clips = min(n_scenes, int(opts.get("max_ai_video_scenes", 6)))
            secs = clips * int(opts.get("video_clip_seconds", 5))
            add("video", vp, secs, "seconds", p["video"].get(vp, 0), 1)
    if "voice" in stages:
        tp = providers.get("tts", "edge")
        add("voice", tp, chars, "characters", p["tts"].get(tp, 0), 1000)
    total = round(sum(i["usd"] for i in items), 4)
    return {"total_usd": total, "items": items, "free": total == 0, "providers": providers,
            "llm_model": model, "note": "Estimates only. Check each provider's current pricing."}


def budget_status() -> dict:
    c = db.get_setting("costs")
    spent = db.month_spend()
    return {"month_spend_usd": round(spent, 4), "monthly_budget_usd": float(c["monthly_budget_usd"]),
            "remaining_usd": round(float(c["monthly_budget_usd"]) - spent, 4),
            "require_approval_above_usd": float(c["require_approval_above_usd"])}


def needs_approval(project_row: dict, est_total: float) -> bool:
    """True if paid work would start without the user's approval for this amount."""
    threshold = float(db.get_setting("costs")["require_approval_above_usd"])
    if est_total <= threshold:
        return False
    return float(project_row.get("cost_approved") or 0) + 1e-9 < est_total


def over_budget(est_total: float) -> bool:
    b = budget_status()
    return est_total > 0 and est_total > b["remaining_usd"]
