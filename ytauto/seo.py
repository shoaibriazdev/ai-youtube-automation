"""STEP 8 - YouTube SEO package: title, description, tags, hashtags, chapters, category, audience.

Honest by construction: titles are linted with the original title.py (length, vagueness, shouting),
tags are capped at YouTube's 500-character limit, chapters are only emitted when they satisfy
YouTube's rules (first at 0:00, at least 3, each >= 10 s), and nothing claims what the video lacks.
"""
from __future__ import annotations

import re

from . import characters, db, legacy, llm

SEO_SCHEMA = {
    "type": "object",
    "properties": {
        "titles": {"type": "array", "items": {"type": "string"}},
        "description_hook": {"type": "string", "description": "First two lines shown above '...more'"},
        "description_body": {"type": "string"},
        "tags": {"type": "array", "items": {"type": "string"}},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "search_queries": {"type": "array", "items": {"type": "string"}},
        "thumbnail_text": {"type": "string"},
    },
    "required": ["titles", "description_hook", "description_body", "tags", "hashtags", "search_queries",
                 "thumbnail_text"],
    "additionalProperties": False,
}

CATEGORIES = {"1": "Film & Animation", "23": "Comedy", "24": "Entertainment", "22": "People & Blogs",
              "15": "Pets & Animals"}


def mmss(t: float) -> str:
    t = int(t)
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def chapters_from_timeline(script: dict, timeline: dict | None) -> dict:
    """Chapters from scene timings, merged so each is >= 10 s. Valid only if YouTube would render them."""
    if not timeline:
        return {"valid": False, "chapters": [], "reason": "render the video first"}
    scenes = {s["n"]: s for s in script.get("scenes", [])}
    groups, cur = [], None
    for sc in timeline["scenes"]:
        label = (scenes.get(sc["n"], {}).get("on_screen_text") or scenes.get(sc["n"], {}).get("action") or "").strip()
        if cur is None or cur["dur"] >= 10:
            if cur:
                groups.append(cur)
            cur = {"start": sc["start"], "dur": 0.0, "label": label}
        cur["dur"] += sc["duration"]
        if not cur["label"]:
            cur["label"] = label
    if cur:
        groups.append(cur)
    if groups and groups[-1]["dur"] < 10 and len(groups) > 1:
        last = groups.pop()
        groups[-1]["dur"] += last["dur"]
    out = []
    for i, g in enumerate(groups):
        title = g["label"] or f"Part {i + 1}"
        title = re.sub(r"\s+", " ", title).strip(" .")[:40]
        out.append({"start": round(g["start"], 2), "label": mmss(g["start"]), "title": title.title() if title.isupper() else title,
                    "seconds": round(g["dur"], 2)})
    if out:
        out[0]["start"], out[0]["label"] = 0.0, "0:00"
    valid = len(out) >= 3 and out[0]["start"] == 0 and all(c["seconds"] >= 10 for c in out)
    return {"valid": valid, "chapters": out,
            "reason": "" if valid else "YouTube needs 3+ chapters of 10s+ each (typical for long videos only)"}


def _clean_tags(tags: list[str]) -> list[str]:
    out, total = [], 0
    for t in tags:
        t = re.sub(r"[<>\"#]", "", t).strip()
        if not t or t.lower() in (x.lower() for x in out):
            continue
        cost = len(t) + (2 if " " in t else 0) + 1
        if total + cost > 480 or len(out) >= 15:
            break
        out.append(t)
        total += cost
    return out


def _hashtags(tags: list[str], vertical: bool) -> list[str]:
    out = []
    for t in tags:
        h = "#" + re.sub(r"[^A-Za-z0-9]", "", t.title())
        if len(h) > 2 and h.lower() not in (x.lower() for x in out):
            out.append(h)
    if vertical and "#shorts" not in (x.lower() for x in out):
        out.insert(0, "#Shorts")
    return out[:3]


def build(project: dict) -> dict:
    script = project.get("script") or {}
    channel = db.get_setting("channel")
    vertical = project["format"] == "short"
    timeline = (project.get("render") or {}).get("timeline")
    cast = [characters.lookup(c) for c in script.get("characters", [])]
    cast = [c for c in cast if c and c.get("species") != "narrator"]
    names = [c["name"] for c in cast]
    if llm.active_provider() == "anthropic":
        prompt = f"""Prepare honest YouTube SEO for this ORIGINAL animated comedy video.
Title idea: {script.get('title')}
Logline: {script.get('logline')}
Hook line: {script.get('hook')}
Characters: {', '.join(f"{c['name']} the {c['species']}" for c in cast)}
Twist: {script.get('ending_twist')}
Format: {'YouTube Short (vertical)' if vertical else 'standard horizontal video'}; audience: {channel['audience']}.

Return: 8 title options (under 60 characters, front-loaded, curiosity without lying - the video must deliver
what the title says, no ALL-CAPS spam, no fake claims), description_hook (two short lines that say what the
viewer gets, in words people search), description_body (3-5 short lines about the episode and the recurring
characters, no spoilers of the twist, friendly CTA to subscribe for the next episode), up to 15 tags
(disambiguation: character names, 'animated comedy', 'funny cat cartoon' etc.; no unrelated tags),
3 hashtags, 3 search_queries this video should win, and thumbnail_text (max 3 words, must NOT repeat title words)."""
        data = llm.generate_json(prompt, SEO_SCHEMA, project_id=project["id"], stage="seo")
        source = "claude"
    else:
        import random
        base = script.get("title") or project.get("title")
        pair = " & ".join(names[:2]) or "The Gang"
        r = random.Random(base)
        title_words = set(re.findall(r"[a-z]+", base.lower()))
        thumbs = [t for t in ["WAIT WHAT", "PLAN B?!", "NOT AGAIN", "UH OH", "CASE CLOSED?", "TOO FAR", "BIG MISTAKE",
                              "WHO DID THIS", "NOPE", "TOTAL CHAOS"] if not set(re.findall(r"[a-z]+", t.lower())) & title_words]
        data = {
            "titles": [base, f"{pair}: {base}"[:95], f"{base} (Animated Comedy)"],
            "description_hook": f"{_trim(script.get('logline', ''), 160)}\nAn original animated comedy with a twist ending.",
            "description_body": (f"Starring {', '.join(names)} - the recurring cast of {channel['name']}.\n"
                                 "New episodes every week. Subscribe so you don't miss the next disaster!"),
            "tags": names + ["animated comedy", "funny animation", "cartoon comedy", "funny animals",
                             "talking animals", "plot twist", "family friendly comedy", "funny cat cartoon",
                             "funny dog cartoon", "AI animation"],
            "hashtags": [],
            "search_queries": ["funny animated cat", "talking dog cartoon", "animated comedy short"],
            "thumbnail_text": r.choice(thumbs or ["WAIT WHAT"]),
        }
        source = "offline template"
    ranked = sorted(({"title": t[:100], **legacy.lint_title(t[:100], data.get("thumbnail_text"))} for t in data["titles"] if t.strip()),
                    key=lambda r: -r["score"])
    tags = _clean_tags(data["tags"])
    hashtags = _hashtags(data.get("hashtags") or tags, vertical)
    for h in data.get("hashtags") or []:
        h = "#" + re.sub(r"[^A-Za-z0-9]", "", h)
        if len(hashtags) < 3 and h.lower() not in (x.lower() for x in hashtags) and len(h) > 1:
            hashtags.append(h)
    chapters = chapters_from_timeline(script, timeline) if not vertical else {"valid": False, "chapters": [],
                                                                                "reason": "Shorts do not show chapters"}
    desc = [data["description_hook"].strip(), ""]
    if chapters["valid"]:
        desc += [f"{c['label']} {c['title']}" for c in chapters["chapters"]] + [""]
    desc += [data["description_body"].strip(), "",
             "This is an original animated comedy. Visuals and voices are created with AI tools.", "",
             " ".join(hashtags)]
    description = "\n".join(desc)[:4900]
    best = ranked[0]["title"] if ranked else (script.get("title") or project["title"])
    return {
        "title": best, "title_options": ranked, "description": description, "tags": tags, "hashtags": hashtags,
        "chapters": chapters, "category_id": channel.get("category_id", "23"),
        "category_name": CATEGORIES.get(channel.get("category_id", "23"), "Comedy"),
        "made_for_kids": bool(channel.get("made_for_kids", False)),
        "contains_synthetic_media": bool(channel.get("contains_synthetic_media", True)),
        "default_language": channel.get("default_language", "en"),
        "search_queries": data.get("search_queries", []), "thumbnail_text": data.get("thumbnail_text", ""),
        "query_check": _query_check(best, data["description_hook"], data.get("search_queries", [])),
        "source": source,
        "audience_note": ("'Made for kids' is a legal (COPPA) setting, not a style choice. Family-friendly comedy "
                          "aimed at general audiences is usually NOT made for kids. Decide in Channel Settings."),
    }


def _query_check(title: str, hook: str, queries: list[str]) -> list[dict]:
    text = (title + " " + hook).lower()
    out = []
    for q in queries:
        words = [w for w in re.findall(r"[a-z0-9']+", q.lower()) if len(w) > 2]
        hit = [w for w in words if w in text]
        out.append({"query": q, "covered": len(hit), "of": len(words), "missing": [w for w in words if w not in hit]})
    return out


def _trim(text: str, n: int) -> str:
    """Cut at a sentence or word boundary, never mid-word."""
    text = (text or "").strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    dot = cut.rfind(". ")
    if dot > n * 0.5:
        return cut[:dot + 1]
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + "..."
