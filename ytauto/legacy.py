"""Bridge to the original skill-pack tools so the platform reuses them instead of re-implementing.

- skills/yt-script/hookscore.py  -> score_hook()
- skills/yt-package/title.py     -> lint_title()
- skills/yt-viral/swipe.py       -> classify_title()
"""
from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache

from . import config


@lru_cache(maxsize=None)
def _load(name: str, rel: str):
    path = config.SKILLS_DIR / rel
    spec = importlib.util.spec_from_file_location(f"ytskill_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def score_hook(text: str) -> dict:
    hs = _load("hookscore", "yt-script/hookscore.py")
    parts, verdict, name, hits = hs.score(text)
    return {"hook": text, "properties": parts, "verdict": verdict, "band": hs.band(verdict),
            "formula": name, "weakest": min(parts, key=parts.get)}


def lint_title(title: str, thumb: str | None = None) -> dict:
    tl = _load("title", "yt-package/title.py")
    r = tl.check(title, thumb)
    r["issues"] = [{"kind": k, "message": m} for k, m in r["issues"]]
    return r


def classify_title(title: str) -> str:
    sw = _load("swipe", "yt-viral/swipe.py")
    return sw.classify(title)
