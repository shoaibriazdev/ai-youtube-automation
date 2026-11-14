"""Find a bold display font on the system (no fonts are bundled, to avoid licensing issues)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from . import config

CANDIDATES = [
    config.ASSETS_DIR / "fonts" / "display.ttf",
    Path("C:/Windows/Fonts/impact.ttf"), Path("C:/Windows/Fonts/ariblk.ttf"), Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    Path("/Library/Fonts/Arial Bold.ttf"), Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
]
BODY = [config.ASSETS_DIR / "fonts" / "body.ttf", Path("C:/Windows/Fonts/arialbd.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]


@lru_cache(maxsize=None)
def _path(kind: str) -> str | None:
    for p in (CANDIDATES if kind == "display" else BODY):
        if p.exists():
            return str(p)
    return None


def font(size: int, kind: str = "display"):
    p = _path(kind) or _path("display")
    if p:
        return ImageFont.truetype(p, size)
    return ImageFont.load_default(size=size)


def family_name() -> str:
    p = _path("body") or ""
    return {"impact.ttf": "Impact", "ariblk.ttf": "Arial Black", "arialbd.ttf": "Arial",
            "dejavusans-bold.ttf": "DejaVu Sans"}.get(Path(p).name.lower(), "DejaVu Sans" if "dejavu" in p.lower() else "Arial")
