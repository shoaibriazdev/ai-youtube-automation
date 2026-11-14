"""Audio: original synthesized sound effects + background music, and the final mix.

Everything here is generated mathematically (numpy), so it is original and royalty-free. To use
your own licensed files instead, drop them in:
  assets/sfx/<name>.wav|mp3   (e.g. assets/sfx/boing.mp3 replaces the synthesized boing)
  assets/music/<mood>*.mp3    (playful, sneaky, bouncy, dramatic, chill) or any file in assets/music
"""
from __future__ import annotations

import wave
import zlib
from pathlib import Path

import numpy as np

from . import config, ffmpeg

SR = 44100
SFX_NAMES = ["boing", "pop", "whoosh", "ding", "rimshot", "record_scratch", "cartoon_slip", "crickets",
             "gasp_sting", "tada", "buzzer", "splat"]


def _t(sec: float) -> np.ndarray:
    return np.arange(int(SR * sec)) / SR


def _env(n: int, attack=0.005, release=0.1) -> np.ndarray:
    e = np.ones(n)
    a, r = max(1, int(attack * SR)), max(1, int(release * SR))
    e[:a] = np.linspace(0, 1, a)
    e[-r:] *= np.linspace(1, 0, r)
    return e


def _tone(freq, sec, kind="sine"):
    t = _t(sec)
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(freq, t.shape)) / SR
    if kind == "square":
        return np.sign(np.sin(ph)) * 0.6
    if kind == "tri":
        return 2 / np.pi * np.arcsin(np.sin(ph))
    return np.sin(ph)


def synth_sfx(name: str) -> np.ndarray:
    rng = np.random.default_rng(zlib.crc32(name.encode()))
    if name == "boing":
        t = _t(0.6)
        f = 180 + 220 * np.exp(-t * 6) * (1 + 0.35 * np.sin(2 * np.pi * 14 * t))
        x = _tone(f, 0.6) * np.exp(-t * 4)
    elif name == "pop":
        t = _t(0.12)
        x = _tone(900 * np.exp(-t * 30) + 300, 0.12) * np.exp(-t * 40)
    elif name == "whoosh":
        n = rng.standard_normal(int(SR * 0.7))
        k = np.convolve(n, np.ones(30) / 30, mode="same")
        x = k * np.sin(np.linspace(0, np.pi, k.size)) ** 2 * 2.5
    elif name == "ding":
        t = _t(1.2)
        x = (np.sin(2 * np.pi * 1318 * t) + 0.5 * np.sin(2 * np.pi * 2637 * t)) * np.exp(-t * 4) * 0.6
    elif name == "rimshot":
        parts = []
        for f, d in ((160, 0.18), (190, 0.18)):
            t = _t(d)
            parts.append(_tone(f * np.exp(-t * 8) + 50, d) * np.exp(-t * 12) + rng.standard_normal(t.size) * np.exp(-t * 30) * 0.3)
        t = _t(0.8)
        cym = rng.standard_normal(t.size) * np.exp(-t * 4) * 0.35
        cym = cym - np.convolve(cym, np.ones(4) / 4, mode="same")
        x = np.concatenate(parts + [cym])
    elif name == "record_scratch":
        t = _t(0.45)
        f = 600 + 500 * np.sin(2 * np.pi * 7 * t)
        x = (_tone(f, 0.45, "square") * 0.3 + rng.standard_normal(t.size) * 0.25) * np.exp(-t * 3)
    elif name == "cartoon_slip":
        t = _t(0.7)
        x = _tone(1200 * np.exp(-t * 3) + 150, 0.7, "tri") * (1 - t / 0.7) * 0.8
    elif name == "crickets":
        t = _t(2.0)
        chirp = np.sin(2 * np.pi * 4500 * t) * (np.sin(2 * np.pi * 30 * t) > 0.6)
        gate = (np.sin(2 * np.pi * 1.5 * t) > 0.2)
        x = chirp * gate * 0.25
    elif name == "gasp_sting":
        parts = [(_tone(f, 0.35, "square") * np.exp(-_t(0.35) * 3) * 0.35) for f in (330, 311, 294)]
        x = np.concatenate(parts + [_tone(277, 0.8, "square") * np.exp(-_t(0.8) * 2) * 0.35])
    elif name == "tada":
        a = sum(np.sin(2 * np.pi * f * _t(0.15)) for f in (523, 659, 784)) * 0.3
        b = sum(np.sin(2 * np.pi * f * _t(0.9)) for f in (523, 659, 784, 1046)) * 0.25 * np.exp(-_t(0.9) * 2)
        x = np.concatenate([a, b])
    elif name == "buzzer":
        t = _t(0.7)
        x = _tone(110, 0.7, "square") * 0.5 + _tone(116, 0.7, "square") * 0.3
    elif name == "splat":
        t = _t(0.35)
        n = rng.standard_normal(t.size)
        x = np.convolve(n, np.ones(60) / 60, mode="same") * np.exp(-t * 12) * 4 + _tone(80, 0.35) * np.exp(-t * 15)
    else:
        raise ValueError(f"unknown sfx {name}")
    x = x * _env(x.size, 0.002, 0.03)
    return (x / (np.max(np.abs(x)) + 1e-9) * 0.9).astype(np.float32)


NOTE = lambda m: 440.0 * 2 ** ((m - 69) / 12)

MOODS = {
    # tempo, root midi, progression (scale degrees as semitone offsets), wave
    "playful": (118, 60, [0, 7, 9, 5], "tri"),
    "bouncy": (132, 62, [0, 5, 7, 5], "square"),
    "sneaky": (96, 57, [0, 3, 5, 3], "tri"),
    "dramatic": (84, 55, [0, 8, 3, 10], "sine"),
    "chill": (90, 60, [0, 9, 5, 7], "sine"),
}


def synth_music(mood: str, seconds: float, seed: int = 7) -> np.ndarray:
    tempo, root, prog, wave_kind = MOODS.get(mood, MOODS["playful"])
    rng = np.random.default_rng(seed)
    beat = 60.0 / tempo
    bar = beat * 4
    total = int(SR * (seconds + 0.5))
    out = np.zeros(total, dtype=np.float32)
    minor = mood in ("sneaky", "dramatic")
    third = 3 if minor else 4
    pattern = [0, third, 7, 12, 7, third, 0, 7]
    bars = int(np.ceil(seconds / bar)) + 1
    for b in range(bars):
        chord_root = root + prog[b % len(prog)]
        t0 = b * bar
        # bass on beats 1 and 3
        for k in (0, 2):
            s = int((t0 + k * beat) * SR)
            note = _tone(NOTE(chord_root - 12), beat * 0.9, "sine") * _env(int(SR * beat * 0.9), 0.005, 0.15) * 0.35
            e = min(total, s + note.size)
            if s < total:
                out[s:e] += note[: e - s]
        # arpeggio in eighths
        for k, off in enumerate(pattern):
            s = int((t0 + k * beat / 2) * SR)
            dur = beat / 2 * 0.8
            n = _tone(NOTE(chord_root + off + (12 if rng.random() < 0.15 else 0)), dur, wave_kind)
            n = n * _env(n.size, 0.003, dur * 0.6) * (0.12 if wave_kind == "square" else 0.18)
            e = min(total, s + n.size)
            if s < total:
                out[s:e] += n[: e - s]
        # light percussion: hat on offbeats, soft kick on 1
        for k in range(8):
            s = int((t0 + k * beat / 2) * SR)
            if k % 2 == 1:
                h = rng.standard_normal(int(SR * 0.04)) * np.exp(-_t(0.04) * 90) * 0.05
            elif k == 0:
                h = _tone(120 * np.exp(-_t(0.15) * 20) + 45, 0.15) * np.exp(-_t(0.15) * 18) * 0.3
            else:
                continue
            e = min(total, s + h.size)
            if s < total:
                out[s:e] += h[: e - s]
    out = out[: int(SR * seconds)]
    fade = min(int(SR * 1.5), out.size // 4)
    if fade:
        out[:fade] *= np.linspace(0, 1, fade)
        out[-fade:] *= np.linspace(1, 0, fade)
    return out / (np.max(np.abs(out)) + 1e-9) * 0.8


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2 or w.getnchannels() != 1 or w.getframerate() != SR:
            raise ValueError(f"{path} must be 16-bit mono {SR} Hz")
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0


def write_wav(path: Path, x: np.ndarray) -> Path:
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
    return path


def load_any(path: Path) -> np.ndarray:
    """Load any audio file as mono float32 at SR (converts via ffmpeg when needed)."""
    path = Path(path)
    if path.suffix.lower() == ".wav":
        try:
            return read_wav(path)
        except (ValueError, wave.Error):
            pass
    tmp = config.CACHE_DIR / f"conv_{zlib.crc32(str(path.resolve()).encode())}.wav"
    if not tmp.exists() or tmp.stat().st_mtime < path.stat().st_mtime:
        ffmpeg.to_wav(path, tmp)
    return read_wav(tmp)


def sfx(name: str) -> np.ndarray:
    for ext in (".wav", ".mp3", ".ogg"):
        f = config.ASSETS_DIR / "sfx" / f"{name}{ext}"
        if f.exists():
            return load_any(f)
    return synth_sfx(name)


def music(mood: str, seconds: float) -> tuple[np.ndarray, str]:
    folder = config.ASSETS_DIR / "music"
    files = sorted([f for f in folder.glob("*") if f.suffix.lower() in (".mp3", ".wav", ".ogg", ".m4a")])
    pick = next((f for f in files if f.stem.lower().startswith(mood)), files[0] if files else None)
    if pick:
        x = load_any(pick)
        reps = int(np.ceil(seconds * SR / max(1, x.size)))
        x = np.tile(x, reps)[: int(seconds * SR)]
        fade = min(int(SR * 1.5), x.size // 4)
        if fade:
            x[-fade:] *= np.linspace(1, 0, fade)
        return x, pick.name
    return synth_music(mood, seconds), f"synth:{mood}"


def mix(duration: float, voice_events: list[tuple[float, np.ndarray]], sfx_events: list[tuple[float, str]],
        mood: str, music_volume: float = 0.16, sfx_volume: float = 0.7) -> tuple[np.ndarray, dict]:
    """Place voices and SFX on a timeline, add music ducked under the voices, normalise."""
    n = int(SR * duration) + SR
    voice = np.zeros(n, dtype=np.float32)
    for t, clip in voice_events:
        s = int(t * SR)
        e = min(n, s + clip.size)
        voice[s:e] += clip[: e - s]
    fx = np.zeros(n, dtype=np.float32)
    for t, name in sfx_events:
        clip = sfx(name)
        s = int(max(0, t) * SR)
        e = min(n, s + clip.size)
        if s < n:
            fx[s:e] += clip[: e - s]
    bed, music_src = music(mood, n / SR)
    bed = np.pad(bed, (0, max(0, n - bed.size)))[:n]
    # Ducking: music drops to 35% while anyone is speaking (smoothed envelope).
    energy = np.sqrt(moving_average(voice.astype(np.float64) ** 2, int(0.05 * SR)))
    speaking = (energy > 0.01).astype(np.float64)
    smooth = moving_average(speaking, int(0.3 * SR))
    duck = 1.0 - 0.65 * np.clip(smooth, 0, 1)
    out = voice + fx * sfx_volume + bed * music_volume * duck
    out = out[: int(SR * duration)]
    peak = np.max(np.abs(out)) + 1e-9
    out = out / peak * 0.89
    return out, {"music": music_src, "peak_before_norm": float(peak)}


def moving_average(x: np.ndarray, win: int) -> np.ndarray:
    """Centered moving average in O(n) using a cumulative sum (same length as x)."""
    win = max(1, int(win))
    c = np.cumsum(np.concatenate([np.zeros(1), x]))
    half = win // 2
    idx = np.arange(x.size)
    lo = np.clip(idx - half, 0, x.size)
    hi = np.clip(idx - half + win, 0, x.size)
    return (c[hi] - c[lo]) / win


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(SR * seconds), dtype=np.float32)
