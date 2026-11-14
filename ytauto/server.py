"""FastAPI backend for the dashboard. Binds to 127.0.0.1 by default (local use only)."""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import (__version__, auth, autopilot, characters, config, costs, db, jobs, llm, pipeline, projects, research,
               scriptgen, seo, youtube)
from .providers import image as image_p, tts as tts_p, video as video_p
from .providers.base import ProviderError

@asynccontextmanager
async def _lifespan(_app):
    db.conn()
    characters.ensure_defaults()
    jobs.mark_stale()
    autopilot.start_scheduler()
    yield


app = FastAPI(title="AI YouTube Automation Pro", version=__version__, lifespan=_lifespan)
app.middleware("http")(auth.middleware)


@app.get("/login", include_in_schema=False)
def login_get(next: str = "/"):
    if not auth.enabled():
        return RedirectResponse("/", status_code=303)
    return auth.login_page(next_url=next if next.startswith("/") and not next.startswith("//") else "/")


@app.post("/login", include_in_schema=False)
async def login_post(request: Request):
    return await auth.handle_login(request)


@app.get("/logout", include_in_schema=False)
def logout():
    return auth.logout()


@app.exception_handler(KeyError)
async def _key_error(_, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc).strip("'\"")})


def _err(e: Exception, code: int = 400):
    raise HTTPException(status_code=code, detail=str(e))


# ---------------- overview / health ----------------
@app.get("/api/health")
def health():
    return {"ok": True, "version": __version__, "time": time.time()}


@app.get("/api/overview")
def overview():
    rows = projects.list_all(500)
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    return {"projects": rows[:10], "counts": by_status, "total": len(rows), "doctor": pipeline.doctor(),
            "budget": costs.budget_status(), "jobs": jobs.recent(10), "events": db.events(None, 30),
            "providers": db.get_setting("providers"), "uploads": youtube.history(5)}


@app.get("/api/doctor")
def doctor():
    return pipeline.doctor()


# ---------------- settings ----------------
@app.get("/api/settings")
def get_settings():
    return {**db.all_settings(), "options": {
        "llm": ["auto", "anthropic", "offline"], "image": image_p.PROVIDERS, "video": video_p.PROVIDERS,
        "tts": tts_p.PROVIDERS, "categories": seo.CATEGORIES, "anthropic_model": config.env("ANTHROPIC_MODEL"),
        "free_notes": costs.FREE_NOTES, "paid_notes": costs.PAID_NOTES}}


@app.put("/api/settings/{key}")
def put_setting(key: str, value: dict = Body(...)):
    if key not in db.DEFAULT_SETTINGS:
        _err(ValueError(f"unknown settings group '{key}'"), 404)
    return db.set_setting(key, value)


@app.get("/api/secrets")
def get_secrets():
    return {"secrets": config.secrets_status(),
            "env": {k: config.env(k) for k in config.NON_SECRET_ENV},
            "env_file": str(config.ENV_FILE), "youtube": youtube.status()}


@app.put("/api/secrets")
def put_secrets(values: dict[str, str] = Body(...)):
    try:
        written = config.write_env_values(values)
    except ValueError as e:
        _err(e)
    return {"written": written, "secrets": config.secrets_status()}


@app.get("/api/costs")
def get_costs():
    return {"budget": costs.budget_status(), "pricing": costs.pricing(), "estimate": costs.estimate(),
            "log": db.query("SELECT * FROM cost_log ORDER BY id DESC LIMIT 200")}


@app.post("/api/costs/estimate")
def post_estimate(body: dict = Body(default={})):
    p = projects.load(body["project_id"]) if body.get("project_id") else None
    return costs.estimate(p, providers=body.get("providers"), stages=body.get("stages"))


# ---------------- research ----------------
@app.post("/api/ideas")
def gen_ideas(body: dict = Body(default={})):
    def task(progress, cancelled):
        progress(0.1, "Researching trends and writing ideas")
        r = research.generate_ideas(int(body.get("n", 10)), body.get("format"), bool(body.get("use_trends", True)),
                                    body.get("topic_hint", ""))
        return {"ok": True, "count": len(r["ideas"]), "batch": r["batch"], "trend_error": r.get("trend_error"),
                "trends": {"available": r["trends"].get("available"), "keywords": r["trends"].get("keywords", []),
                           "videos": r["trends"].get("videos", [])[:15], "note": r["trends"].get("note")}}
    return {"job_id": jobs.submit("ideas", task)}


@app.get("/api/ideas")
def list_ideas(unused: bool = False):
    return research.saved_ideas(200, unused)


@app.post("/api/hookscore")
def hookscore(body: dict = Body(...)):
    from . import legacy
    return [legacy.score_hook(h) for h in body.get("hooks", []) if h.strip()]


@app.post("/api/titlelint")
def titlelint(body: dict = Body(...)):
    from . import legacy
    return [legacy.lint_title(t, body.get("thumb")) for t in body.get("titles", []) if t.strip()]


# ---------------- projects ----------------
@app.get("/api/projects")
def list_projects():
    return projects.list_all()


@app.post("/api/projects")
def create_project(body: dict = Body(default={})):
    idea = None
    if body.get("idea_id"):
        idea = research.get_idea(int(body["idea_id"]))
        research.mark_used(int(body["idea_id"]))
    elif body.get("idea"):
        idea = body["idea"]
    try:
        p = projects.create((idea or {}).get("title") or body.get("title") or "Untitled video",
                            body.get("format") or (idea or {}).get("format"), idea)
    except ValueError as e:
        _err(e)
    if body.get("both_aspects"):
        p["export_aspects"] = ["9:16", "16:9"]
        projects.save(p)
    return p


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    p = projects.load(pid)
    return {**p, "row": projects.row(pid), "events": db.events(pid, 100), "jobs": jobs.recent(10, pid),
            "uploads": db.query("SELECT * FROM uploads WHERE project_id=? ORDER BY id DESC", (pid,))}


@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    projects.delete(pid)
    return {"deleted": pid}


@app.put("/api/projects/{pid}/script")
def put_script(pid: str, script: dict = Body(...)):
    p = projects.load(pid)
    try:
        p["script"] = scriptgen.finalize(script)
    except (ValueError, KeyError, TypeError) as e:
        _err(e)
    (projects.project_dir(pid) / "script.md").write_text(scriptgen.to_text(p["script"]), encoding="utf-8")
    p["assets"]["voice"] = {}  # dialogue may have changed
    projects.save(p)
    db.log_event(pid, "script", "Script edited by user")
    return p["script"]


@app.put("/api/projects/{pid}/seo")
def put_seo(pid: str, data: dict = Body(...)):
    p = projects.load(pid)
    allowed = {"title", "description", "tags", "hashtags", "category_id", "made_for_kids", "contains_synthetic_media",
               "default_language", "thumbnail_text"}
    p.setdefault("seo", {}).update({k: v for k, v in data.items() if k in allowed})
    if len(p["seo"].get("title", "")) > 100:
        _err(ValueError("Title must be 100 characters or fewer"))
    projects.save(p)
    return p["seo"]


@app.put("/api/projects/{pid}/options")
def put_options(pid: str, data: dict = Body(...)):
    p = projects.load(pid)
    if "export_aspects" in data:
        asp = [a for a in data["export_aspects"] if a in ("9:16", "16:9")]
        if not asp:
            _err(ValueError("choose at least one aspect"))
        p["export_aspects"] = asp
    projects.save(p)
    return {"export_aspects": p.get("export_aspects")}


@app.post("/api/projects/{pid}/run")
def run_project(pid: str, body: dict = Body(default={})):
    projects.row(pid)
    stages = body.get("stages") or pipeline.STAGES
    force = body.get("force") or []
    extra = {k: body[k] for k in ("notes", "thumbnail_text", "thumbnail_style", "aspects", "topic_hint") if k in body}

    def task(progress, cancelled):
        return pipeline.run(pid, stages, progress=progress, cancel=cancelled, force=force, **extra)
    return {"job_id": jobs.submit("pipeline:" + ",".join(stages), task, pid)}


@app.post("/api/projects/{pid}/approve-cost")
def approve_cost(pid: str, body: dict = Body(default={})):
    return pipeline.approve_cost(pid, body.get("amount"))


@app.post("/api/projects/{pid}/approve")
def approve(pid: str, body: dict = Body(default={})):
    p = projects.load(pid)
    if not (p.get("render") or {}).get("outputs"):
        _err(ValueError("Render the video before approving it."))
    approved = bool(body.get("approved", True))
    projects.update_row(pid, approved=1 if approved else 0, status="approved" if approved else "ready_for_review")
    db.log_event(pid, "review", "Approved by you" if approved else "Approval withdrawn")
    return projects.row(pid)


@app.post("/api/today")
def today(body: dict = Body(default={})):
    def task(progress, cancelled):
        return pipeline.create_todays_video(body.get("format"), body.get("topic_hint", ""), progress, cancelled)
    return {"job_id": jobs.submit("create_todays_video", task)}


@app.get("/api/projects/{pid}/file/{path:path}")
def project_file(pid: str, path: str):
    base = projects.project_dir(pid).resolve()
    f = (base / path).resolve()
    if base not in f.parents or not f.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(f)


# ---------------- jobs / events ----------------
@app.get("/api/jobs")
def list_jobs(project_id: str | None = None):
    return jobs.recent(50, project_id)


@app.get("/api/jobs/{jid}")
def get_job(jid: str):
    return jobs.get(jid)


@app.post("/api/jobs/{jid}/cancel")
def cancel_job(jid: str):
    jobs.cancel(jid)
    return {"cancelling": jid}


@app.get("/api/events")
def list_events(project_id: str | None = None, limit: int = 200):
    return db.events(project_id, limit)


# ---------------- characters ----------------
@app.get("/api/characters")
def list_characters():
    return characters.all_characters()


@app.post("/api/characters")
def save_character(c: dict = Body(...)):
    if not c.get("name"):
        _err(ValueError("name is required"))
    return characters.save(c)


@app.delete("/api/characters/{cid}")
def delete_character(cid: str):
    characters.delete(cid)
    return {"deleted": cid}


@app.post("/api/characters/{cid}/reference")
def character_reference(cid: str):
    c = characters.get(cid)
    if not c:
        raise HTTPException(404, "character not found")
    prov = db.get_setting("providers")["image"]

    def task(progress, cancelled):
        out = config.DATA_DIR / "characters" / f"{cid}_{prov}.png"
        image_p.generate(prov, characters.image_prompt(c), out, "16:9", c["seed"],
                         {"scene": {"setting": "studio", "n": "ref", "dialogue": []}, "cast": [c], "clean": True})
        c["reference_image"], c["reference_provider"] = out.name, prov
        characters.save(c)
        return {"ok": True, "file": out.name}
    return {"job_id": jobs.submit(f"character_ref:{cid}", task)}


@app.get("/api/characters/{cid}/image")
def character_image(cid: str):
    c = characters.get(cid)
    if not c or not c.get("reference_image"):
        raise HTTPException(404, "no reference image yet")
    f = config.DATA_DIR / "characters" / c["reference_image"]
    if not f.exists():
        raise HTTPException(404, "no reference image yet")
    return FileResponse(f)


@app.post("/api/characters/{cid}/voice-test")
def voice_test(cid: str, body: dict = Body(default={})):
    c = characters.get(cid)
    if not c:
        raise HTTPException(404, "character not found")
    prov = body.get("provider") or db.get_setting("providers")["tts"]
    text = body.get("text") or c.get("catchphrase") or f"Hi, I'm {c['name']}!"
    out = config.CACHE_DIR / f"voicetest_{cid}_{prov}"
    try:
        f = tts_p.synthesize(prov, text, c, out)
    except ProviderError as e:
        _err(e)
    return FileResponse(f)


@app.get("/api/voices")
def list_voices():
    out = {"edge": tts_p.EDGE_VOICES, "openai": ["alloy", "ash", "ballad", "coral", "echo", "fable", "nova", "onyx",
                                                 "sage", "shimmer", "verse"], "sapi": tts_p.sapi_voices(), "elevenlabs": []}
    if config.has_secret("ELEVENLABS_API_KEY"):
        try:
            out["elevenlabs"] = tts_p.elevenlabs_voices()
        except ProviderError as e:
            out["elevenlabs_error"] = str(e)
    return out


# ---------------- youtube ----------------
@app.get("/api/youtube/status")
def yt_status():
    return youtube.status()


def _public_base(request: Request) -> str:
    base = config.env("PUBLIC_URL")
    if base:
        return base.rstrip("/")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    return f"{proto}://{host}"


@app.get("/api/youtube/oauth/start", include_in_schema=False)
def yt_oauth_start(request: Request):
    """Web OAuth (for online deployments). Needs a 'Web application' OAuth client."""
    try:
        url = youtube.web_flow_start(_public_base(request) + "/api/youtube/oauth/callback")
    except youtube.YouTubeError as e:
        return HTMLResponse(f"<p>{e}</p><p><a href='/#upload'>Back</a></p>", status_code=400)
    return RedirectResponse(url, status_code=303)


@app.get("/api/youtube/oauth/callback", include_in_schema=False)
def yt_oauth_callback(request: Request, state: str = "", code: str = "", error: str = ""):
    if error:
        return RedirectResponse("/#upload", status_code=303)
    try:
        youtube.web_flow_finish(state, _public_base(request) + "/api/youtube/oauth/callback?" + request.url.query)
    except youtube.YouTubeError as e:
        return HTMLResponse(f"<p>YouTube sign-in failed: {e}</p><p><a href='/#upload'>Back</a></p>", status_code=400)
    return RedirectResponse("/#upload", status_code=303)


@app.post("/api/youtube/client-secret")
def yt_client_secret(data: dict = Body(...)):
    try:
        return youtube.save_client_secret(data)
    except youtube.YouTubeError as e:
        _err(e)


@app.post("/api/youtube/connect")
def yt_connect():
    try:
        return youtube.connect(open_browser=True, blocking=False)
    except youtube.YouTubeError as e:
        _err(e)


@app.post("/api/youtube/disconnect")
def yt_disconnect():
    youtube.disconnect()
    return youtube.status()


@app.post("/api/projects/{pid}/upload")
def yt_upload(pid: str, body: dict = Body(default={})):
    row = projects.row(pid)
    if not row.get("approved"):
        _err(ValueError("Approve the video first (watch it, then click Approve)."))
    privacy = body.get("privacy", "private")
    if (privacy == "public" or body.get("publish_at")) and not body.get("confirm_public"):
        _err(ValueError("Public or scheduled publishing requires confirm_public=true."))

    def task(progress, cancelled):
        return {"ok": True, **youtube.upload(pid, privacy, body.get("publish_at"), body.get("aspect"),
                                             bool(body.get("confirm_public")), progress)}
    return {"job_id": jobs.submit("upload", task, pid)}


@app.post("/api/projects/{pid}/schedule")
def yt_schedule(pid: str, body: dict = Body(...)):
    try:
        return youtube.schedule_existing(pid, body["publish_at"], bool(body.get("confirm_public")))
    except (youtube.YouTubeError, KeyError) as e:
        _err(e)


@app.get("/api/uploads")
def uploads():
    return youtube.history()


@app.get("/api/schedule")
def schedule():
    rows = db.query("SELECT u.*, p.title AS project_title FROM uploads u LEFT JOIN projects p ON p.id=u.project_id "
                    "WHERE u.publish_at IS NOT NULL ORDER BY u.publish_at")
    ready = [r for r in projects.list_all() if r["status"] in ("approved", "ready_for_review")]
    return {"scheduled": rows, "ready": ready, "channel": db.get_setting("channel")}


@app.get("/api/analytics")
def analytics(days: int = 28):
    out: dict[str, Any] = {"connected": False}
    try:
        st = youtube.status()
        if not st["connected"]:
            out["message"] = "Connect YouTube in the Upload Manager to see analytics."
            return out
        out["connected"] = True
        out["channel"] = youtube.refresh_channel()
        ids = [r["video_id"] for r in youtube.history() if r.get("video_id")]
        out["videos"] = youtube.video_stats(list(dict.fromkeys(ids)))
        try:
            out["report"] = youtube.analytics_report(days)
        except youtube.YouTubeError as e:
            out["report_error"] = str(e)
    except youtube.YouTubeError as e:
        out["error"] = str(e)
    return out


# ---------------- autopilot ----------------
@app.get("/api/autopilot")
def autopilot_get():
    return autopilot.status()


@app.put("/api/autopilot")
def autopilot_put(values: dict = Body(...)):
    try:
        return autopilot.save(values)
    except ValueError as e:
        _err(e)


@app.post("/api/autopilot/run")
def autopilot_run():
    return {"job_id": jobs.submit("autopilot", lambda progress, cancel: autopilot.run_once(progress, cancel))}


# ---------------- static dashboard ----------------
if (config.WEB_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=config.WEB_DIST / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "unknown API route")
    index = config.WEB_DIST / "index.html"
    if index.exists():
        return FileResponse(index)
    return HTMLResponse("<h1>Dashboard not built</h1><p>The API is running. Build the frontend with "
                        "<code>cd frontend && npm install && npm run build</code>, or use the CLI.</p>")


def serve(host: str | None = None, port: int | None = None, open_browser: bool = False) -> None:
    import threading
    import webbrowser

    import uvicorn
    host = host or config.env("YTAUTO_HOST")
    port = int(port or config.env("PORT", "") or config.env("YTAUTO_PORT"))  # PORT = set by cloud hosts
    if host not in ("127.0.0.1", "localhost", "::1") and not auth.enabled():
        raise SystemExit("Refusing to listen on a public address without a password. Set APP_PASSWORD "
                         "(and keep YTAUTO_HOST=127.0.0.1 for local-only use).")
    (config.DATA_DIR / "server.pid").write_text(str(__import__("os").getpid()))
    if open_browser:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}")).start()
    uvicorn.run(app, host=host, port=port, log_level="info", proxy_headers=True, forwarded_allow_ips="*")
