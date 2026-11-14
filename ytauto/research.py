"""STEP 1 - Topic research.

1. Trend signals (optional, free): YouTube Data API search for recent comedy-animation videos in
   the US, ranked by views per day, with the title formula classified by the original skill pack's
   hooks.json. Only public metadata (titles, counts) is read; nothing is downloaded or copied.
2. Ideas: Claude (if configured) or the offline template writer generates ORIGINAL ideas that use
   the channel's own recurring characters.
3. Scoring: audience appeal + production feasibility, 0-100 each, combined.
"""
from __future__ import annotations

import json
import re
import statistics
import time
from datetime import datetime, timedelta, timezone

import httpx

from . import characters, config, db, legacy, llm, offline_writer

DEFAULT_QUERIES = ["funny animated cat", "talking dog animation funny", "office comedy animation short",
                   "funny animal cartoon shorts", "animated comedy skit plot twist"]

YT = "https://www.googleapis.com/youtube/v3"


class ResearchError(RuntimeError):
    pass


def _iso_days(iso: str) -> float:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0.5, (datetime.now(timezone.utc) - dt).total_seconds() / 86400)


def trend_signals(queries: list[str] | None = None, days: int = 21, per_query: int = 15,
                  region: str = "US") -> dict:
    """Return trending public videos for the niche. Costs ~101 quota units per query, no money."""
    key = config.env("YOUTUBE_API_KEY")
    if not key:
        return {"available": False, "videos": [], "keywords": [],
                "note": "Set YOUTUBE_API_KEY (free) to add live YouTube trend signals to research."}
    queries = queries or DEFAULT_QUERIES
    after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    with httpx.Client(timeout=30) as c:
        for q in queries:
            r = c.get(f"{YT}/search", params={"part": "snippet", "q": q, "type": "video", "order": "viewCount",
                                              "publishedAfter": after, "regionCode": region,
                                              "relevanceLanguage": "en", "maxResults": per_query,
                                              "safeSearch": "moderate", "key": key})
            if r.status_code == 403:
                raise ResearchError(f"YouTube API refused the request (quota or key restriction): {r.text[:300]}")
            if r.status_code == 400:
                raise ResearchError(f"YouTube API key rejected: {r.text[:300]}")
            r.raise_for_status()
            ids += [it["id"]["videoId"] for it in r.json().get("items", []) if it.get("id", {}).get("videoId")]
        ids = list(dict.fromkeys(ids))
        videos = []
        for i in range(0, len(ids), 50):
            r = c.get(f"{YT}/videos", params={"part": "snippet,statistics,contentDetails",
                                              "id": ",".join(ids[i:i + 50]), "key": key})
            r.raise_for_status()
            for v in r.json().get("items", []):
                st = v.get("statistics", {})
                views = int(st.get("viewCount", 0))
                age = _iso_days(v["snippet"]["publishedAt"])
                videos.append({"title": v["snippet"]["title"], "channel": v["snippet"]["channelTitle"],
                               "views": views, "likes": int(st.get("likeCount", 0) or 0),
                               "views_per_day": round(views / age), "age_days": round(age, 1),
                               "url": f"https://www.youtube.com/watch?v={v['id']}",
                               "duration": v.get("contentDetails", {}).get("duration"),
                               "formula": legacy.classify_title(v["snippet"]["title"])})
    videos.sort(key=lambda v: -v["views_per_day"])
    if videos:
        med = statistics.median(v["views_per_day"] for v in videos) or 1
        for v in videos:
            v["multiple"] = round(v["views_per_day"] / med, 2)
    stop = set("the a an of to and in on for with is my your this that it when i you me funny video shorts short "
               "animation animated cartoon comedy #shorts".split())
    freq: dict[str, int] = {}
    for v in videos[:40]:
        for w in re.findall(r"[a-z']{3,}", v["title"].lower()):
            if w not in stop:
                freq[w] = freq.get(w, 0) + 1
    keywords = [w for w, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:25]]
    return {"available": True, "videos": videos[:40], "keywords": keywords, "queries": queries,
            "note": "Public metadata only. Use as inspiration for themes - never copy titles, scripts or characters."}


IDEA_SCHEMA = {
    "type": "object",
    "properties": {"ideas": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "title": {"type": "string"}, "premise": {"type": "string"}, "hook": {"type": "string"},
            "characters": {"type": "array", "items": {"type": "string"}},
            "setting": {"type": "string"}, "twist": {"type": "string"},
            "appeal_score": {"type": "integer"}, "feasibility_score": {"type": "integer"},
            "why_it_works": {"type": "string"},
        },
        "required": ["title", "premise", "hook", "characters", "setting", "twist", "appeal_score",
                     "feasibility_score", "why_it_works"],
        "additionalProperties": False}}},
    "required": ["ideas"], "additionalProperties": False,
}


def _feasibility(idea: dict) -> int:
    n_chars = len(idea.get("characters") or [])
    known = sum(1 for c in idea.get("characters") or [] if characters.lookup(c))
    s = 90 - max(0, n_chars - 2) * 12 + known * 4 - (0 if known == n_chars else 15)
    if len((idea.get("premise") or "").split()) > 70:
        s -= 10
    return max(10, min(100, s))


def _appeal(idea: dict, keywords: list[str]) -> int:
    hook = legacy.score_hook(idea.get("hook") or idea.get("title", ""))
    title = legacy.lint_title(idea.get("title", ""))
    text = (idea.get("title", "") + " " + idea.get("premise", "")).lower()
    trend_hits = sum(1 for k in keywords if k in text)
    return max(10, min(100, round(0.45 * hook["verdict"] + 0.35 * title["score"] + 20 + 4 * min(trend_hits, 5))))


def score(idea: dict, keywords: list[str] | None = None) -> dict:
    keywords = keywords or []
    appeal_h = _appeal(idea, keywords)
    feas_h = _feasibility(idea)
    appeal = round((appeal_h + idea["appeal_score"]) / 2) if isinstance(idea.get("appeal_score"), int) else appeal_h
    feas = round((feas_h + idea["feasibility_score"]) / 2) if isinstance(idea.get("feasibility_score"), int) else feas_h
    idea["appeal_score"], idea["feasibility_score"] = appeal, feas
    idea["total_score"] = round(0.6 * appeal + 0.4 * feas)
    idea["hook_score"] = legacy.score_hook(idea.get("hook") or idea["title"])
    idea["title_lint"] = legacy.lint_title(idea["title"])
    return idea


def generate_ideas(n: int = 10, fmt: str | None = None, use_trends: bool = True, topic_hint: str = "",
                   seed=None) -> dict:
    channel = db.get_setting("channel")
    fmt = fmt or channel["default_format"]
    cast = [c for c in characters.all_characters()]
    trends = {"available": False, "videos": [], "keywords": []}
    trend_error = None
    if use_trends:
        try:
            trends = trend_signals()
        except (ResearchError, httpx.HTTPError) as e:
            trend_error = str(e)
            db.log_event(None, "research", f"Trend lookup failed: {e}", "warning")
    provider = llm.active_provider()
    if provider == "anthropic":
        top = "\n".join(f"- {v['title']} ({v['views_per_day']}/day, formula: {v['formula']})" for v in trends["videos"][:15])
        prompt = f"""Channel: {channel['name']} - {channel['niche']}.
Audience: {channel['audience']}. Tone: {channel['tone']}.
Themes we like: {', '.join(channel['themes'])}.
Format: {'YouTube Short, vertical 9:16, 30-55 seconds' if fmt == 'short' else 'horizontal 16:9 video, 2-4 minutes'}.
{('Extra direction from the creator: ' + topic_hint) if topic_hint else ''}

Our recurring ORIGINAL characters (use their ids in "characters"; you may invent at most one new side character):
{characters.describe_cast([c['id'] for c in cast])}

What is currently getting views in the wider niche (for THEMES and FORMATS only - do not copy any title, joke,
character or plot from these):
{top or '(no live trend data available - rely on evergreen relatable comedy)'}
Trending words: {', '.join(trends['keywords'][:20]) or 'n/a'}

Generate {n} ORIGINAL video ideas. Each needs: a title under 60 characters (no clickbait that the video does not
deliver), a 2-3 sentence premise, the spoken hook line for the first 3 seconds, 1-3 characters (ids), the
setting, the twist ending, appeal_score (0-100, audience appeal for US/English family comedy viewers),
feasibility_score (0-100, how easy to produce with AI images + voices: fewer characters/settings = easier),
and one sentence on why it works."""
        data = llm.generate_json(prompt, IDEA_SCHEMA, stage="research")
        ideas = data["ideas"]
        for i in ideas:
            i["format"], i["source"] = fmt, "claude"
    else:
        ideas = offline_writer.ideas(n, cast, fmt, seed=seed)
    ideas = [score(i, trends.get("keywords")) for i in ideas]
    ideas.sort(key=lambda i: -i["total_score"])
    batch = time.strftime("%Y%m%d-%H%M%S")
    for i in ideas:
        i["id"] = db.execute("INSERT INTO ideas(ts,batch,data) VALUES(?,?,?)", (time.time(), batch, json.dumps(i)))
    db.log_event(None, "research", f"Generated {len(ideas)} ideas with {provider}"
                 + (f" + {len(trends['videos'])} trend signals" if trends.get("available") else ""))
    return {"batch": batch, "provider": provider, "ideas": ideas, "trends": trends, "trend_error": trend_error}


def saved_ideas(limit: int = 100, unused_only: bool = False) -> list[dict]:
    sql = "SELECT * FROM ideas " + ("WHERE used=0 " if unused_only else "") + "ORDER BY id DESC LIMIT ?"
    out = []
    for r in db.query(sql, (limit,)):
        d = json.loads(r["data"])
        d.update({"id": r["id"], "batch": r["batch"], "used": bool(r["used"])})
        out.append(d)
    return out


def get_idea(idea_id: int) -> dict:
    rows = db.query("SELECT * FROM ideas WHERE id=?", (idea_id,))
    if not rows:
        raise KeyError(f"idea {idea_id} not found")
    d = json.loads(rows[0]["data"])
    d["id"] = idea_id
    return d


def mark_used(idea_id: int) -> None:
    db.execute("UPDATE ideas SET used=1 WHERE id=?", (idea_id,))
