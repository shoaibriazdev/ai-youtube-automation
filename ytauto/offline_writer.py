"""Offline template writer - free, no API key.

It assembles ORIGINAL premises and scripts from hand-written comedy building blocks (situations,
schemes, complications, twists) and the channel's own characters. It is deterministic for a seed so
results are reproducible. Quality is decent for testing the pipeline and for idea sparks, but it is
not a substitute for Claude - the dashboard labels its output as "offline template".
"""
from __future__ import annotations

import random

SITUATIONS = [
    # (setting, situation, visual)
    ("kitchen", "the food bowl is {empty} for {n} whole minutes", "a cozy kitchen with an empty pet bowl in a spotlight"),
    ("living room", "the humans bought a robot vacuum", "a sunny living room with a small round robot vacuum"),
    ("office", "the office coffee machine got replaced by a smart fridge that talks", "an open-plan office with a shiny talking fridge"),
    ("office", "Monday's meeting is about scheduling more meetings", "a meeting room with a giant whiteboard full of arrows"),
    ("vet clinic", "it is vet day and nobody said the word 'vet' out loud", "a bright vet waiting room with a scale"),
    ("backyard", "a squirrel has been seen wearing tiny sunglasses", "a sunny backyard with a suspicious oak tree"),
    ("grocery store", "the family left the pets in the car with the window cracked and a shopping list", "a supermarket parking lot seen through a car window"),
    ("bedroom", "the human is trying to work from home on a video call", "a messy home office with a laptop on a video call"),
    ("park", "the dog park introduced a talent show", "a dog park with a tiny wooden stage and bunting"),
    ("office", "the printer is jammed and everyone is too scared to touch it", "a dim office corner with a menacing printer"),
    ("living room", "the humans bought a new couch and it is clearly a throne", "a living room with a brand-new velvet couch"),
    ("kitchen", "someone ate the last slice of pizza and there are no witnesses", "a kitchen at night with an empty pizza box"),
    ("road trip", "the car GPS starts giving life advice", "a minivan interior on a highway at sunset"),
    ("office", "the team must pick a password everyone can remember", "an office desk with sticky notes everywhere"),
    ("bathroom", "bath time has been announced", "a bathroom with a bubbly bathtub and rubber duck"),
]

SCHEMES = [
    "launch a top-secret undercover operation", "file a formal complaint with management",
    "start a podcast about it", "hold a dramatic courtroom trial", "build a trap out of cardboard",
    "write a strongly worded letter", "pretend to be someone else entirely", "train for it like an athlete",
    "form a union", "consult a fortune-telling goldfish",
]

COMPLICATIONS = [
    "the plan works way too well", "the evidence is stuck to their own face",
    "the human is watching the whole time", "they forget the plan halfway through",
    "the disguise is just a hat", "the smart speaker starts repeating everything",
]

TWISTS = [
    "the culprit was the narrator all along", "the 'monster' was a birthday surprise for them",
    "it was a dream - inside the robot vacuum's dream", "the humans were doing the exact same scheme in the next room",
    "the goldfish was the real boss the entire time", "the problem solved itself while they argued",
    "they were on the wrong house the entire time", "the security camera footage shows something even weirder",
]

HOOKS = [
    "{a}, we have a code red. {Situation}.",
    "Nobody panic, but {situation}.",
    "You are not going to believe this: {situation}.",
    "{b}, look at me. {Situation}. This changes everything.",
    "Breaking news: {situation}. And yes, I have a plan.",
    "Stop what you're doing. {Situation}, and we have one minute.",
]

LINES = {
    "react": ["Wait. WHAT?", "You're telling me this NOW?", "Okay. Okay. Deep breaths.", "This is the worst day of my life. Again.",
              "I have so many questions and zero snacks."],
    "plan": ["Here's the plan: we {scheme}.", "There's only one option. We {scheme}.", "Simple. We {scheme}. What could go wrong?"],
    "doubt": ["That is the worst plan I've ever heard. I'm in.", "Do we have a backup plan?", "Last time we tried that I got stuck in a lampshade."],
    "complication": ["Uh... small problem. {Complication}.", "Don't look now, but {complication}.", "So, funny thing... {complication}."],
    "twist_setup": ["Wait. Listen. Do you hear that?", "Hold on. Something isn't right.", "Everybody freeze."],
    "twist": ["Turns out {twist}.", "Plot twist: {twist}.", "And that's when they realized {twist}."],
    "button": ["I'm going to need a nap after this.", "Same time tomorrow?", "Don't. Tell. Anyone.", "Five stars. Would panic again."],
}

TITLE_TEMPLATES = [
    "{a} Finds Out {situation_title}",
    "When {situation_title} ({a} vs {b})",
    "{a} and {b} Try to {scheme_title}",
    "The Day {situation_title}",
    "{a} Has ONE Job: {scheme_title}",
]

SFX = ["boing", "pop", "whoosh", "ding", "rimshot", "record_scratch", "cartoon_slip", "crickets", "gasp_sting", "tada", "buzzer", "splat"]


def _cap(s: str) -> str:
    return " ".join((w[0].upper() + w[1:]) if w.lower() not in ("a", "the", "of", "to", "and", "for", "in", "on") else w
                    for w in s.split())


def _short(s: str, n: int) -> str:
    """Trim to n chars at a word boundary, dropping dangling small words."""
    if len(s) <= n:
        return s
    words = s[:n + 1].split()[:-1]
    while words and words[-1].lower() in ("a", "the", "of", "to", "and", "for", "in", "on", "with", "that", "is"):
        words.pop()
    return " ".join(words)


def _pick_cast(r: random.Random, cast: list[dict]) -> tuple[dict, dict]:
    pool = [c for c in cast if c.get("species") != "narrator"] or cast
    a = r.choice(pool)
    rest = [c for c in pool if c["id"] != a["id"]] or pool
    return a, r.choice(rest)


def make_idea(r: random.Random, cast: list[dict], fmt: str = "short") -> dict:
    setting, situation, visual = r.choice(SITUATIONS)
    a, b = _pick_cast(r, cast)
    n = r.choice([3, 4, 7, 12])
    situation = situation.format(empty=r.choice(["EMPTY", "empty", "half empty"]), n=n)
    scheme, comp, twist = r.choice(SCHEMES), r.choice(COMPLICATIONS), r.choice(TWISTS)
    title = r.choice(TITLE_TEMPLATES).format(
        a=a["name"], b=b["name"], situation_title=_short(_cap(situation), 48), scheme_title=_short(_cap(scheme), 40))
    from .legacy import score_hook
    options = [h.format(a=a["name"], b=b["name"], situation=situation, Situation=situation[0].upper() + situation[1:])
               for h in r.sample(HOOKS, 3)]
    hook = max(options, key=lambda h: score_hook(h)["verdict"])
    return {"title": title[:95], "premise": f"{a['name']} and {b['name']} discover that {situation}. "
            f"They {scheme}, but {comp}. Twist: {twist}.",
            "hook": hook, "hook_options": options, "characters": [a["id"], b["id"]], "setting": setting, "visual": visual,
            "scheme": scheme, "complication": comp, "twist": twist, "situation": situation,
            "format": fmt, "source": "offline template"}


def ideas(n: int, cast: list[dict], fmt: str, seed=None) -> list[dict]:
    r = random.Random(seed)
    out, seen = [], set()
    tries = 0
    while len(out) < n and tries < n * 20:
        tries += 1
        idea = make_idea(r, cast, fmt)
        if idea["title"] in seen:
            continue
        seen.add(idea["title"])
        out.append(idea)
    return out


def script(idea: dict, cast_lookup, fmt: str, seed=None) -> dict:
    r = random.Random(seed if seed is not None else idea.get("title"))
    ids = idea.get("characters") or []
    a = cast_lookup(ids[0]) if ids else None
    b = cast_lookup(ids[1]) if len(ids) > 1 else None
    if not a or not b:
        raise ValueError("offline writer needs two characters from the library")
    situation = idea.get("situation") or idea.get("premise", "something strange is happening")
    scheme = idea.get("scheme") or r.choice(SCHEMES)
    comp = idea.get("complication") or r.choice(COMPLICATIONS)
    twist = idea.get("twist") or r.choice(TWISTS)
    setting = idea.get("setting") or "living room"
    base_visual = idea.get("visual") or f"a colorful cartoon {setting}"
    f = lambda key: r.choice(LINES[key]).format(scheme=scheme, complication=comp, twist=twist,
                                                Complication=comp[0].upper() + comp[1:])
    A, B = a["name"], b["name"]
    scenes = [
        {"setting": setting, "visual": f"{base_visual}, {A} staring in shock, {B} in the background",
         "camera": "fast push-in on {}'s face".format(A), "action": f"{A} bursts into frame, panicking.",
         "on_screen_text": "CODE RED", "dialogue": [{"character": a["id"], "line": idea.get("hook") or f"{situation}!", "emotion": "panicked", "delivery": "fast, loud, urgent"}],
         "sfx": [{"name": "record_scratch", "cue": "start"}]},
        {"setting": setting, "visual": f"{base_visual}, {B} reacting with wide eyes next to {A}",
         "camera": "two-shot, slight shake", "action": f"{B} reacts.",
         "on_screen_text": "", "dialogue": [{"character": b["id"], "line": f("react"), "emotion": "shocked", "delivery": "comic disbelief"},
                                            {"character": a["id"], "line": f("plan"), "emotion": "determined", "delivery": "dramatic whisper"}],
         "sfx": [{"name": "gasp_sting", "cue": "start"}]},
        {"setting": setting, "visual": f"{base_visual}, {A} and {B} huddled over a crayon-drawn battle plan",
         "camera": "top-down shot of the plan", "action": "They plan with absurd seriousness.",
         "on_screen_text": "THE PLAN", "dialogue": [{"character": b["id"], "line": f("doubt"), "emotion": "nervous", "delivery": "hesitant, then committed"}],
         "sfx": [{"name": "whoosh", "cue": "start"}, {"name": "ding", "cue": "end"}]},
        {"setting": setting, "visual": f"{base_visual}, chaos: {A} tangled in a mess while {B} freezes",
         "camera": "wide shot, quick zoom", "action": "The plan goes sideways.",
         "on_screen_text": "", "dialogue": [{"character": a["id"], "line": f("complication"), "emotion": "embarrassed", "delivery": "quiet, guilty"}],
         "sfx": [{"name": "cartoon_slip", "cue": "start"}, {"name": "boing", "cue": "end"}]},
        {"setting": setting, "visual": f"{base_visual}, dramatic lighting, {B} slowly turning around",
         "camera": "slow dolly-in, dramatic", "action": "Everything stops.",
         "on_screen_text": "WAIT...", "dialogue": [{"character": b["id"], "line": f("twist_setup"), "emotion": "suspicious", "delivery": "slow, suspenseful"},
                                                   {"character": "narrator", "line": f("twist"), "emotion": "wry", "delivery": "deadpan"}],
         "sfx": [{"name": "crickets", "cue": "start"}, {"name": "tada", "cue": "end"}]},
        {"setting": setting, "visual": f"{base_visual}, {A} and {B} looking at the camera, deadpan",
         "camera": "static close-up, both look at camera", "action": "The button.",
         "on_screen_text": "", "dialogue": [{"character": a["id"], "line": a.get("catchphrase") or f("button"), "emotion": "deadpan", "delivery": "flat, perfect comic timing"},
                                            {"character": b["id"], "line": f("button"), "emotion": "tired", "delivery": "sigh"}],
         "sfx": [{"name": "rimshot", "cue": "end"}]},
    ]
    if fmt == "long":
        # Long form: an extra escalation round before the twist.
        scenes.insert(4, {"setting": setting, "visual": f"{base_visual}, {A} and {B} try plan B with cardboard disguises",
                          "camera": "handheld, comedic", "action": "Plan B is worse.", "on_screen_text": "PLAN B",
                          "dialogue": [{"character": b["id"], "line": "Plan B. Same as plan A, but with hats.", "emotion": "proud", "delivery": "confident"},
                                       {"character": a["id"], "line": f("react"), "emotion": "exasperated", "delivery": "loud"}],
                          "sfx": [{"name": "pop", "cue": "start"}, {"name": "buzzer", "cue": "end"}]})
    for i, s in enumerate(scenes, 1):
        s["n"] = i
    words = sum(len(l["line"].split()) for s in scenes for l in s["dialogue"])
    return {"title": idea.get("title", "Untitled"), "logline": idea.get("premise", ""), "hook": idea.get("hook", ""),
            "format": fmt, "target_seconds": int(words / 2.6 + len(scenes) * 1.2), "characters": sorted({a["id"], b["id"], "narrator"}),
            "music_mood": r.choice(["playful", "sneaky", "bouncy"]), "ending_twist": twist, "scenes": scenes,
            "source": "offline template"}
