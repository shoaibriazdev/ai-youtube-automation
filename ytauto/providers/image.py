"""STEP 4a - Image generation providers.

storyboard   free, offline   cartoon storyboard frames drawn locally with Pillow (preview quality)
pollinations free, no key    https://image.pollinations.ai (community service, rate-limited)
openai       paid            OpenAI Images API (gpt-image-1)            OPENAI_API_KEY
stability    paid            Stability AI Stable Image Core             STABILITY_API_KEY
replicate    paid            Replicate (default black-forest-labs/flux-schnell)  REPLICATE_API_TOKEN
"""
from __future__ import annotations

import base64
import io
import math
import random
import urllib.parse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from .. import db, fonts
from .base import ProviderError, poll, request, require

PROVIDERS = ["storyboard", "pollinations", "openai", "stability", "replicate"]


def size_for(aspect: str, provider: str) -> tuple[int, int]:
    vertical = aspect == "9:16"
    if provider == "openai":
        return (1024, 1536) if vertical else (1536, 1024)
    if provider == "pollinations":
        return (768, 1344) if vertical else (1344, 768)
    return (1080, 1920) if vertical else (1920, 1080)


def generate(provider: str, prompt: str, out: Path, aspect: str = "16:9", seed: int = 0,
             context: dict | None = None) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if provider == "storyboard":
        return storyboard(out, aspect, context or {}, seed)
    fn = {"pollinations": _pollinations, "openai": _openai, "stability": _stability,
          "replicate": _replicate}.get(provider)
    if not fn:
        raise ProviderError(f"unknown image provider '{provider}'. Choose one of {PROVIDERS}")
    data = fn(prompt, aspect, seed)
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as e:
        raise ProviderError(f"{provider} did not return a valid image") from e
    img.save(out, "PNG")
    return out


# ---------------- remote providers ----------------
def _pollinations(prompt, aspect, seed):
    w, h = size_for(aspect, "pollinations")
    opts = db.get_setting("provider_options")
    q = {"width": w, "height": h, "seed": seed, "model": opts.get("pollinations_model", "flux"),
         "nologo": "true", "private": "true", "enhance": "false"}
    from .. import config
    headers = {}
    if config.env("POLLINATIONS_TOKEN"):
        headers["Authorization"] = f"Bearer {config.env('POLLINATIONS_TOKEN')}"
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt[:1500]) + "?" + urllib.parse.urlencode(q)
    r = request("GET", url, timeout=180, headers=headers, retries=3)
    if not r.headers.get("content-type", "").startswith("image/"):
        raise ProviderError(f"Pollinations returned {r.headers.get('content-type')}: {r.text[:200]}")
    return r.content


def _openai(prompt, aspect, seed):
    key = require("OPENAI_API_KEY", "OpenAI Images")
    opts = db.get_setting("provider_options")
    w, h = size_for(aspect, "openai")
    r = request("POST", "https://api.openai.com/v1/images/generations", timeout=300,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": opts.get("openai_image_model", "gpt-image-1"), "prompt": prompt[:4000],
                      "size": f"{w}x{h}", "quality": opts.get("openai_image_quality", "medium"), "n": 1})
    item = r.json()["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    return request("GET", item["url"]).content


def _stability(prompt, aspect, seed):
    key = require("STABILITY_API_KEY", "Stability AI")
    neg = db.get_setting("style").get("negative", "")
    r = request("POST", "https://api.stability.ai/v2beta/stable-image/generate/core", timeout=300,
                headers={"Authorization": f"Bearer {key}", "Accept": "image/*"},
                files={"none": ("", "")},
                data={"prompt": prompt[:10000], "negative_prompt": neg, "aspect_ratio": aspect,
                      "seed": seed % 4294967294, "output_format": "png"})
    return r.content


def _replicate(prompt, aspect, seed):
    token = require("REPLICATE_API_TOKEN", "Replicate")
    model = db.get_setting("provider_options").get("replicate_image_model", "black-forest-labs/flux-schnell")
    headers = {"Authorization": f"Bearer {token}", "Prefer": "wait=60"}
    r = request("POST", f"https://api.replicate.com/v1/models/{model}/predictions", headers=headers, timeout=180,
                json={"input": {"prompt": prompt, "aspect_ratio": aspect, "seed": seed, "output_format": "png",
                                "num_outputs": 1}})
    pred = r.json()
    if pred.get("status") not in ("succeeded",):
        pred = poll(lambda: request("GET", pred["urls"]["get"], headers=headers).json(),
                    lambda d: d.get("status") == "succeeded",
                    lambda d: (f"Replicate failed: {d.get('error')}" if d.get("status") in ("failed", "canceled") else None),
                    timeout=600, interval=3)
    out = pred.get("output")
    url = out[0] if isinstance(out, list) else out
    return request("GET", url).content


# ---------------- storyboard (offline) ----------------
SETTING_COLORS = {
    "kitchen": ("#FFE8B8", "#F6C27A", "#B97A45"), "office": ("#DDE7F2", "#AFC3D9", "#6D7F95"),
    "living room": ("#FCE1E4", "#E8B4BC", "#9B6B6B"), "backyard": ("#BDE8FF", "#8FD16A", "#4E8F3A"),
    "park": ("#BDE8FF", "#9AD66E", "#4E8F3A"), "vet clinic": ("#E6F7F4", "#B5E3DA", "#6AA79C"),
    "bedroom": ("#E9E1FF", "#C2B5F0", "#7B6CB3"), "grocery store": ("#FFF6D6", "#F3D27A", "#B58E2E"),
    "road trip": ("#FFC48C", "#F78C6B", "#5B4B8A"), "bathroom": ("#DFF6FF", "#A7DDF2", "#5A9BB5"),
}


def _hex(c: str) -> tuple:
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _background(img: Image.Image, setting: str, r: random.Random):
    W, H = img.size
    key = next((k for k in SETTING_COLORS if k in (setting or "").lower()), None)
    sky, floor, accent = (_hex(x) for x in SETTING_COLORS.get(key, ("#EAF4FF", "#CFE3C1", "#7A9C6A")))
    d = ImageDraw.Draw(img)
    horizon = int(H * 0.62)
    for y in range(horizon):
        t = y / horizon
        d.line([(0, y), (W, y)], fill=tuple(int(sky[i] * (1 - 0.18 * t)) for i in range(3)))
    for y in range(horizon, H):
        t = (y - horizon) / (H - horizon)
        d.line([(0, y), (W, y)], fill=_shade(floor, 1 - 0.25 * t))
    # simple props so frames are not empty: windows/frames/shelves in the setting accent colour
    for _ in range(3):
        w = r.randint(W // 10, W // 5)
        h = r.randint(H // 10, H // 5)
        x = r.randint(0, W - w)
        y = r.randint(int(H * 0.08), max(int(H * 0.09), horizon - h - 20))
        d.rounded_rectangle([x, y, x + w, y + h], radius=18, fill=_shade(sky, 0.9), outline=accent, width=max(4, W // 300))
    d.rectangle([0, horizon - 6, W, horizon + 6], fill=_shade(floor, 0.8))


def _eyes(d, cx, cy, s, emotion, color=(30, 30, 30)):
    e = (emotion or "").lower()
    ex = s * 0.32
    for sx in (-1, 1):
        x = cx + sx * ex
        if e in ("tired", "deadpan", "bored", "sleepy"):
            d.line([(x - s * .14, cy), (x + s * .14, cy)], fill=color, width=max(3, int(s * .05)))
        else:
            rr = s * (0.17 if e in ("shocked", "panicked", "surprised", "excited") else 0.13)
            d.ellipse([x - rr, cy - rr, x + rr, cy + rr], fill="white", outline=color, width=max(2, int(s * .02)))
            pr = rr * 0.55
            d.ellipse([x - pr, cy - pr, x + pr, cy + pr], fill=color)
            d.ellipse([x - pr * .3 + pr * .3, cy - pr * .6, x + pr * .3 + pr * .3, cy], fill="white")
        if e in ("angry", "determined", "suspicious", "exasperated"):
            d.line([(x - s * .18, cy - s * .25 - sx * s * .06), (x + s * .18, cy - s * .25 + sx * s * .06)], fill=color, width=max(3, int(s * .05)))


def _mouth(d, cx, cy, s, emotion, color=(40, 20, 20)):
    e = (emotion or "").lower()
    w = max(3, int(s * .05))
    if e in ("shocked", "panicked", "surprised", "scared"):
        d.ellipse([cx - s * .12, cy - s * .1, cx + s * .12, cy + s * .16], fill=color)
    elif e in ("sad", "embarrassed", "nervous", "tired", "exasperated"):
        d.arc([cx - s * .2, cy, cx + s * .2, cy + s * .25], 200, 340, fill=color, width=w)
    elif e in ("deadpan", "suspicious", "neutral", "determined"):
        d.line([(cx - s * .15, cy + s * .05), (cx + s * .15, cy + s * .05)], fill=color, width=w)
    else:
        d.chord([cx - s * .22, cy - s * .12, cx + s * .22, cy + s * .22], 0, 180, fill=color)


def _draw_character(img, c: dict, cx: float, base_y: float, s: float, emotion: str):
    d = ImageDraw.Draw(img)
    pal = [_hex(x) for x in (c.get("palette") or ["#999999", "#FFFFFF", "#333333"])] + [(80, 80, 80)] * 3
    main, light, accent = pal[0], pal[1], pal[2]
    out = _shade(main, 0.55)
    ow = max(3, int(s * .03))
    sp = c.get("species", "other")
    # shadow
    d.ellipse([cx - s * .7, base_y - s * .08, cx + s * .7, base_y + s * .08], fill=(0, 0, 0, 60))
    if sp == "human":
        d.rounded_rectangle([cx - s * .45, base_y - s * 1.5, cx + s * .45, base_y], radius=int(s * .2), fill=accent, outline=_shade(accent, .6), width=ow)
        d.rounded_rectangle([cx - s * .55, base_y - s * 1.45, cx - s * .2, base_y - s * .2], radius=int(s * .15), fill=main, outline=out, width=ow)
        d.rounded_rectangle([cx + s * .2, base_y - s * 1.45, cx + s * .55, base_y - s * .2], radius=int(s * .15), fill=main, outline=out, width=ow)
        hy = base_y - s * 2.05
        d.ellipse([cx - s * .45, hy - s * .5, cx + s * .45, hy + s * .5], fill=(246, 210, 180), outline=(150, 110, 90), width=ow)
        d.chord([cx - s * .5, hy - s * .62, cx + s * .5, hy + s * .1], 180, 360, fill=pal[2] if len(pal) > 2 else (90, 60, 40))
        _eyes(d, cx, hy, s * .9, emotion)
        for sx in (-1, 1):
            d.ellipse([cx + sx * s * .29 - s * .17, hy - s * .17, cx + sx * s * .29 + s * .17, hy + s * .17], outline=(30, 30, 30), width=ow)
        _mouth(d, cx, hy + s * .22, s * .9, emotion)
        return
    body_h = s * (1.25 if sp == "owl" else 1.0)
    d.ellipse([cx - s * .6, base_y - body_h, cx + s * .6, base_y], fill=main, outline=out, width=ow)
    d.ellipse([cx - s * .35, base_y - body_h * .8, cx + s * .35, base_y - s * .05], fill=light)
    hy = base_y - body_h - s * .35
    hr = s * .55
    if sp == "owl":
        hy = base_y - body_h * .72
        for sx in (-1, 1):
            d.polygon([(cx + sx * hr * .5, hy - hr * .9), (cx + sx * hr * .95, hy - hr * 1.35), (cx + sx * hr * .9, hy - hr * .6)], fill=main, outline=out)
        _eyes(d, cx, hy - hr * .3, s * 1.2, emotion)
        d.polygon([(cx - s * .08, hy - hr * .05), (cx + s * .08, hy - hr * .05), (cx, hy + s * .12)], fill=(245, 170, 30))
        d.polygon([(cx - s * .06, hy + s * .2), (cx + s * .06, hy + s * .2), (cx, hy + s * .65)], fill=accent)
        return
    if sp == "cat":
        for sx in (-1, 1):
            d.polygon([(cx + sx * hr * .25, hy - hr * .75), (cx + sx * hr * .95, hy - hr * 1.25), (cx + sx * hr * .85, hy - hr * .2)], fill=main, outline=out, width=ow)
    d.ellipse([cx - hr, hy - hr, cx + hr, hy + hr], fill=main, outline=out, width=ow)
    if sp == "dog":
        for sx in (-1, 1):
            d.ellipse([cx + sx * hr * .75 - hr * .3, hy - hr * .7, cx + sx * hr * .75 + hr * .3, hy + hr * .5], fill=_shade(main, .75), outline=out, width=ow)
        d.ellipse([cx - hr * .5, hy + hr * .05, cx + hr * .5, hy + hr * .75], fill=light)
    _eyes(d, cx, hy - hr * .1, s, emotion)
    d.ellipse([cx - s * .08, hy + hr * .2, cx + s * .08, hy + hr * .35], fill=(40, 30, 30))
    _mouth(d, cx, hy + hr * .45, s * .8, emotion)
    if sp == "cat":
        for sy in (-1, 0, 1):
            for sx in (-1, 1):
                d.line([(cx + sx * hr * .35, hy + hr * .35), (cx + sx * hr * 1.1, hy + hr * .3 + sy * hr * .15)], fill=out, width=max(2, ow // 2))
    # collar in accent colour
    d.arc([cx - hr * .7, hy + hr * .45, cx + hr * .7, hy + hr * 1.15], 20, 160, fill=accent, width=max(6, int(s * .09)))


def _wrap(text, fnt, width, d):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def storyboard(out: Path, aspect: str, ctx: dict, seed: int = 0) -> Path:
    W, H = size_for(aspect, "storyboard")
    r = random.Random(seed)
    img = Image.new("RGB", (W, H))
    scene = ctx.get("scene") or {}
    _background(img, scene.get("setting", ""), r)
    cast = [c for c in ctx.get("cast", []) if c.get("species") != "narrator"][:3]
    emotions = {d["character"]: d.get("emotion") for d in scene.get("dialogue", [])}
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    s = (W if aspect == "16:9" else W * 1.7) / (5.5 + len(cast))
    base_y = H * (0.86 if aspect == "16:9" else 0.84)
    for i, c in enumerate(cast):
        cx = W * (i + 1) / (len(cast) + 1)
        _draw_character(layer, c, cx, base_y, s, emotions.get(c["id"], "happy"))
    img.paste(layer, (0, 0), layer)
    d = ImageDraw.Draw(img)
    # scene label (storyboard look) - captions are added later as subtitles
    if scene.get("on_screen_text") and not ctx.get("clean"):
        f_big = fonts.font(max(48, W // 14))
        txt = scene["on_screen_text"].upper()
        tw = d.textlength(txt, font=f_big)
        y = H * (0.12 if aspect == "16:9" else 0.18)
        d.text(((W - tw) / 2, y), txt, font=f_big, fill=(255, 220, 0), stroke_width=max(4, W // 200), stroke_fill=(0, 0, 0))
    img = img.filter(ImageFilter.SMOOTH)
    img.save(out, "PNG")
    return out
