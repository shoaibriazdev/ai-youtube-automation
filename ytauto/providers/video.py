"""STEP 4b - AI video clip providers (image-to-video / text-to-video).

kenburns   free, offline  no API call: the editor animates each still with pan/zoom (FFmpeg)
runway     paid           Runway API image_to_video (gen4_turbo)          RUNWAY_API_KEY
luma       paid           Luma Dream Machine generations (ray-2)          LUMA_API_KEY
replicate  paid           any Replicate video model (default minimax/video-01) REPLICATE_API_TOKEN

Each returns the path of a downloaded MP4 clip, or None for kenburns.
"""
from __future__ import annotations

import base64
from pathlib import Path

from .. import db
from .base import ProviderError, download, poll, request, require

PROVIDERS = ["kenburns", "runway", "luma", "replicate"]


def _data_uri(image: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(Path(image).read_bytes()).decode()


def generate(provider: str, prompt: str, image: Path | None, out: Path, aspect: str = "16:9",
             seconds: int = 5) -> Path | None:
    if provider == "kenburns":
        return None
    fn = {"runway": _runway, "luma": _luma, "replicate": _replicate}.get(provider)
    if not fn:
        raise ProviderError(f"unknown video provider '{provider}'. Choose one of {PROVIDERS}")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    url = fn(prompt, image, aspect, seconds)
    download(url, out, timeout=600)
    if out.stat().st_size < 1000:
        raise ProviderError(f"{provider} returned an empty video file")
    return out


def _runway(prompt, image, aspect, seconds):
    key = require("RUNWAY_API_KEY", "Runway")
    if not image:
        raise ProviderError("Runway image_to_video needs a scene image; generate images first.")
    model = db.get_setting("provider_options").get("runway_model", "gen4_turbo")
    headers = {"Authorization": f"Bearer {key}", "X-Runway-Version": "2024-11-06"}
    ratio = "720:1280" if aspect == "9:16" else "1280:720"
    r = request("POST", "https://api.dev.runwayml.com/v1/image_to_video", headers=headers, timeout=120,
                json={"model": model, "promptImage": _data_uri(image), "promptText": prompt[:1000],
                      "ratio": ratio, "duration": 10 if seconds > 7 else 5})
    task_id = r.json()["id"]
    data = poll(lambda: request("GET", f"https://api.dev.runwayml.com/v1/tasks/{task_id}", headers=headers).json(),
                lambda d: d.get("status") == "SUCCEEDED",
                lambda d: (f"Runway task failed: {d.get('failure') or d.get('failureCode')}"
                           if d.get("status") in ("FAILED", "CANCELLED") else None), timeout=900, interval=6)
    return data["output"][0]


def _luma(prompt, image, aspect, seconds):
    key = require("LUMA_API_KEY", "Luma")
    model = db.get_setting("provider_options").get("luma_model", "ray-2")
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    body = {"prompt": prompt[:2000], "model": model, "aspect_ratio": aspect,
            "duration": "9s" if seconds > 7 else "5s", "resolution": "720p", "loop": False}
    r = request("POST", "https://api.lumalabs.ai/dream-machine/v1/generations", headers=headers, json=body, timeout=120)
    gid = r.json()["id"]
    data = poll(lambda: request("GET", f"https://api.lumalabs.ai/dream-machine/v1/generations/{gid}", headers=headers).json(),
                lambda d: d.get("state") == "completed",
                lambda d: (f"Luma generation failed: {d.get('failure_reason')}" if d.get("state") == "failed" else None),
                timeout=900, interval=6)
    return data["assets"]["video"]


def _replicate(prompt, image, aspect, seconds):
    token = require("REPLICATE_API_TOKEN", "Replicate")
    opts = db.get_setting("provider_options")
    model = opts.get("replicate_video_model", "minimax/video-01")
    field = opts.get("replicate_video_image_field", "first_frame_image")
    headers = {"Authorization": f"Bearer {token}", "Prefer": "wait=60"}
    inp = {"prompt": prompt[:2000]}
    if image and field:
        inp[field] = _data_uri(image)
    r = request("POST", f"https://api.replicate.com/v1/models/{model}/predictions", headers=headers, json={"input": inp},
                timeout=180)
    pred = r.json()
    if pred.get("status") != "succeeded":
        pred = poll(lambda: request("GET", pred["urls"]["get"], headers=headers).json(),
                    lambda d: d.get("status") == "succeeded",
                    lambda d: (f"Replicate failed: {d.get('error')}" if d.get("status") in ("failed", "canceled") else None),
                    timeout=1200, interval=8)
    out = pred.get("output")
    return out[0] if isinstance(out, list) else out
