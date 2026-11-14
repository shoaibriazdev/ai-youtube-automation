"""STEP 6 - Automatic video editing with FFmpeg + Python.

1. Timeline: each scene lasts as long as its dialogue (+ padding, min length).
2. Scene clips: AI video clip (looped/trimmed, cover-cropped) or the still image animated with a
   Ken Burns move (zoom in/out, pan) via zoompan. Images of the other aspect are letterboxed on a
   blurred copy of themselves, so 16:9 art also makes a usable 9:16 and vice versa.
3. Transitions: xfade between scenes (fade, slideleft, circleopen, wipeleft) or hard cuts.
4. Audio: voices placed on the timeline, synthesized/user SFX at cue points, background music
   ducked under dialogue, normalised (numpy) -> one WAV.
5. Subtitles: styled ASS captions (speaker-coloured, word-chunked) burned in with libass, plus an
   .srt sidecar for YouTube closed captions.
6. Export H.264/AAC MP4 (yuv420p, +faststart) at 9:16 (1080x1920) and/or 16:9 (1920x1080).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageFilter

from . import audio, characters, db, ffmpeg, fonts, projects

QUALITY = {"draft": {"short": (720, 1280), "long": (1280, 720), "fps": 24, "crf": 26, "preset": "veryfast"},
           "hd": {"short": (1080, 1920), "long": (1920, 1080), "fps": 30, "crf": 20, "preset": "medium"}}
MOVES = ["zoom_in", "pan_right", "zoom_out", "pan_left"]


class EditError(RuntimeError):
    pass


def build_timeline(project: dict) -> dict:
    r = db.get_setting("render")
    script = project.get("script") or {}
    voice = project["assets"].get("voice", {})
    t, scenes = 0.0, []
    lead, gap = 0.35, 0.22
    for s in script.get("scenes", []):
        lines, cur = [], lead
        for i, d in enumerate(s["dialogue"]):
            key = f"{s['n']}-{i}"
            v = voice.get(key)
            if not v:
                raise EditError(f"Missing voiceover for scene {s['n']} line {i + 1}. Run the voice step first.")
            lines.append({"key": key, "character": d["character"], "text": d["line"], "start": round(t + cur, 3),
                          "duration": v["duration"], "file": v["file"]})
            cur += v["duration"] + gap
        dur = max(float(r["min_scene_seconds"]), cur - gap + float(r["scene_padding_seconds"]))
        sfx = []
        for x in s.get("sfx", []):
            cue = x.get("cue", "start")
            if cue == "end":
                at = t + dur - 0.5
            elif cue.startswith("after_line:"):
                try:
                    k = int(cue.split(":")[1]) - 1
                    ln = lines[max(0, min(k, len(lines) - 1))]
                    at = ln["start"] + ln["duration"] + 0.02
                except (ValueError, IndexError):
                    at = t
            else:
                at = t + 0.02
            sfx.append({"name": x["name"], "at": round(max(0, at), 3)})
        scenes.append({"n": s["n"], "start": round(t, 3), "duration": round(dur, 3), "lines": lines, "sfx": sfx})
        t += dur
    if not scenes:
        raise EditError("Script has no scenes.")
    return {"duration": round(t, 3), "scenes": scenes}


def _prepare_frame(src: Path, dst: Path, W: int, H: int, scale: float = 1.0) -> Path:
    """Cover-crop if aspect is close; otherwise fit over a blurred, darkened copy (no stretching)."""
    img = Image.open(src).convert("RGB")
    tw, th = int(W * scale), int(H * scale)
    ar_src, ar_dst = img.width / img.height, tw / th
    if abs(ar_src - ar_dst) / ar_dst < 0.25:
        k = max(tw / img.width, th / img.height)
        im = img.resize((max(tw, round(img.width * k)), max(th, round(img.height * k))), Image.LANCZOS)
        x, y = (im.width - tw) // 2, (im.height - th) // 2
        out = im.crop((x, y, x + tw, y + th))
    else:
        k = max(tw / img.width, th / img.height)
        bg = img.resize((round(img.width * k) + 2, round(img.height * k) + 2)).crop((0, 0, tw, th))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=max(8, tw // 40))).point(lambda v: int(v * 0.6))
        k2 = min(tw / img.width, th / img.height)
        fg = img.resize((round(img.width * k2), round(img.height * k2)), Image.LANCZOS)
        bg.paste(fg, ((tw - fg.width) // 2, (th - fg.height) // 2))
        out = bg
    out.save(dst, "PNG")
    return dst


def _zoompan(move: str, frames: int) -> str:
    n = max(1, frames - 1)
    if move == "zoom_in":
        return f"zoompan=z='1+0.18*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    if move == "zoom_out":
        return f"zoompan=z='1.18-0.18*on/{n}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    if move == "pan_right":
        return f"zoompan=z='1.15':x='(iw-iw/zoom)*on/{n}':y='ih/2-(ih/zoom/2)'"
    return f"zoompan=z='1.15':x='(iw-iw/zoom)*(1-on/{n})':y='ih/2-(ih/zoom/2)'"


def render_scene_clip(src_image: Path | None, src_clip: Path | None, out: Path, W: int, H: int, fps: int,
                      duration: float, move: str, q: dict, work: Path) -> Path:
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", str(q["crf"]), "-pix_fmt", "yuv420p", "-an"]
    if src_clip and Path(src_clip).exists():
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps},setsar=1"
        ffmpeg.run(["-stream_loop", "-1", "-i", src_clip, "-t", f"{duration:.3f}", "-vf", vf, *enc, out],
                   retries=1, what=f"scene clip {out.name}")
        return out
    if not src_image or not Path(src_image).exists():
        raise EditError(f"No image for {out.stem}. Run the image step first.")
    frame = _prepare_frame(Path(src_image), work / f"{out.stem}_frame.png", W, H, scale=1.5)
    frames = int(round(duration * fps))
    vf = f"{_zoompan(move, frames)}:d={frames}:s={W}x{H}:fps={fps},setsar=1,format=yuv420p"
    ffmpeg.run(["-i", frame, "-vf", vf, "-frames:v", str(frames), *enc, out], retries=1,
               what=f"Ken Burns clip {out.name}")
    return out


# ---------------- subtitles ----------------
def _ass_time(t: float) -> str:
    t = max(0.0, t)
    h, m = int(t // 3600), int(t % 3600 // 60)
    s = t - h * 3600 - m * 60
    return f"{h}:{m:02d}:{s:05.2f}"


def _srt_time(t: float) -> str:
    ms = int(round(max(0.0, t) * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def _ass_color(hexcolor: str) -> str:
    c = hexcolor.lstrip("#")
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H00{b}{g}{r}".upper()


def caption_chunks(timeline: dict, words_per: int) -> list[dict]:
    out = []
    for sc in timeline["scenes"]:
        for ln in sc["lines"]:
            words = ln["text"].split()
            if not words:
                continue
            chunks = [words[i:i + words_per] for i in range(0, len(words), words_per)]
            total = sum(len(" ".join(c)) for c in chunks) or 1
            t = ln["start"]
            for c in chunks:
                txt = " ".join(c)
                d = ln["duration"] * len(txt) / total
                out.append({"start": t, "end": t + d, "text": txt, "character": ln["character"]})
                t += d
    return out


def write_subtitles(timeline: dict, folder: Path, W: int, H: int, words_per: int) -> tuple[Path, Path]:
    vertical = H > W
    size = int(H * 0.046) if vertical else int(H * 0.066)
    # Shorts: captions sit in the upper-middle (clear of characters and of YouTube's bottom UI).
    margin_v = int(H * 0.56) if vertical else int(H * 0.06)
    font = fonts.family_name()
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,1,0,1,{max(3, size // 12)},{max(2, size // 20)},2,{int(W * .06)},{int(W * .06)},{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines, srt = [], []
    for i, c in enumerate(caption_chunks(timeline, words_per), 1):
        ch = characters.lookup(c["character"]) or {}
        color = (ch.get("palette") or ["#FFFFFF"])[0] if ch.get("species") != "narrator" else "#FFFFFF"
        # lighten very dark colours so captions stay readable
        rgb = [int(color.lstrip("#")[k:k + 2], 16) for k in (0, 2, 4)]
        if sum(rgb) < 300:
            color = "#FFFFFF"
        txt = c["text"].replace("{", "(").replace("}", ")").upper()
        lines.append(f"Dialogue: 0,{_ass_time(c['start'])},{_ass_time(c['end'])},Default,,0,0,0,,"
                     f"{{\\c{_ass_color(color)}\\fad(40,40)}}{txt}")
        srt.append(f"{i}\n{_srt_time(c['start'])} --> {_srt_time(c['end'])}\n{c['text']}\n")
    ass = folder / "subs.ass"
    ass.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")
    srt_path = folder / "captions.srt"
    srt_path.write_text("\n".join(srt), encoding="utf-8")
    return ass, srt_path


# ---------------- audio ----------------
def build_audio(project: dict, timeline: dict, out: Path) -> dict:
    r = db.get_setting("render")
    pid = project["id"]
    voices = []
    for sc in timeline["scenes"]:
        for ln in sc["lines"]:
            voices.append((ln["start"], audio.read_wav(projects.abspath(pid, ln["file"]))))
    sfx = [(x["at"], x["name"]) for sc in timeline["scenes"] for x in sc["sfx"]]
    mood = (project.get("script") or {}).get("music_mood", "playful")
    mixed, info = audio.mix(timeline["duration"], voices, sfx, mood, float(r["music_volume"]), float(r["sfx_volume"]))
    audio.write_wav(out, mixed)
    return info


# ---------------- main ----------------
def render(project: dict, aspects: list[str] | None = None, progress=None) -> dict:
    pid = project["id"]
    rs = db.get_setting("render")
    q = QUALITY.get(rs.get("quality", "hd"), QUALITY["hd"])
    fps = q["fps"]
    primary = "9:16" if project["format"] == "short" else "16:9"
    aspects = aspects or [primary]
    timeline = build_timeline(project)
    rdir = projects.project_dir(pid) / "render"
    work = rdir / "work"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    say = progress or (lambda *_: None)

    say(0.05, "Mixing audio (voices, SFX, music)")
    wav = work / "mix.wav"
    audio_info = build_audio(project, timeline, wav)

    trans = rs.get("transition", "fade")
    T = float(rs.get("transition_seconds", 0.4)) if trans != "none" else 0.0
    results = {}
    for ai, aspect in enumerate(aspects):
        W, H = q["short"] if aspect == "9:16" else q["long"]
        tag = "vertical_9x16" if aspect == "9:16" else "horizontal_16x9"
        clips = []
        n = len(timeline["scenes"])
        for i, sc in enumerate(timeline["scenes"]):
            say(0.1 + 0.75 * (ai + i / n) / len(aspects), f"Rendering scene {sc['n']}/{n} ({aspect})")
            dur = sc["duration"] + (T if i < n - 1 else 0)
            img = (project["assets"].get("images_alt", {}).get(aspect, {}).get(str(sc["n"]))
                   or project["assets"]["images"].get(str(sc["n"])))
            clip = project["assets"]["clips"].get(str(sc["n"]))
            out = work / f"{tag}_scene{sc['n']:02d}.mp4"
            render_scene_clip(projects.abspath(pid, img) if img else None,
                              projects.abspath(pid, clip) if clip else None,
                              out, W, H, fps, dur, MOVES[i % len(MOVES)], q, work)
            clips.append(out.name)
        ass, srt = write_subtitles(timeline, work, W, H, int(rs.get("subtitle_words_per_caption", 4)))
        final = rdir / f"final_{tag}.mp4"
        say(0.1 + 0.75 * (ai + 1) / len(aspects), f"Assembling final video ({aspect})")
        inputs = []
        for c in clips:
            inputs += ["-i", c]
        inputs += ["-i", wav.name]
        parts, last = [], "[0:v]"
        if T > 0 and n > 1:
            off = 0.0
            for i in range(1, n):
                off += timeline["scenes"][i - 1]["duration"]
                label = f"[x{i}]"
                parts.append(f"{last}[{i}:v]xfade=transition={trans}:duration={T:.3f}:offset={off:.3f}{label}")
                last = label
        elif n > 1:
            parts.append("".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n}:v=1:a=0[cat]")
            last = "[cat]"
        sub = f",ass={ass.name}" if rs.get("subtitles", True) and ffmpeg.has_filter("ass") else ""
        parts.append(f"{last}format=yuv420p{sub}[vout]")
        args = [*inputs, "-filter_complex", ";".join(parts), "-map", "[vout]", "-map", f"{n}:a",
                "-c:v", "libx264", "-preset", q["preset"], "-crf", str(q["crf"]), "-r", str(fps),
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-t", f"{timeline['duration']:.3f}",
                "-movflags", "+faststart", str(final.resolve())]
        ffmpeg.run(args, cwd=work, retries=1, what=f"final render {aspect}")
        shutil.copy(srt, rdir / f"captions_{tag}.srt")
        results[aspect] = {"file": projects.rel(pid, final), "width": W, "height": H,
                           "srt": projects.rel(pid, rdir / f"captions_{tag}.srt"),
                           "duration": round(ffmpeg.media_duration(final), 2),
                           "size_mb": round(final.stat().st_size / 1e6, 2)}
    shutil.copy(wav, rdir / "mix.wav")
    shutil.rmtree(work, ignore_errors=True)
    say(1.0, "Render complete")
    return {"outputs": results, "timeline": timeline, "audio": audio_info, "quality": rs.get("quality"),
            "subtitles_burned": bool(rs.get("subtitles", True) and ffmpeg.has_filter("ass"))}
