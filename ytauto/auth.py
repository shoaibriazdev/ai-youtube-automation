"""Password protection for online deployments.

Locally (127.0.0.1) no password is needed. When APP_PASSWORD is set, every page and API route
(except /login and /api/health) requires a signed session cookie. `serve()` refuses to listen on a
public interface without APP_PASSWORD, so the dashboard can never be exposed unprotected by accident.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import time
import urllib.parse

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import config

COOKIE = "ytauto_session"
MAX_AGE = 14 * 86400
PUBLIC_PATHS = {"/login", "/logout", "/api/health", "/favicon.ico"}
_failures: dict[str, list[float]] = {}


def enabled() -> bool:
    return bool(config.env("APP_PASSWORD"))


def _secret() -> bytes:
    base = (config.env("APP_SECRET") or "") + "|" + (config.env("APP_PASSWORD") or "")
    return hashlib.sha256(("ytauto-session-v1|" + base).encode()).digest()


def make_token(now: float | None = None) -> str:
    exp = int((time.time() if now is None else now) + MAX_AGE)
    sig = hmac.new(_secret(), str(exp).encode(), hashlib.sha256).hexdigest()
    return f"{exp}.{sig}"


def valid_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    exp, sig = token.split(".", 1)
    if not exp.isdigit() or int(exp) < time.time():
        return False
    good = hmac.new(_secret(), exp.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, sig)


def check_password(pw: str) -> bool:
    want = config.env("APP_PASSWORD") or ""
    return bool(want) and hmac.compare_digest(pw.encode(), want.encode())


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


def _locked(ip: str) -> bool:
    recent = [t for t in _failures.get(ip, []) if t > time.time() - 900]
    _failures[ip] = recent
    return len(recent) >= 10  # 10 wrong passwords in 15 minutes -> wait


LOGIN_HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign in - AI YouTube Automation Pro</title><style>
:root{{--bg:#f4f5f8;--panel:#fff;--text:#151821;--muted:#667085;--line:#e3e6ec}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0e1015;--panel:#161a22;--text:#e8eaf0;--muted:#98a2b3;--line:#2a303c}}}}
body{{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);font-family:Inter,"Segoe UI",system-ui,sans-serif;padding:16px}}
form{{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:28px;width:100%;max-width:360px}}
.mark{{width:40px;height:40px;border-radius:10px;background:linear-gradient(135deg,#ff3b3b,#ff7a45);color:#fff;display:grid;place-items:center;margin-bottom:12px}}
h1{{font-size:18px;margin:0 0 4px}}p{{color:var(--muted);font-size:13px;margin:0 0 18px}}
input{{width:100%;box-sizing:border-box;padding:10px;border-radius:8px;border:1px solid var(--line);background:transparent;color:var(--text);font:inherit}}
button{{margin-top:12px;width:100%;padding:10px;border:0;border-radius:8px;background:linear-gradient(135deg,#ff3b3b,#ff7a45);color:#fff;font-weight:600;cursor:pointer;font:inherit}}
.err{{color:#d92d20;font-size:13px;margin-top:10px}}</style></head><body>
<form method="post" action="/login"><div class="mark">&#9654;</div><h1>AI YouTube Automation Pro</h1><p>Enter the dashboard password.</p>
<input type="password" name="password" autofocus autocomplete="current-password" placeholder="Password" required>
<input type="hidden" name="next" value="{next}"><button type="submit">Sign in</button>{error}</form></body></html>"""


def login_page(error: str = "", next_url: str = "/") -> HTMLResponse:
    err = f'<div class="err">{html.escape(error)}</div>' if error else ""
    return HTMLResponse(LOGIN_HTML.format(error=err, next=html.escape(next_url, quote=True)),
                        status_code=401 if error else 200)


async def handle_login(request: Request):
    ip = _client_ip(request)
    form = urllib.parse.parse_qs((await request.body()).decode("utf-8", "replace"))
    pw = (form.get("password") or [""])[0]
    nxt = (form.get("next") or ["/"])[0]
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/"
    if _locked(ip):
        return login_page("Too many attempts. Try again in 15 minutes.", nxt)
    if not check_password(pw):
        _failures.setdefault(ip, []).append(time.time())
        await asyncio.sleep(1)
        return login_page("Wrong password.", nxt)
    _failures.pop(ip, None)
    resp = RedirectResponse(nxt, status_code=303)
    secure = request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
    resp.set_cookie(COOKIE, make_token(), max_age=MAX_AGE, httponly=True, samesite="lax", secure=secure)
    return resp


def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(COOKIE)
    return resp


async def middleware(request: Request, call_next):
    if not enabled():
        return await call_next(request)
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/assets/"):
        return await call_next(request)
    if valid_token(request.cookies.get(COOKIE)):
        return await call_next(request)
    if path.startswith("/api/"):
        return JSONResponse({"detail": "Not signed in"}, status_code=401)
    target = path + (("?" + request.url.query) if request.url.query else "")
    return RedirectResponse("/login?next=" + urllib.parse.quote(target), status_code=303)
