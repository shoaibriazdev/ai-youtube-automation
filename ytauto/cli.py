"""Command line: `ytauto <command>` (or `python -m ytauto <command>`).

These are what the Claude Code skills (/yt-ideas, /yt-script, ... /yt-today) call.
"""
from __future__ import annotations

import argparse
import json
import sys

from . import (characters, costs, db, jobs, pipeline, projects, research, scriptgen)


def _p(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def _bar(frac: float, msg: str = "") -> None:
    n = int(frac * 30)
    sys.stdout.write(f"\r[{'#' * n}{'.' * (30 - n)}] {int(frac * 100):3d}% {msg[:60]:<60}")
    sys.stdout.flush()


def _latest(pid: str | None) -> str:
    if pid:
        return pid
    rows = projects.list_all(1)
    if not rows:
        sys.exit("No projects yet. Run: ytauto today   (or: ytauto new --idea <id>)")
    return rows[0]["id"]


def _run(pid: str, stages: list[str], force=None, **kw) -> dict:
    res = pipeline.run(pid, stages, progress=_bar, force=force or [], **kw)
    print()
    if res.get("needs_approval"):
        est = res["estimate"]
        print(f"\nPaused: this would cost about ${est['total_usd']:.2f} with paid providers:")
        for it in est["items"]:
            if it["usd"]:
                print(f"  - {it['stage']:<10} {it['provider']:<14} ${it['usd']:.3f}  ({it['units']} {it['unit']})")
        print(f"\nApprove with:  ytauto approve-cost {pid}   then run the command again.")
    return res


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="ytauto", description="AI YouTube Automation Pro")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="start the dashboard (http://localhost:8000)")
    s.add_argument("--host"); s.add_argument("--port", type=int); s.add_argument("--open", action="store_true")

    sub.add_parser("doctor", help="check FFmpeg, providers, keys, YouTube connection")

    s = sub.add_parser("ideas", help="/yt-ideas: research trends and generate scored ideas")
    s.add_argument("-n", type=int, default=10); s.add_argument("--format", choices=["short", "long"])
    s.add_argument("--no-trends", action="store_true"); s.add_argument("--hint", default="")
    s.add_argument("--list", action="store_true", help="list saved ideas instead")

    s = sub.add_parser("new", help="create a project from an idea id (or a title)")
    s.add_argument("--idea", type=int); s.add_argument("--title"); s.add_argument("--format", choices=["short", "long"])
    s.add_argument("--both", action="store_true", help="export 9:16 and 16:9")

    for name, stage, helptext in [("script", "script", "/yt-script: write the scene-by-scene script"),
                                  ("characters", "characters", "/yt-characters: build character reference sheets"),
                                  ("generate", None, "/yt-generate: scene images (+ AI video clips)"),
                                  ("voice", "voice", "/yt-voice: character voiceovers"),
                                  ("edit", "edit", "/yt-edit: render the final MP4(s)"),
                                  ("thumbnail", "thumbnail", "/yt-thumbnail: 1280x720 thumbnail"),
                                  ("seo", "seo", "/yt-seo: title, description, tags, chapters")]:
        s = sub.add_parser(name, help=helptext)
        s.add_argument("project", nargs="?"); s.add_argument("--force", action="store_true")
        if name == "script":
            s.add_argument("--notes", default="")
        if name == "thumbnail":
            s.add_argument("--text"); s.add_argument("--style", default="pop", choices=["pop", "clean", "shock"])
        if name == "edit":
            s.add_argument("--both", action="store_true", help="render 9:16 and 16:9")

    s = sub.add_parser("run", help="run any stages: ytauto run <project> script images voice edit")
    s.add_argument("project"); s.add_argument("stages", nargs="*")

    s = sub.add_parser("today", help="CREATE TODAY'S VIDEO end to end (stops before upload)")
    s.add_argument("--format", choices=["short", "long"]); s.add_argument("--hint", default="")

    s = sub.add_parser("estimate", help="show estimated API cost for a project")
    s.add_argument("project", nargs="?")
    s = sub.add_parser("approve-cost", help="approve the estimated spend for a project")
    s.add_argument("project"); s.add_argument("--amount", type=float)
    s = sub.add_parser("approve", help="approve a rendered video for upload (after watching it)")
    s.add_argument("project")

    s = sub.add_parser("youtube", help="connect | status | disconnect")
    s.add_argument("action", choices=["connect", "status", "disconnect"])

    s = sub.add_parser("upload", help="/yt-upload: upload (private by default)")
    s.add_argument("project"); s.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    s.add_argument("--publish-at", help="ISO time with offset, e.g. 2026-11-20T17:00:00-05:00")
    s.add_argument("--aspect", choices=["9:16", "16:9"])
    s.add_argument("--yes-public", action="store_true", help="confirm public/scheduled publishing")

    s = sub.add_parser("schedule", help="/yt-schedule: set publish time of an uploaded private video")
    s.add_argument("project"); s.add_argument("publish_at"); s.add_argument("--yes-public", action="store_true")

    s = sub.add_parser("analytics", help="/yt-analytics: channel + uploaded video stats")
    s.add_argument("--days", type=int, default=28)

    s = sub.add_parser("autopilot", help="daily automatic create + upload: status | run | on | off")
    s.add_argument("action", choices=["status", "run", "on", "off"])
    s.add_argument("--time", help="HH:MM daily run time"); s.add_argument("--tz", help="e.g. Asia/Karachi")

    sub.add_parser("projects", help="list projects")
    s = sub.add_parser("show", help="show a project (json)")
    s.add_argument("project", nargs="?")
    s = sub.add_parser("hook", help="score hooks with the original hookscore panel")
    s.add_argument("hooks", nargs="+")

    a = ap.parse_args(argv)
    db.conn()
    characters.ensure_defaults()

    if a.cmd == "serve":
        from .server import serve
        serve(a.host, a.port, a.open)
    elif a.cmd == "doctor":
        r = pipeline.doctor()
        for c in r["checks"]:
            mark = "OK " if c["ok"] else ("!! " if c["required"] else "-- ")
            print(f"  {mark} {c['name']:<28} {c['detail']}")
        print("\nAll required checks passed." if r["ok"] else "\nSome required checks failed (see !! above).")
        sys.exit(0 if r["ok"] else 1)
    elif a.cmd == "ideas":
        ideas = research.saved_ideas(50) if a.list else None
        if ideas is None:
            r = research.generate_ideas(a.n, a.format, not a.no_trends, a.hint)
            ideas = r["ideas"]
            print(f"Provider: {r['provider']}   trends: {'yes' if r['trends'].get('available') else 'no'}"
                  + (f"  ({r['trend_error']})" if r.get("trend_error") else ""))
        for i in ideas:
            print(f"\n#{i['id']}  [{i.get('total_score')}]  {i['title']}"
                  f"\n     appeal {i.get('appeal_score')}  feasibility {i.get('feasibility_score')}  "
                  f"cast: {', '.join(i.get('characters', []))}\n     hook: {i.get('hook')}\n     {i.get('premise')}")
        print("\nStart one with:  ytauto new --idea <id>")
    elif a.cmd == "new":
        idea = research.get_idea(a.idea) if a.idea else None
        if a.idea:
            research.mark_used(a.idea)
        p = projects.create((idea or {}).get("title") or a.title or "Untitled video", a.format or (idea or {}).get("format"), idea)
        if a.both:
            p["export_aspects"] = ["9:16", "16:9"]
            projects.save(p)
        print(f"Created project {p['id']}: {p['title']}")
    elif a.cmd in ("script", "characters", "voice", "edit", "thumbnail", "seo", "generate"):
        pid = _latest(a.project)
        stages = {"generate": ["characters", "images", "video"]}.get(a.cmd, [a.cmd])
        if a.cmd == "script":
            p = projects.load(pid)
            if not p.get("idea"):
                stages = ["research", "script"]
        kw = {}
        if a.cmd == "script":
            kw["notes"] = a.notes
        if a.cmd == "thumbnail":
            kw.update(thumbnail_text=a.text, thumbnail_style=a.style)
        if a.cmd == "edit" and a.both:
            kw["aspects"] = ["9:16", "16:9"]
        res = _run(pid, stages, force=stages if a.force else [], **kw)
        if res.get("ok"):
            p = projects.load(pid)
            if a.cmd == "script":
                print(scriptgen.to_text(p["script"]))
            elif a.cmd == "edit":
                for asp, o in p["render"]["outputs"].items():
                    print(f"{asp}: {projects.abspath(pid, o['file'])}  ({o['duration']}s, {o['size_mb']} MB)")
            elif a.cmd == "thumbnail":
                print(projects.abspath(pid, p["thumbnail"]["jpg"]))
            elif a.cmd == "seo":
                _p({k: p["seo"][k] for k in ("title", "description", "tags", "hashtags", "category_name", "made_for_kids")})
            else:
                print(f"{a.cmd} done for {pid}")
    elif a.cmd == "run":
        _run(a.project, a.stages or pipeline.STAGES)
    elif a.cmd == "today":
        print("CREATE TODAY'S VIDEO: topic -> script -> scenes -> visuals -> voices -> edit -> thumbnail -> SEO")
        res = pipeline.create_todays_video(a.format, a.hint, progress=_bar)
        print()
        pid = res["project"]
        if res.get("needs_approval"):
            print(f"Paused for cost approval: ytauto approve-cost {pid}  then  ytauto run {pid}")
        elif res.get("ok"):
            p = projects.load(pid)
            print(f"\nReady for review: {p['title']}  (project {pid})")
            for asp, o in p["render"]["outputs"].items():
                print(f"  video {asp}: {projects.abspath(pid, o['file'])}")
            print(f"  thumbnail: {projects.abspath(pid, p['thumbnail']['jpg'])}")
            print(f"  title: {p['seo']['title']}")
            print(f"\nWatch it. If you like it:  ytauto approve {pid}   then   ytauto upload {pid}   (private)")
        else:
            print(f"Failed: {res.get('error')}  - details: ytauto show {pid}")
            sys.exit(1)
    elif a.cmd == "estimate":
        pid = a.project
        _p(costs.estimate(projects.load(pid) if pid else None))
    elif a.cmd == "approve-cost":
        _p(pipeline.approve_cost(a.project, a.amount))
    elif a.cmd == "approve":
        p = projects.load(a.project)
        if not (p.get("render") or {}).get("outputs"):
            sys.exit("Render the video first (ytauto edit).")
        projects.update_row(a.project, approved=1, status="approved")
        db.log_event(a.project, "review", "Approved by you (CLI)")
        print("Approved. Upload privately with: ytauto upload " + a.project)
    elif a.cmd == "youtube":
        from . import youtube
        if a.action == "connect":
            _p(youtube.connect(open_browser=True, blocking=True))
        elif a.action == "disconnect":
            youtube.disconnect(); print("Disconnected.")
        else:
            _p(youtube.status())
    elif a.cmd == "upload":
        from . import youtube
        if (a.privacy == "public" or a.publish_at) and not a.yes_public:
            ans = input(f"This will make the video {'public' if a.privacy == 'public' else 'public at ' + a.publish_at}. "
                        "Type PUBLISH to confirm: ")
            if ans.strip() != "PUBLISH":
                sys.exit("Cancelled.")
            a.yes_public = True
        _p(youtube.upload(a.project, a.privacy, a.publish_at, a.aspect, a.yes_public, progress=_bar))
    elif a.cmd == "schedule":
        from . import youtube
        if not a.yes_public:
            if input(f"Video becomes PUBLIC at {a.publish_at}. Type PUBLISH to confirm: ").strip() != "PUBLISH":
                sys.exit("Cancelled.")
        _p(youtube.schedule_existing(a.project, a.publish_at, True))
    elif a.cmd == "analytics":
        from .server import analytics
        _p(analytics(a.days))
    elif a.cmd == "autopilot":
        from . import autopilot
        if a.action == "run":
            _p(autopilot.run_once(progress=_bar))
        elif a.action in ("on", "off"):
            vals = {"enabled": a.action == "on"}
            if a.time:
                vals["run_at"] = a.time
            if a.tz:
                vals["timezone"] = a.tz
            _p(autopilot.save(vals))
            print("Autopilot runs while the server (ytauto serve / start.bat / Docker) is running.")
        else:
            _p(autopilot.status())
    elif a.cmd == "projects":
        for r in projects.list_all():
            print(f"{r['id']}  {r['status']:<22} {r['format']:<5} {r['title']}")
    elif a.cmd == "show":
        _p({**projects.load(_latest(a.project)), "row": projects.row(_latest(a.project))})
    elif a.cmd == "hook":
        from . import legacy
        for h in sorted((legacy.score_hook(x) for x in a.hooks), key=lambda r: -r["verdict"]):
            print(f"{h['verdict']:3d} {h['band']:<8} {h['formula']:<24} {h['hook']}")


if __name__ == "__main__":
    main()
