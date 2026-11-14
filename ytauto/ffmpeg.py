"""Locate and run FFmpeg with retries and readable errors.

Order: FFMPEG_BINARY env var -> `ffmpeg` on PATH -> the static build bundled by the
`imageio-ffmpeg` pip package (installed by setup.bat, so no manual FFmpeg install is needed).
"""
from __future__ import annotations

import shutil
import subprocess
import time
import wave
from functools import lru_cache
from pathlib import Path

from . import config


class FFmpegError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def binary() -> str:
    custom = config.env("FFMPEG_BINARY")
    if custom and Path(custom).exists():
        return custom
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # pragma: no cover - depends on install
        raise FFmpegError("FFmpeg not found. Run setup.bat again (installs imageio-ffmpeg), install FFmpeg "
                          "and add it to PATH, or set FFMPEG_BINARY in .env.") from e


def version() -> str:
    out = subprocess.run([binary(), "-version"], capture_output=True, text=True, timeout=30)
    return out.stdout.splitlines()[0] if out.stdout else "unknown"


def has_filter(name: str) -> bool:
    out = subprocess.run([binary(), "-hide_banner", "-filters"], capture_output=True, text=True, timeout=30)
    return f" {name} " in out.stdout


def run(args: list[str], cwd: str | Path | None = None, retries: int = 1, timeout: int = 1800,
        what: str = "ffmpeg") -> None:
    cmd = [binary(), "-hide_banner", "-loglevel", "error", "-y", *map(str, args)]
    last = ""
    for attempt in range(retries + 1):
        try:
            p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
                               encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            last = f"timed out after {timeout}s"
            continue
        if p.returncode == 0:
            return
        last = (p.stderr or "").strip()[-1500:]
        time.sleep(1 + attempt)
    raise FFmpegError(f"{what} failed: {last}")


def to_wav(src: Path, dst: Path, rate: int = 44100) -> Path:
    run(["-i", src, "-ac", "1", "-ar", rate, "-sample_fmt", "s16", dst], what=f"convert {Path(src).name} to wav")
    return dst


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


def media_duration(path: Path) -> float:
    """Duration of any media file, by decoding with ffmpeg (no ffprobe needed)."""
    p = subprocess.run([binary(), "-hide_banner", "-i", str(path), "-f", "null", "-"],
                       capture_output=True, text=True, timeout=600, encoding="utf-8", errors="replace")
    t = 0.0
    for line in (p.stderr or "").splitlines():
        if "time=" in line:
            try:
                hms = line.split("time=")[1].split()[0]
                h, m, s = hms.split(":")
                t = int(h) * 3600 + int(m) * 60 + float(s)
            except (ValueError, IndexError):
                pass
    return t
