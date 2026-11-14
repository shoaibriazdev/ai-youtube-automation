"""Character library: original recurring characters with a fixed "visual DNA" for consistency.

Consistency strategy (works across providers):
  1. Every image prompt embeds the character's exact `visual_dna` sentence, unchanged, every time.
  2. Each character has a fixed integer `seed`; providers that accept seeds reuse it.
  3. A `reference_image` (the character sheet) is generated once and reused for image-to-video.
  4. Voices are mapped per TTS provider so a character always sounds the same.
"""
from __future__ import annotations

import json
import re
import time
import zlib

from . import db

DEFAULT_CHARACTERS = [
    {
        "id": "biscuit", "name": "Biscuit", "species": "cat",
        "personality": "Dramatic orange tabby who believes he is secretly royalty. Overreacts to everything, "
                       "speaks like a theatrical butler, deeply offended by empty food bowls.",
        "visual_dna": "a chubby orange tabby cat with cream belly, big green eyes, one bent left ear, "
                      "tiny gold crown-shaped tag on a purple collar",
        "palette": ["#F28C28", "#FFE3B3", "#7B3FA0"], "catchphrase": "This is an outrage. A delicious outrage.",
        "voice": {"edge": {"voice": "en-GB-RyanNeural", "rate": "+5%", "pitch": "+10Hz"},
                  "openai": {"voice": "fable", "instructions": "Pompous, theatrical, posh British cat."},
                  "elevenlabs": {"voice_id": ""}, "sapi": {"rate": 175}},
    },
    {
        "id": "waffles", "name": "Waffles", "species": "dog",
        "personality": "Overconfident fawn pug who thinks he is a genius detective. Always wrong, never doubts.",
        "visual_dna": "a round fawn pug with a black wrinkled face, huge brown eyes, curly tail, "
                      "red bandana with white polka dots",
        "palette": ["#D9B48F", "#2B2B2B", "#D62828"], "catchphrase": "Case closed. I think. What was the case?",
        "voice": {"edge": {"voice": "en-US-GuyNeural", "rate": "+12%", "pitch": "-8Hz"},
                  "openai": {"voice": "onyx", "instructions": "Gruff, overconfident, comic detective."},
                  "elevenlabs": {"voice_id": ""}, "sapi": {"rate": 190}},
    },
    {
        "id": "nugget", "name": "Nugget", "species": "dog",
        "personality": "Hyperactive golden retriever puppy. Everything is the best day ever. Easily distracted "
                       "by squirrels, mail carriers and his own tail.",
        "visual_dna": "a fluffy golden retriever puppy with floppy ears, tongue out, sparkling eyes, "
                      "bright blue collar with a bone-shaped tag",
        "palette": ["#F4C430", "#FFF5D6", "#1E88E5"], "catchphrase": "Best. Day. EVER!",
        "voice": {"edge": {"voice": "en-US-AnaNeural", "rate": "+18%", "pitch": "+20Hz"},
                  "openai": {"voice": "coral", "instructions": "Super excited, breathless puppy energy."},
                  "elevenlabs": {"voice_id": ""}, "sapi": {"rate": 210}},
    },
    {
        "id": "gary", "name": "Gary", "species": "human",
        "personality": "Exhausted office worker who just wants one quiet coffee. The calm straight man to chaos.",
        "visual_dna": "a lanky cartoon office worker in his 30s with messy brown hair, round glasses, beige "
                      "cardigan over a blue shirt, holding a white mug",
        "palette": ["#C8B593", "#4A6FA5", "#6B4226"], "catchphrase": "I just wanted coffee.",
        "voice": {"edge": {"voice": "en-US-ChristopherNeural", "rate": "-2%", "pitch": "+0Hz"},
                  "openai": {"voice": "echo", "instructions": "Tired, deadpan, sighing office worker."},
                  "elevenlabs": {"voice_id": ""}, "sapi": {"rate": 160}},
    },
    {
        "id": "boss_hoot", "name": "Boss Hoot", "species": "owl",
        "personality": "Owl office manager obsessed with meetings, buzzwords and spreadsheets. Means well.",
        "visual_dna": "a short round brown owl with huge amber eyes, tiny rectangular glasses and a "
                      "navy blue necktie, holding a clipboard",
        "palette": ["#8B5E3C", "#F2A900", "#1F3A93"], "catchphrase": "Let's circle back on that. Literally.",
        "voice": {"edge": {"voice": "en-US-EricNeural", "rate": "+3%", "pitch": "+6Hz"},
                  "openai": {"voice": "ash", "instructions": "Upbeat corporate manager, full of buzzwords."},
                  "elevenlabs": {"voice_id": ""}, "sapi": {"rate": 170}},
    },
    {
        "id": "narrator", "name": "Narrator", "species": "narrator",
        "personality": "Warm, slightly sarcastic storyteller voice.",
        "visual_dna": "", "palette": ["#333333", "#FFFFFF", "#FFCC00"], "catchphrase": "",
        "voice": {"edge": {"voice": "en-US-AndrewNeural", "rate": "+0%", "pitch": "+0Hz"},
                  "openai": {"voice": "sage", "instructions": "Warm, wry storyteller."},
                  "elevenlabs": {"voice_id": ""}, "sapi": {"rate": 170}},
    },
]

SPECIES = ["cat", "dog", "owl", "human", "hamster", "parrot", "rabbit", "raccoon", "narrator", "other"]


def _seed_for(cid: str) -> int:
    return zlib.crc32(cid.encode()) % 2_000_000_000


def normalize(c: dict) -> dict:
    c = dict(c)
    if not c.get("id"):
        c["id"] = re.sub(r"[^a-z0-9]+", "_", c.get("name", "character").lower()).strip("_") or "character"
    c.setdefault("species", "other")
    c.setdefault("personality", "")
    c.setdefault("visual_dna", "")
    c.setdefault("palette", ["#888888", "#FFFFFF", "#222222"])
    c.setdefault("catchphrase", "")
    c.setdefault("voice", {})
    c.setdefault("seed", _seed_for(c["id"]))
    c.setdefault("reference_image", None)
    c.setdefault("episodes", 0)
    return c


def ensure_defaults() -> None:
    if not db.query("SELECT id FROM characters LIMIT 1"):
        for c in DEFAULT_CHARACTERS:
            save(c)


def save(c: dict) -> dict:
    c = normalize(c)
    db.execute("INSERT INTO characters(id,data,updated) VALUES(?,?,?) "
               "ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated=excluded.updated",
               (c["id"], json.dumps(c), time.time()))
    return c


def get(cid: str) -> dict | None:
    rows = db.query("SELECT data FROM characters WHERE id=?", (cid,))
    return json.loads(rows[0]["data"]) if rows else None


def all_characters() -> list[dict]:
    ensure_defaults()
    return [json.loads(r["data"]) for r in db.query("SELECT data FROM characters ORDER BY id")]


def delete(cid: str) -> None:
    db.execute("DELETE FROM characters WHERE id=?", (cid,))


def lookup(name_or_id: str) -> dict | None:
    key = (name_or_id or "").strip().lower()
    for c in all_characters():
        if c["id"] == key or c["name"].lower() == key:
            return c
    return None


def image_prompt(c: dict, style: dict | None = None) -> str:
    style = style or db.get_setting("style")
    return (f"Character reference sheet of {c['visual_dna']}, full body, front view, neutral pose, "
            f"plain light background. {style['art_style']}.")


def describe_cast(ids: list[str]) -> str:
    lines = []
    for cid in ids:
        c = lookup(cid)
        if c:
            lines.append(f"- {c['name']} ({c['species']}): {c['personality']} Look: {c['visual_dna']}.")
    return "\n".join(lines)
