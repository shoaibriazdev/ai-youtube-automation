"""STEP 9 - YouTube Data API v3: OAuth, upload, thumbnail, schedule, history, analytics.

Safety rules enforced in code:
  * Uploads default to PRIVATE.
  * A project must be explicitly approved (after you watched it) before ANY upload.
  * 'public' or a scheduled publish time additionally requires `confirm_public=True`, which the
    dashboard/CLI only sends after you confirm in a separate prompt.
  * OAuth client secrets and tokens live in data/secrets/ (git-ignored), never in source code.
"""
from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config, db, projects

SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly",
          "https://www.googleapis.com/auth/yt-analytics.readonly"]
TOKEN_FILE = config.SECRETS_DIR / "youtube_token.json"
RETRIABLE_STATUS = (500, 502, 503, 504)


class YouTubeError(RuntimeError):
    pass


def client_secrets_file() -> Path:
    p = Path(config.env("GOOGLE_CLIENT_SECRETS_FILE"))
    return p if p.is_absolute() else (config.ROOT / p)


def status() -> dict:
    cs = client_secrets_file()
    out = {"client_secrets_found": cs.exists(), "client_secrets_path": str(cs), "connected": False,
           "token_path": str(TOKEN_FILE), "channel": None, "oauth_in_progress": _flow_state.get("running", False),
           "last_oauth_error": _flow_state.get("error"), "client_type": None}
    if cs.exists():
        try:
            out["client_type"] = "web" if "web" in json.loads(cs.read_text(encoding="utf-8")) else "desktop"
        except ValueError:
            out["client_type"] = "invalid"
    if TOKEN_FILE.exists():
        try:
            creds = _credentials(refresh=True)
            out["connected"] = bool(creds and creds.valid)
            ch = db.get_setting("youtube_channel")
            out["channel"] = ch if isinstance(ch, dict) else None
        except YouTubeError as e:
            out["error"] = str(e)
    return out


def _credentials(refresh: bool = True):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    if not TOKEN_FILE.exists():
        raise YouTubeError("YouTube is not connected. Open Upload Manager -> Connect YouTube "
                           "(or run: ytauto youtube connect). See docs/YOUTUBE_OAUTH.md.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if refresh and not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError as e:
                raise YouTubeError("YouTube authorization expired or was revoked. Connect again.") from e
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        else:
            raise YouTubeError("Stored YouTube token is invalid. Connect again.")
    return creds


_flow_state: dict = {}


def connect(open_browser: bool = True, port: int = 8765, blocking: bool = True) -> dict:
    """Run Google's installed-app OAuth flow (opens your browser, local redirect on `port`)."""
    cs = client_secrets_file()
    if not cs.exists():
        raise YouTubeError(f"OAuth client file not found at {cs}. Create an OAuth client ID (type: Desktop app) "
                           "in Google Cloud Console, download the JSON and save it there. See docs/YOUTUBE_OAUTH.md.")
    from google_auth_oauthlib.flow import InstalledAppFlow

    def run():
        _flow_state.update(running=True, error=None)
        try:
            flow = InstalledAppFlow.from_client_secrets_file(str(cs), SCOPES)
            creds = flow.run_local_server(port=port, open_browser=open_browser, prompt="consent",
                                          authorization_prompt_message="Opening Google sign-in: {url}",
                                          success_message="YouTube connected. You can close this tab and return to the dashboard.",
                                          timeout_seconds=600)
            TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
            try:
                refresh_channel()
            except Exception as e:  # noqa: BLE001
                db.log_event(None, "youtube", f"Connected, but channel lookup failed: {e}", "warning")
            db.log_event(None, "youtube", "YouTube account connected")
        except Exception as e:  # noqa: BLE001
            _flow_state["error"] = str(e)
            db.log_event(None, "youtube", f"OAuth failed: {e}", "error")
        finally:
            _flow_state["running"] = False

    if blocking:
        run()
        if _flow_state.get("error"):
            raise YouTubeError(_flow_state["error"])
        return status()
    if _flow_state.get("running"):
        return {"started": False, "message": "OAuth already in progress - finish it in your browser."}
    threading.Thread(target=run, daemon=True).start()
    return {"started": True, "message": "A Google sign-in tab is opening in your browser. Approve access, then come back."}


_web_flows: dict[str, tuple[float, object]] = {}


def save_client_secret(data: dict) -> dict:
    """Store a pasted OAuth client JSON (used by online deployments where there is no file explorer)."""
    if not isinstance(data, dict) or not ({"web", "installed"} & set(data)):
        raise YouTubeError("That is not an OAuth client JSON (expected a 'web' or 'installed' section). "
                           "Download it from Google Cloud > Credentials > your OAuth client > Download JSON.")
    inner = data.get("web") or data.get("installed")
    if not inner.get("client_id") or not inner.get("client_secret"):
        raise YouTubeError("The JSON is missing client_id or client_secret.")
    f = client_secrets_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data), encoding="utf-8")
    db.log_event(None, "youtube", f"OAuth client saved ({'web' if 'web' in data else 'desktop'} type)")
    return {"saved": True, "type": "web" if "web" in data else "desktop", "path": str(f)}


def web_flow_start(redirect_uri: str) -> str:
    """Start the browser-redirect OAuth flow; returns Google's consent URL."""
    cs = client_secrets_file()
    if not cs.exists():
        raise YouTubeError("No OAuth client yet. In API Settings, paste the 'Web application' OAuth client JSON "
                           "(see docs/DEPLOY.md).")
    if "web" not in json.loads(cs.read_text(encoding="utf-8")):
        raise YouTubeError("Online sign-in needs an OAuth client of type 'Web application' with the redirect URI "
                           f"{redirect_uri}. The saved client is a Desktop client.")
    from google_auth_oauthlib.flow import Flow
    flow = Flow.from_client_secrets_file(str(cs), scopes=SCOPES, redirect_uri=redirect_uri)
    url, state = flow.authorization_url(access_type="offline", prompt="consent", include_granted_scopes="true")
    now = time.time()
    for k in [k for k, (t, _) in _web_flows.items() if t < now - 900]:
        _web_flows.pop(k, None)
    _web_flows[state] = (now, flow)
    return url


def web_flow_finish(state: str, authorization_response: str) -> dict:
    entry = _web_flows.pop(state, None)
    if not entry:
        raise YouTubeError("Sign-in session expired or unknown. Click Connect YouTube again.")
    flow = entry[1]
    try:
        flow.fetch_token(authorization_response=authorization_response)
    except Exception as e:  # noqa: BLE001
        raise YouTubeError(f"Google rejected the sign-in: {e}") from e
    TOKEN_FILE.write_text(flow.credentials.to_json(), encoding="utf-8")
    try:
        refresh_channel()
    except Exception as e:  # noqa: BLE001
        db.log_event(None, "youtube", f"Connected, but channel lookup failed: {e}", "warning")
    db.log_event(None, "youtube", "YouTube account connected (web sign-in)")
    return status()


def disconnect() -> None:
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
    db.set_setting("youtube_channel", None)


def _service(name="youtube", version="v3"):
    from googleapiclient.discovery import build
    return build(name, version, credentials=_credentials(), cache_discovery=False)


def refresh_channel() -> dict:
    resp = _service().channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
    items = resp.get("items", [])
    if not items:
        raise YouTubeError("This Google account has no YouTube channel. Create one at youtube.com first.")
    ch = items[0]
    info = {"id": ch["id"], "title": ch["snippet"]["title"], "thumbnail": ch["snippet"]["thumbnails"].get("default", {}).get("url"),
            "subscribers": ch["statistics"].get("subscriberCount"), "views": ch["statistics"].get("viewCount"),
            "videos": ch["statistics"].get("videoCount"),
            "uploads_playlist": ch.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")}
    db.set_setting("youtube_channel", info)
    return info


def _validate_publish_at(publish_at: str | None) -> str | None:
    if not publish_at:
        return None
    try:
        dt = datetime.fromisoformat(publish_at.replace("Z", "+00:00"))
    except ValueError as e:
        raise YouTubeError("publish_at must be ISO 8601, e.g. 2026-11-20T17:00:00-05:00") from e
    if dt.tzinfo is None:
        raise YouTubeError("publish_at needs a timezone offset, e.g. 2026-11-20T17:00:00-05:00")
    if dt <= datetime.now(timezone.utc):
        raise YouTubeError("publish_at must be in the future")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build_body(seo: dict, privacy: str, publish_at: str | None) -> dict:
    status_ = {"privacyStatus": "private" if publish_at else privacy,
               "selfDeclaredMadeForKids": bool(seo.get("made_for_kids", False)),
               "containsSyntheticMedia": bool(seo.get("contains_synthetic_media", True)),
               "embeddable": True, "license": "youtube"}
    if publish_at:
        status_["publishAt"] = publish_at
    return {"snippet": {"title": seo["title"][:100], "description": seo.get("description", "")[:5000],
                        "tags": seo.get("tags", []), "categoryId": str(seo.get("category_id", "23")),
                        "defaultLanguage": seo.get("default_language", "en"),
                        "defaultAudioLanguage": seo.get("default_language", "en")},
            "status": status_}


def upload(pid: str, privacy: str = "private", publish_at: str | None = None, aspect: str | None = None,
           confirm_public: bool = False, progress=None) -> dict:
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload

    if privacy not in ("private", "unlisted", "public"):
        raise YouTubeError("privacy must be private, unlisted or public")
    row = projects.row(pid)
    if not row.get("approved"):
        raise YouTubeError("This video has not been approved. Watch it in Production History / Video Editor "
                           "and click Approve before uploading.")
    publish_at = _validate_publish_at(publish_at)
    if (privacy == "public" or publish_at) and not confirm_public:
        raise YouTubeError("Public or scheduled publishing needs your explicit confirmation (confirm_public).")
    p = projects.load(pid)
    if not p.get("seo"):
        raise YouTubeError("No SEO metadata yet. Run the SEO step first.")
    outputs = (p.get("render") or {}).get("outputs") or {}
    aspect = aspect or ("9:16" if p["format"] == "short" else "16:9")
    out = outputs.get(aspect) or next(iter(outputs.values()), None)
    if not out:
        raise YouTubeError("No rendered video. Run the edit step first.")
    video_path = projects.abspath(pid, out["file"])
    body = build_body(p["seo"], privacy, publish_at)
    yt = _service()
    uid = db.execute("INSERT INTO uploads(project_id,privacy,publish_at,status,ts,title) VALUES(?,?,?,?,?,?)",
                     (pid, body["status"]["privacyStatus"], publish_at, "uploading", time.time(), body["snippet"]["title"]))
    projects.update_row(pid, status="uploading")
    say = progress or (lambda *_: None)
    try:
        media = MediaFileUpload(str(video_path), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media, notifySubscribers=privacy == "public")
        response, retry = None, 0
        while response is None:
            try:
                st, response = req.next_chunk()
                if st:
                    say(0.05 + 0.85 * st.progress(), f"Uploading {int(st.progress() * 100)}%")
            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS and retry < 8:
                    retry += 1
                    time.sleep(min(64, 2 ** retry) + random.random())
                    continue
                raise
            except (ConnectionError, TimeoutError, OSError):
                if retry < 8:
                    retry += 1
                    time.sleep(min(64, 2 ** retry) + random.random())
                    continue
                raise
        vid = response["id"]
        thumb_status = "skipped"
        thumb = (p.get("thumbnail") or {}).get("jpg")
        if thumb and projects.abspath(pid, thumb).exists():
            say(0.93, "Setting custom thumbnail")
            try:
                yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(projects.abspath(pid, thumb)),
                                                                            mimetype="image/jpeg")).execute()
                thumb_status = "set"
            except HttpError as e:
                thumb_status = f"failed: {_http_reason(e)}"
                if e.resp.status == 403:
                    thumb_status += " (custom thumbnails need a phone-verified channel)"
        srt = out.get("srt")
        url = f"https://www.youtube.com/watch?v={vid}" if aspect == "16:9" else f"https://youtube.com/shorts/{vid}"
        final_status = "scheduled" if publish_at else "uploaded"
        db.execute("UPDATE uploads SET video_id=?, status=?, url=?, thumbnail_status=? WHERE id=?",
                   (vid, final_status, url, thumb_status, uid))
        projects.update_row(pid, status=final_status, error=None)
        p["youtube"] = {"video_id": vid, "url": url, "privacy": body["status"]["privacyStatus"],
                        "publish_at": publish_at, "uploaded": time.time(), "thumbnail": thumb_status,
                        "captions_file": srt}
        projects.save(p)
        db.log_event(pid, "upload", f"Uploaded {vid} as {body['status']['privacyStatus']}"
                     + (f", scheduled {publish_at}" if publish_at else "") + f"; thumbnail {thumb_status}")
        say(1.0, "Upload complete")
        return p["youtube"]
    except HttpError as e:
        msg = _http_reason(e)
        if "quotaExceeded" in str(e):
            msg = "YouTube API daily quota exceeded. Try again tomorrow or request more quota."
        elif "uploadLimitExceeded" in str(e):
            msg = "YouTube upload limit reached for this channel today."
        db.execute("UPDATE uploads SET status=?, error=? WHERE id=?", ("failed", msg, uid))
        projects.update_row(pid, status="failed", error=msg)
        db.log_event(pid, "upload", f"Upload failed: {msg}", "error")
        raise YouTubeError(msg) from e
    except Exception as e:
        db.execute("UPDATE uploads SET status=?, error=? WHERE id=?", ("failed", str(e), uid))
        projects.update_row(pid, status="failed", error=str(e))
        db.log_event(pid, "upload", f"Upload failed: {e}", "error")
        raise


def _http_reason(e) -> str:
    try:
        data = json.loads(e.content.decode())
        return data["error"]["message"]
    except Exception:  # noqa: BLE001
        return str(e)


def schedule_existing(pid: str, publish_at: str, confirm_public: bool = False) -> dict:
    """Set/replace the publish time of an already-uploaded private video."""
    if not confirm_public:
        raise YouTubeError("Scheduling makes the video public at that time - confirm_public is required.")
    p = projects.load(pid)
    vid = (p.get("youtube") or {}).get("video_id")
    if not vid:
        raise YouTubeError("This project has not been uploaded yet.")
    when = _validate_publish_at(publish_at)
    yt = _service()
    cur = yt.videos().list(part="status", id=vid).execute()["items"][0]["status"]
    cur.update({"privacyStatus": "private", "publishAt": when})
    yt.videos().update(part="status", body={"id": vid, "status": cur}).execute()
    p["youtube"].update(publish_at=when, privacy="private")
    projects.save(p)
    projects.update_row(pid, status="scheduled")
    db.execute("INSERT INTO uploads(project_id,video_id,privacy,publish_at,status,ts,title,url) VALUES(?,?,?,?,?,?,?,?)",
               (pid, vid, "private", when, "scheduled", time.time(), p["seo"].get("title"), p["youtube"].get("url")))
    db.log_event(pid, "schedule", f"Scheduled {vid} for {when}")
    return p["youtube"]


def history(limit: int = 200) -> list[dict]:
    return db.query("SELECT * FROM uploads ORDER BY id DESC LIMIT ?", (limit,))


def video_stats(video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    yt = _service()
    out = []
    for i in range(0, len(video_ids), 50):
        resp = yt.videos().list(part="snippet,statistics,status", id=",".join(video_ids[i:i + 50])).execute()
        for v in resp.get("items", []):
            s = v.get("statistics", {})
            out.append({"video_id": v["id"], "title": v["snippet"]["title"], "published": v["snippet"].get("publishedAt"),
                        "privacy": v["status"].get("privacyStatus"), "views": int(s.get("viewCount", 0)),
                        "likes": int(s.get("likeCount", 0) or 0), "comments": int(s.get("commentCount", 0) or 0)})
    return out


def analytics_report(days: int = 28) -> dict:
    """Channel-level YouTube Analytics for the last `days` days (needs yt-analytics.readonly scope)."""
    from datetime import date, timedelta
    from googleapiclient.errors import HttpError
    end = date.today()
    start = end - timedelta(days=days)
    try:
        ya = _service("youtubeAnalytics", "v2")
        resp = ya.reports().query(ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
                                  metrics="views,estimatedMinutesWatched,averageViewDuration,subscribersGained,likes",
                                  dimensions="day", sort="day").execute()
    except HttpError as e:
        raise YouTubeError(f"YouTube Analytics API error: {_http_reason(e)} (enable 'YouTube Analytics API' "
                           "in Google Cloud and reconnect).") from e
    cols = [c["name"] for c in resp.get("columnHeaders", [])]
    rows = [dict(zip(cols, r)) for r in resp.get("rows", [])]
    totals = {c: sum(r.get(c, 0) for r in rows) for c in cols if c != "day"}
    if rows:
        totals["averageViewDuration"] = round(sum(r.get("averageViewDuration", 0) for r in rows) / len(rows), 1)
    return {"start": start.isoformat(), "end": end.isoformat(), "rows": rows, "totals": totals}
