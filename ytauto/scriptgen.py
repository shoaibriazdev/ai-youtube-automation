"""STEP 2 - Script generation: hook in the first 3 seconds, scene-by-scene, dialogue with delivery
(voiceover) notes and sound-effect cues. Hooks are scored with the original hookscore.py."""
from __future__ import annotations

from . import characters, db, legacy, llm, offline_writer
from .audio import SFX_NAMES

SCENE_SCHEMA = {
    "type": "object",
    "properties": {
        "setting": {"type": "string"},
        "visual": {"type": "string", "description": "What the frame shows. Describe characters by name only."},
        "camera": {"type": "string"},
        "action": {"type": "string"},
        "on_screen_text": {"type": "string"},
        "dialogue": {"type": "array", "items": {
            "type": "object",
            "properties": {"character": {"type": "string"}, "line": {"type": "string"},
                           "emotion": {"type": "string"}, "delivery": {"type": "string"}},
            "required": ["character", "line", "emotion", "delivery"], "additionalProperties": False}},
        "sfx": {"type": "array", "items": {
            "type": "object",
            "properties": {"name": {"type": "string", "enum": SFX_NAMES},
                           "cue": {"type": "string", "description": "start | end | after_line:N"}},
            "required": ["name", "cue"], "additionalProperties": False}},
    },
    "required": ["setting", "visual", "camera", "action", "on_screen_text", "dialogue", "sfx"],
    "additionalProperties": False,
}

SCRIPT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"}, "logline": {"type": "string"},
        "hook_options": {"type": "array", "items": {"type": "string"}},
        "hook": {"type": "string"}, "target_seconds": {"type": "integer"},
        "characters": {"type": "array", "items": {"type": "string"}},
        "music_mood": {"type": "string", "enum": ["playful", "sneaky", "bouncy", "dramatic", "chill"]},
        "ending_twist": {"type": "string"},
        "scenes": {"type": "array", "items": SCENE_SCHEMA},
    },
    "required": ["title", "logline", "hook_options", "hook", "target_seconds", "characters", "music_mood",
                 "ending_twist", "scenes"],
    "additionalProperties": False,
}


def generate(idea: dict, fmt: str = "short", project_id: str | None = None, notes: str = "") -> dict:
    provider = llm.active_provider()
    channel = db.get_setting("channel")
    if provider == "anthropic":
        cast_ids = list(dict.fromkeys((idea.get("characters") or []) + ["narrator"]))
        shape = ("YouTube Short (vertical 9:16): 5-7 scenes, 30-55 seconds of dialogue total, one joke beat per scene"
                 if fmt == "short" else
                 "horizontal 16:9 video: 10-16 scenes, 2-4 minutes, a clear beginning/middle/end with escalating gags")
        prompt = f"""Write the full production script for this ORIGINAL animated comedy video.

Idea: {idea.get('title')}
Premise: {idea.get('premise')}
Proposed hook: {idea.get('hook', '')}
Twist: {idea.get('twist', '')}
Format: {shape}
Channel tone: {channel['tone']}. Audience: {channel['audience']}.
{('Creator notes: ' + notes) if notes else ''}

Cast (use these exact ids in dialogue.character; "narrator" is available for voice-over):
{characters.describe_cast(cast_ids)}

Requirements:
- hook_options: FIVE different spoken opening lines (9-24 words), each grabbing attention in the first 3 seconds
  and confirming what the title promises. Set "hook" to the best one; scene 1's first line must be that hook.
- Funny, character-driven dialogue, short lines (max ~20 words each) that are easy for TTS to deliver.
- delivery: voice-over direction for the actor (pace, volume, attitude). emotion: one word.
- visual: a concrete description of the frame for an image generator (setting, poses, expressions, props).
  Refer to characters by NAME only - their exact appearance is injected automatically.
- sfx: 0-2 cues per scene chosen from the allowed list, cue = start | end | after_line:N (1-based line index).
- on_screen_text: max 3 words or empty.
- End on an unexpected twist, then a quick button line.
- Clean, family-friendly, original. No real people, brands or copyrighted characters."""
        data = llm.generate_json(prompt, SCRIPT_SCHEMA, project_id=project_id, stage="script")
        data["source"] = "claude"
    else:
        data = offline_writer.script(idea, characters.lookup, fmt)
        data["hook_options"] = idea.get("hook_options") or [data["hook"]]
    data["format"] = fmt
    return finalize(data)


def finalize(data: dict) -> dict:
    """Normalise a script (from Claude, offline writer or user edits) and attach scores."""
    scenes = data.get("scenes") or []
    if not scenes:
        raise ValueError("script has no scenes")
    for i, s in enumerate(scenes, 1):
        s["n"] = i
        s.setdefault("on_screen_text", "")
        s.setdefault("sfx", [])
        s.setdefault("camera", "")
        s.setdefault("action", "")
        s["sfx"] = [x for x in s["sfx"] if x.get("name") in SFX_NAMES]
        clean = []
        for d in s.get("dialogue") or []:
            if not (d.get("line") or "").strip():
                continue
            c = characters.lookup(d.get("character", "")) or characters.lookup("narrator")
            d["character"] = c["id"] if c else "narrator"
            d.setdefault("emotion", "neutral")
            d.setdefault("delivery", "")
            clean.append(d)
        s["dialogue"] = clean
    used = sorted({d["character"] for s in scenes for d in s["dialogue"]})
    data["characters"] = used
    opts = data.get("hook_options") or [data.get("hook", "")]
    data["hook_scores"] = sorted([legacy.score_hook(h) for h in opts if h], key=lambda h: -h["verdict"])
    words = sum(len(d["line"].split()) for s in scenes for d in s["dialogue"])
    data["word_count"] = words
    data["estimated_seconds"] = round(words / 2.6 + len(scenes) * 0.8, 1)  # ~155 wpm comedic pace + beats
    return data


def to_text(script: dict) -> str:
    """Human-readable screenplay (saved as script.md next to the project)."""
    out = [f"# {script['title']}", "", f"_{script.get('logline', '')}_", "",
           f"**Hook (0-3s):** {script.get('hook', '')}", ""]
    for h in script.get("hook_scores", [])[:3]:
        out.append(f"- hookscore {h['verdict']} {h['band']} ({h['formula']}): {h['hook']}")
    out.append("")
    for s in script["scenes"]:
        out += [f"## Scene {s['n']} - {s['setting']}", f"[ON SCREEN: {s['visual']}]",
                f"[CAMERA: {s.get('camera', '')}]  [ACTION: {s.get('action', '')}]"]
        if s.get("on_screen_text"):
            out.append(f"[TEXT: {s['on_screen_text']}]")
        for d in s["dialogue"]:
            c = characters.lookup(d["character"])
            out.append(f"**{(c or {}).get('name', d['character']).upper()}** ({d['emotion']}; {d['delivery']}): {d['line']}")
        for x in s.get("sfx", []):
            out.append(f"[SFX: {x['name']} @ {x['cue']}]")
        out.append("")
    out.append(f"Twist: {script.get('ending_twist', '')}")
    out.append(f"Estimated runtime: {script.get('estimated_seconds')}s ({script.get('word_count')} words)")
    return "\n".join(out)
