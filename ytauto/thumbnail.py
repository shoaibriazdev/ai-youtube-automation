"""STEP 7 - Thumbnail generator (1280x720, JPG under YouTube's 2 MB limit, plus PNG).

Background: a dedicated AI image (if the image provider is paid/remote) or the strongest scene frame.
Design: colour grade, vignette, a bold stroked text block (max 3 words, never repeating the title -
checked with the original title.py linter), an accent burst, optional emoji-style badge.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from . import fonts, legacy

W, H = 1280, 720
STYLES = {
    "pop": {"text": (255, 230, 0), "stroke": (0, 0, 0), "accent": (255, 60, 60)},
    "clean": {"text": (255, 255, 255), "stroke": (20, 20, 20), "accent": (0, 170, 255)},
    "shock": {"text": (255, 255, 255), "stroke": (200, 0, 0), "accent": (255, 210, 0)},
}


def _cover(img: Image.Image) -> Image.Image:
    k = max(W / img.width, H / img.height)
    im = img.resize((round(img.width * k) + 1, round(img.height * k) + 1), Image.LANCZOS)
    x, y = (im.width - W) // 2, max(0, (im.height - H) // 3)
    return im.crop((x, y, x + W, y + H))


def _vignette(img: Image.Image, strength: float = 0.55) -> Image.Image:
    """Darken the edges only (centre stays at full brightness)."""
    import numpy as np
    y, x = np.ogrid[:H, :W]
    r = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2) / np.sqrt(2)
    keep = 1 - strength * np.clip((r - 0.45) / 0.55, 0, 1) ** 1.5
    arr = np.asarray(img).astype(np.float32) * keep[..., None]
    return Image.fromarray(arr.clip(0, 255).astype("uint8"))


def _burst(d: ImageDraw.ImageDraw, cx, cy, r, color, spikes=14):
    pts = []
    for i in range(spikes * 2):
        ang = math.pi * i / spikes
        rr = r if i % 2 == 0 else r * 0.62
        pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
    d.polygon(pts, fill=color, outline=(0, 0, 0))


def make(background: Path | None, text: str, out_dir: Path, title: str = "", style: str = "pop",
         badge: str = "?!", text_side: str = "left") -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    st = STYLES.get(style, STYLES["pop"])
    words = (text or "").split()
    warnings = []
    if len(words) > 3:
        warnings.append("More than 3 words - trimmed to 3 so it reads at feed size.")
        words = words[:3]
    text = " ".join(words).upper()
    if background and Path(background).exists():
        img = _cover(Image.open(background).convert("RGB"))
    else:
        img = Image.new("RGB", (W, H), (40, 120, 220))
    img = ImageEnhance.Color(img).enhance(1.35)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = _vignette(img)
    d = ImageDraw.Draw(img)
    if text:
        size = 150 if len(text) <= 10 else 120 if len(text) <= 16 else 96
        f = fonts.font(size)
        lines = text.split() if len(text) > 10 else [text]
        if len(lines) == 3:
            lines = [lines[0], " ".join(lines[1:])]
        heights = [d.textbbox((0, 0), ln, font=f, stroke_width=10)[3] for ln in lines]
        y = H - sum(heights) - 40 * len(lines) - 30
        for ln, hh in zip(lines, heights):
            tw = d.textlength(ln, font=f)
            x = 50 if text_side == "left" else W - tw - 50
            # drop shadow, then stroked text
            d.text((x + 8, y + 10), ln, font=f, fill=(0, 0, 0), stroke_width=12, stroke_fill=(0, 0, 0))
            d.text((x, y), ln, font=f, fill=st["text"], stroke_width=10, stroke_fill=st["stroke"])
            y += hh + 30
    if badge:
        cx = W - 140 if text_side == "left" else 140
        _burst(d, cx, 130, 105, st["accent"])
        bf = fonts.font(90)
        bw = d.textlength(badge, font=bf)
        d.text((cx - bw / 2, 130 - 58), badge, font=bf, fill=(255, 255, 255), stroke_width=6, stroke_fill=(0, 0, 0))
    png = out_dir / "thumbnail.png"
    jpg = out_dir / "thumbnail.jpg"
    img.save(png, "PNG")
    quality = 92
    while True:
        img.save(jpg, "JPEG", quality=quality, optimize=True)
        if jpg.stat().st_size < 2_000_000 or quality <= 50:
            break
        quality -= 8
    lint = legacy.lint_title(title, text) if title else None
    return {"png": str(png), "jpg": str(jpg), "text": text, "style": style, "warnings": warnings,
            "lint": lint, "size_kb": round(jpg.stat().st_size / 1024)}


def best_scene_image(project: dict) -> str | None:
    """Pick the hook scene (first) or the twist scene for the thumbnail background."""
    imgs = project["assets"].get("images", {})
    if "thumb" in imgs:
        return imgs["thumb"]
    script = project.get("script") or {}
    scenes = script.get("scenes") or []
    for s in scenes:  # prefer a scene with on-screen text energy, else scene 1
        if s.get("on_screen_text") and str(s["n"]) in imgs:
            return imgs[str(s["n"])]
    return imgs.get("1") or next(iter(imgs.values()), None)
