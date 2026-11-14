"""The production pipeline: research -> script -> characters -> images -> video -> voice -> edit ->
thumbnail -> seo -> review. Upload is separate and needs approval (see youtube.py).

Every stage is resumable (results are saved in project.json) and logged to the events table.
Before any paid work, the cost estimate must be approved (status 'awaiting_cost_approval').
"""
from __future__ import annotations

import re
import time
import traceback
import zlib

from . import (characters, costs, db, editor, ffmpeg, llm, projects, research, scriptgen, seo,
               thumbnail)
from .providers import image as image_p, tts as tts_p, video as video_p
from .providers.base import ProviderError

STAGES = ["research", "script", "characters", "images", "video", "voice", "edit", "thumbnail", "seo", "review"]
PAID_STAGES = {"research", "script", "images", "video", "voice", "thumbnail", "seo"}


class NeedsApproval(Exception):
    def __init__(self, estimate: dict):
        super().__init__(f"Estimated cost ${estimate['total_usd']:.2f} needs your approval")
        self.estimate = estimate


class Cancelled(Exception):
    pass


def _aspect(p: dict) -> str:
    return "9:16" if p["format"] == "short" else "16:9"


def _log(pid, stage, msg, level="info"):
    db.log_event(pid, stage, msg, level)


# ---------------- stages ----------------
def stage_research(p: dict, **kw) -> None:
    if p.get("idea") and p["idea"].get("title"):
        return
    pool = [i for i in research.saved_ideas(50, unused_only=True) if i.get("format", p["format"]) == p["format"]]
    if not pool:
        pool = research.generate_ideas(10, fmt=p["format"], topic_hint=kw.get("topic_hint", ""))["ideas"]
    best = max(pool, key=lambda i: i.get("total_score", 0))
    research.mark_used(best["id"])
    p["idea"] = best
    p["title"] = best["title"]
    projects.update_row(p["id"], title=best["title"])
    _log(p["id"], "research", f"Picked idea #{best['id']}: {best['title']} (score {best.get('total_score')})")


def stage_script(p: dict, force: bool = False, **kw) -> None:
    if p.get("script") and not force:
        return
    if not p.get("idea"):
        raise ValueError("No idea selected for this project. Run research or pick an idea.")
    s = scriptgen.generate(p["idea"], p["format"], project_id=p["id"], notes=kw.get("notes", ""))
    p["script"] = s
    p["title"] = s["title"]
    projects.update_row(p["id"], title=s["title"])
    (projects.project_dir(p["id"]) / "script.md").write_text(scriptgen.to_text(s), encoding="utf-8")
    best = (s.get("hook_scores") or [{}])[0]
    _log(p["id"], "script", f"Script ready: {len(s['scenes'])} scenes, ~{s['estimated_seconds']}s, "
         f"hook {best.get('verdict')} {best.get('band')} ({s.get('source')})")


def stage_characters(p: dict, **kw) -> None:
    prov = db.get_setting("providers")["image"]
    from . import config
    cdir = config.DATA_DIR / "characters"
    cdir.mkdir(parents=True, exist_ok=True)
    for cid in (p.get("script") or {}).get("characters", []):
        c = characters.lookup(cid)
        if not c or c.get("species") == "narrator":
            continue
        ref = c.get("reference_image")
        if ref and (cdir / ref).exists() and c.get("reference_provider") == prov:
            continue
        out = cdir / f"{c['id']}_{prov}.png"
        image_p.generate(prov, characters.image_prompt(c), out, "16:9", c["seed"],
                         {"scene": {"setting": "studio", "n": "ref", "dialogue": []}, "cast": [c], "clean": True})
        c["reference_image"], c["reference_provider"] = out.name, prov
        characters.save(c)
        _log(p["id"], "characters", f"Reference sheet for {c['name']} ({prov})")


def scene_prompt(scene: dict, style: dict) -> tuple[str, list[dict]]:
    text = scene.get("visual", "")
    cast = []
    for c in characters.all_characters():
        if c.get("species") == "narrator" or not c.get("visual_dna"):
            continue
        if re.search(rf"\b{re.escape(c['name'])}\b", text, re.I) or any(d["character"] == c["id"] for d in scene.get("dialogue", [])):
            cast.append(c)
            text = re.sub(rf"\b{re.escape(c['name'])}\b", f"{c['name']} ({c['visual_dna']})", text, count=1, flags=re.I)
    missing = [c for c in cast if c["visual_dna"] not in text]
    if missing:
        text += ". Also in frame: " + "; ".join(f"{c['name']} ({c['visual_dna']})" for c in missing)
    prompt = (f"{text}. Setting: {scene.get('setting', '')}. Camera: {scene.get('camera', '')}. "
              f"{style['art_style']}. Single cinematic frame, no text, no speech bubbles. Avoid: {style.get('negative', '')}.")
    return prompt, cast


def stage_images(p: dict, force: bool = False, progress=None, **kw) -> None:
    prov = db.get_setting("providers")["image"]
    style = db.get_setting("style")
    pid = p["id"]
    scenes = p["script"]["scenes"]
    base_seed = zlib.crc32(pid.encode()) % 1_000_000
    for i, sc in enumerate(scenes):
        key = str(sc["n"])
        if key in p["assets"]["images"] and not force and projects.abspath(pid, p["assets"]["images"][key]).exists():
            continue
        if progress:
            progress(i / len(scenes), f"Image {i + 1}/{len(scenes)} via {prov}")
        prompt, cast = scene_prompt(sc, style)
        seed = (cast[0]["seed"] if cast else base_seed) + sc["n"]
        out = projects.project_dir(pid) / "images" / f"scene{sc['n']:02d}.png"
        image_p.generate(prov, prompt, out, _aspect(p), seed, {"scene": sc, "cast": cast})
        p["assets"]["images"][key] = projects.rel(pid, out)
        p["assets"].setdefault("prompts", {})[key] = prompt
        projects.save(p)
    # Free storyboard frames: also draw native frames for any extra export aspect (no blur padding).
    if prov == "storyboard":
        for asp in (p.get("export_aspects") or []):
            if asp == _aspect(p):
                continue
            alt = p["assets"].setdefault("images_alt", {}).setdefault(asp, {})
            for sc in scenes:
                prompt, cast = scene_prompt(sc, style)
                out = projects.project_dir(pid) / "images" / f"scene{sc['n']:02d}_{asp.replace(':', 'x')}.png"
                image_p.generate(prov, prompt, out, asp, base_seed + sc["n"], {"scene": sc, "cast": cast})
                alt[str(sc["n"])] = projects.rel(pid, out)
    # clean thumbnail background (first scene, no labels)
    first = scenes[0]
    prompt, cast = scene_prompt(first, style)
    out = projects.project_dir(pid) / "images" / "thumb_bg.png"
    if force or not out.exists():
        image_p.generate(prov, prompt + " Close-up, exaggerated expressions, bold composition for a YouTube thumbnail.",
                         out, "16:9", base_seed + 999, {"scene": first, "cast": cast, "clean": True})
    p["assets"]["images"]["thumb"] = projects.rel(pid, out)
    _log(pid, "images", f"{len(scenes)} scene images ready ({prov})")


def stage_video(p: dict, force: bool = False, progress=None, **kw) -> None:
    prov = db.get_setting("providers")["video"]
    pid = p["id"]
    if prov == "kenburns":
        p["assets"]["clips"] = {}
        _log(pid, "video", "Using Ken Burns motion on stills (free). Select an AI video provider for animated clips.")
        return
    opts = db.get_setting("provider_options")
    limit = int(opts.get("max_ai_video_scenes", 6))
    secs = int(opts.get("video_clip_seconds", 5))
    scenes = p["script"]["scenes"][:limit]
    for i, sc in enumerate(scenes):
        key = str(sc["n"])
        if key in p["assets"]["clips"] and not force:
            continue
        if progress:
            progress(i / len(scenes), f"Video clip {i + 1}/{len(scenes)} via {prov} (this can take minutes)")
        img = p["assets"]["images"].get(key)
        prompt = p["assets"].get("prompts", {}).get(key) or sc["visual"]
        prompt = f"{sc.get('action', '')} {sc.get('camera', '')}. {prompt}"
        out = projects.project_dir(pid) / "video" / f"scene{sc['n']:02d}.mp4"
        try:
            video_p.generate(prov, prompt, projects.abspath(pid, img) if img else None, out, _aspect(p), secs)
        except ProviderError as e:
            _log(pid, "video", f"Scene {sc['n']} clip failed ({e}); falling back to Ken Burns for this scene", "warning")
            continue
        p["assets"]["clips"][key] = projects.rel(pid, out)
        db.log_cost(pid, prov, "video", secs, secs * costs.pricing()["video"].get(prov, 0))
        projects.save(p)
    _log(pid, "video", f"{len(p['assets']['clips'])} AI clips ready ({prov})")


def stage_voice(p: dict, force: bool = False, progress=None, **kw) -> None:
    prov = db.get_setting("providers")["tts"]
    pid = p["id"]
    lines = [(sc, i, d) for sc in p["script"]["scenes"] for i, d in enumerate(sc["dialogue"])]
    voice = p["assets"].setdefault("voice", {})
    if force or p["assets"].get("voice_provider") != prov:
        voice.clear()
    chars = 0
    for k, (sc, i, d) in enumerate(lines):
        key = f"{sc['n']}-{i}"
        if key in voice and projects.abspath(pid, voice[key]["file"]).exists():
            continue
        if progress:
            progress(k / max(1, len(lines)), f"Voice line {k + 1}/{len(lines)} via {prov}")
        c = characters.lookup(d["character"]) or characters.lookup("narrator")
        base = projects.project_dir(pid) / "audio" / f"s{sc['n']:02d}_l{i:02d}_{c['id']}"
        raw = tts_p.synthesize(prov, d["line"], c, base, d.get("emotion", ""), d.get("delivery", ""))
        wav = base.with_name(base.name + "_norm.wav")
        if prov == "silent":
            ffmpeg.to_wav(raw, wav)
        else:  # trim leading/trailing silence so timing is tight
            ffmpeg.run(["-i", raw, "-af", "silenceremove=start_periods=1:start_threshold=-50dB,areverse,"
                        "silenceremove=start_periods=1:start_threshold=-50dB,areverse,apad=pad_dur=0.05",
                        "-ac", "1", "-ar", "44100", "-sample_fmt", "s16", wav], what="normalise voice line")
        dur = ffmpeg.wav_duration(wav)
        if dur < 0.2:
            raise ProviderError(f"Voice line {key} came back empty from {prov}")
        voice[key] = {"file": projects.rel(pid, wav), "duration": round(dur, 3), "character": c["id"]}
        chars += len(d["line"])
        projects.save(p)
    p["assets"]["voice_provider"] = prov
    if chars:
        db.log_cost(pid, prov, "tts", chars, chars / 1000 * costs.pricing()["tts"].get(prov, 0))
    _log(pid, "voice", f"{len(voice)} voice lines ready ({prov})")


def stage_edit(p: dict, progress=None, **kw) -> None:
    aspects = kw.get("aspects") or p.get("export_aspects") or [_aspect(p)]
    result = editor.render(p, aspects, progress=progress)
    p["render"] = result
    outs = ", ".join(f"{a}: {o['duration']}s {o['size_mb']}MB" for a, o in result["outputs"].items())
    _log(p["id"], "edit", f"Rendered {outs}")


def stage_thumbnail(p: dict, **kw) -> None:
    pid = p["id"]
    bg = thumbnail.best_scene_image(p)
    text = kw.get("thumbnail_text") or (p.get("seo") or {}).get("thumbnail_text") or \
        next((s["on_screen_text"] for s in p["script"]["scenes"] if s.get("on_screen_text")), "") or "WAIT WHAT"
    res = thumbnail.make(projects.abspath(pid, bg) if bg else None, text, projects.project_dir(pid) / "thumbnail",
                         title=(p.get("seo") or {}).get("title") or p["title"], style=kw.get("thumbnail_style", "pop"))
    res["png"], res["jpg"] = projects.rel(pid, res["png"]), projects.rel(pid, res["jpg"])
    p["thumbnail"] = res
    _log(pid, "thumbnail", f"Thumbnail '{res['text']}' ({res['size_kb']} KB)")


def stage_seo(p: dict, **kw) -> None:
    p["seo"] = seo.build(p)
    # keep thumbnail text in sync with SEO suggestion (rebuild if it differs)
    if p.get("thumbnail") and p["seo"].get("thumbnail_text") and p["thumbnail"].get("text") != p["seo"]["thumbnail_text"].upper()[:40]:
        stage_thumbnail(p, thumbnail_text=p["seo"]["thumbnail_text"])
    _log(p["id"], "seo", f"SEO ready: '{p['seo']['title']}' ({len(p['seo']['tags'])} tags, {p['seo']['source']})")


def stage_review(p: dict, **kw) -> None:
    projects.update_row(p["id"], status="ready_for_review")
    _log(p["id"], "review", "Ready for your review. Watch it, then Approve (uploads stay private until you say otherwise).")


FUNCS = {"research": stage_research, "script": stage_script, "characters": stage_characters, "images": stage_images,
         "video": stage_video, "voice": stage_voice, "edit": stage_edit, "thumbnail": stage_thumbnail,
         "seo": stage_seo, "review": stage_review}


# ---------------- runner ----------------
def check_costs(p: dict, stages: list[str]) -> dict:
    est = costs.estimate(p, stages=[s for s in stages if s in PAID_STAGES])
    p["estimate"] = est
    projects.save(p)
    projects.update_row(p["id"], est_cost=est["total_usd"])
    row = projects.row(p["id"])
    if costs.over_budget(est["total_usd"]) and costs.needs_approval(row, est["total_usd"]):
        est["over_budget"] = True
    if costs.needs_approval(row, est["total_usd"]):
        raise NeedsApproval(est)
    return est


def approve_cost(pid: str, amount: float | None = None) -> dict:
    p = projects.load(pid)
    est = p.get("estimate") or costs.estimate(p)
    amt = float(amount if amount is not None else est["total_usd"])
    projects.update_row(pid, cost_approved=amt, status="draft")
    _log(pid, "costs", f"You approved spending up to ${amt:.2f} for this video")
    return {"approved_usd": amt}


def run(pid: str, stages: list[str] | None = None, progress=None, cancel=None, force: list[str] | None = None,
        **kw) -> dict:
    stages = stages or [s for s in STAGES]
    bad = [s for s in stages if s not in FUNCS]
    if bad:
        raise ValueError(f"unknown stage(s): {bad}. Valid: {STAGES}")
    stages = [s for s in STAGES if s in stages]  # canonical order
    force = force or []
    p = projects.load(pid)
    say = progress or (lambda *_: None)
    projects.update_row(pid, status="running", error=None)
    try:
        check_costs(p, stages)  # nothing paid runs before this passes
        for i, st in enumerate(stages):
            if cancel and cancel():
                raise Cancelled()
            frac = i / len(stages)
            say(frac, f"{st}...")
            projects.update_row(pid, stage=st)
            t0 = time.time()

            def sub(f, msg, _i=i):
                say((_i + max(0.0, min(1.0, f))) / len(stages), msg)

            FUNCS[st](p, force=st in force, progress=sub, **kw)
            p["stages"][st] = {"done": time.time(), "seconds": round(time.time() - t0, 1)}
            projects.save(p)
            if st == "script":  # real scene count is known now - re-check the estimate
                check_costs(p, stages[i + 1:])
        if "review" not in stages:
            projects.update_row(pid, status="draft")
        say(1.0, "Done")
        return {"ok": True, "project": pid}
    except NeedsApproval as e:
        projects.update_row(pid, status="awaiting_cost_approval")
        _log(pid, "costs", f"Paused: estimated ${e.estimate['total_usd']:.2f} with paid providers. Approve to continue.",
             "warning")
        return {"ok": False, "needs_approval": True, "estimate": e.estimate}
    except Cancelled:
        projects.update_row(pid, status="draft", error="cancelled")
        _log(pid, "pipeline", "Cancelled by user", "warning")
        return {"ok": False, "cancelled": True}
    except Exception as e:
        projects.save(p)
        msg = f"{type(e).__name__}: {e}"
        projects.update_row(pid, status="failed", error=msg)
        _log(pid, projects.row(pid).get("stage") or "pipeline", msg, "error")
        db.log_event(pid, "trace", traceback.format_exc()[-3000:], "debug")
        raise


def create_todays_video(fmt: str | None = None, topic_hint: str = "", progress=None, cancel=None) -> dict:
    """End-to-end: topic -> script -> scenes -> visuals -> voices -> edit -> thumbnail -> SEO -> review.
    Stops before upload; uploading needs your approval."""
    fmt = fmt or db.get_setting("channel")["default_format"]
    p = projects.create("Today's video", fmt)
    try:
        res = run(p["id"], STAGES, progress=progress, cancel=cancel, topic_hint=topic_hint)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "project": p["id"], "error": str(e)}
    res["project"] = p["id"]
    return res


def doctor() -> dict:
    """Environment check used by `ytauto doctor` and the dashboard Overview."""
    from . import config, youtube
    checks = []

    def add(name, ok, detail, required=True):
        checks.append({"name": name, "ok": bool(ok), "detail": detail, "required": required})

    try:
        add("FFmpeg", True, ffmpeg.version())
        add("FFmpeg libass (subtitles)", ffmpeg.has_filter("ass"), "burned-in subtitles", required=False)
    except Exception as e:  # noqa: BLE001
        add("FFmpeg", False, str(e))
    add("Database", config.DB_PATH.exists() or True, str(config.DB_PATH))
    try:
        add("LLM provider", True, f"{llm.active_provider()} ({llm.active_model()})")
    except llm.LLMError as e:
        add("LLM provider", False, str(e))
    prov = db.get_setting("providers")
    for kind, mapping in (("image", {"openai": "OPENAI_API_KEY", "stability": "STABILITY_API_KEY", "replicate": "REPLICATE_API_TOKEN"}),
                          ("video", {"runway": "RUNWAY_API_KEY", "luma": "LUMA_API_KEY", "replicate": "REPLICATE_API_TOKEN"}),
                          ("tts", {"elevenlabs": "ELEVENLABS_API_KEY", "openai": "OPENAI_API_KEY"})):
        sel = prov.get(kind)
        key = mapping.get(sel)
        add(f"{kind} provider", (not key) or config.has_secret(key),
            f"{sel}" + (f" (needs {key})" if key and not config.has_secret(key) else ""))
    yts = youtube.status()
    add("YouTube OAuth client file", yts["client_secrets_found"], yts["client_secrets_path"], required=False)
    add("YouTube connected", yts["connected"], (yts.get("channel") or {}).get("title", "not connected"), required=False)
    add("YouTube research key", config.has_secret("YOUTUBE_API_KEY"), "optional trend signals", required=False)
    return {"ok": all(c["ok"] for c in checks if c["required"]), "checks": checks}
