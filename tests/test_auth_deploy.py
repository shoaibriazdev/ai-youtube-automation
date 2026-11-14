"""Online deployment: password login, refusal to run unprotected, web OAuth, pasted client JSON."""
import json

import pytest
from fastapi.testclient import TestClient

from ytauto import auth, server, youtube


@pytest.fixture()
def locked(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "correct horse battery")
    auth._failures.clear()
    with TestClient(server.app) as c:
        yield c


def test_everything_requires_login(locked):
    c = locked
    assert c.get("/api/health").status_code == 200
    assert c.get("/api/settings").status_code == 401
    r = c.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert c.get("/login").status_code == 200


def test_wrong_then_right_password(locked):
    c = locked
    r = c.post("/login", data={"password": "nope", "next": "/"}, follow_redirects=False)
    assert r.status_code == 401 and auth.COOKIE not in r.cookies
    r = c.post("/login", data={"password": "correct horse battery", "next": "//evil.com"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert c.get("/api/settings").status_code == 200
    c.get("/logout")
    c.cookies.clear()
    assert c.get("/api/settings").status_code == 401


def test_tokens_expire_and_change_with_password(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "one")
    t = auth.make_token()
    assert auth.valid_token(t) and not auth.valid_token(t + "x")
    assert not auth.valid_token(auth.make_token(now=0))
    monkeypatch.setenv("APP_PASSWORD", "two")
    assert not auth.valid_token(t)


def test_refuses_public_bind_without_password(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "")
    with pytest.raises(SystemExit, match="APP_PASSWORD"):
        server.serve(host="0.0.0.0", port=8999)


def test_client_secret_and_web_flow():
    with pytest.raises(youtube.YouTubeError):
        youtube.save_client_secret({"foo": 1})
    web = {"web": {"client_id": "123.apps.googleusercontent.com", "client_secret": "s", "project_id": "p",
                   "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
                   "redirect_uris": ["https://x.up.railway.app/api/youtube/oauth/callback"]}}
    assert youtube.save_client_secret(web)["type"] == "web"
    url = youtube.web_flow_start("https://x.up.railway.app/api/youtube/oauth/callback")
    assert url.startswith("https://accounts.google.com/") and "youtube.upload" in url and "redirect_uri=" in url
    with pytest.raises(youtube.YouTubeError, match="expired"):
        youtube.web_flow_finish("unknown-state", "https://x/cb?code=1&state=unknown-state")
    assert youtube.status()["client_type"] == "web"
    youtube.client_secrets_file().unlink()
