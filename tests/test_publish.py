"""SEO rules, YouTube safety gates, provider credential errors and the HTTP API."""
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from ytauto import projects, seo, youtube
from ytauto.providers import image as image_p, tts as tts_p, video as video_p
from ytauto.providers.base import MissingCredentials


# ---------------- SEO ----------------
def test_chapters_follow_youtube_rules():
    script = {"scenes": [{"n": i, "on_screen_text": f"PART {i}", "action": ""} for i in range(1, 9)]}
    tl = {"scenes": [{"n": i, "start": (i - 1) * 6.0, "duration": 6.0} for i in range(1, 9)]}
    ch = seo.chapters_from_timeline(script, tl)
    assert ch["valid"] and ch["chapters"][0]["label"] == "0:00"
    assert all(c["seconds"] >= 10 for c in ch["chapters"]) and len(ch["chapters"]) >= 3
    short = {"scenes": [{"n": 1, "start": 0, "duration": 8}, {"n": 2, "start": 8, "duration": 7}]}
    assert not seo.chapters_from_timeline(script, short)["valid"]


def test_tags_and_hashtags():
    tags = seo._clean_tags(["funny cat"] * 3 + [f"tag number {i}" for i in range(40)])
    assert len(tags) <= 15 and sum(len(t) + 3 for t in tags) <= 500 and tags.count("funny cat") == 1
    assert seo._hashtags(["funny cat", "office comedy"], vertical=True)[0] == "#Shorts"


# ---------------- YouTube gates (no network needed) ----------------
def _approved_project():
    p = projects.create("upload gate", "short")
    p["seo"] = {"title": "T", "description": "D", "tags": [], "category_id": "23"}
    p["render"] = {"outputs": {"9:16": {"file": "render/x.mp4"}}}
    projects.save(p)
    return p


def test_upload_requires_approval():
    p = _approved_project()
    with pytest.raises(youtube.YouTubeError, match="approved"):
        youtube.upload(p["id"])


def test_public_requires_confirmation():
    p = _approved_project()
    projects.update_row(p["id"], approved=1)
    with pytest.raises(youtube.YouTubeError, match="confirm"):
        youtube.upload(p["id"], privacy="public")
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    with pytest.raises(youtube.YouTubeError, match="confirm"):
        youtube.upload(p["id"], publish_at=future)


def test_publish_at_validation_and_body():
    with pytest.raises(youtube.YouTubeError):
        youtube._validate_publish_at("2020-01-01T10:00:00+00:00")
    with pytest.raises(youtube.YouTubeError, match="timezone"):
        youtube._validate_publish_at("2030-01-01T10:00:00")
    when = youtube._validate_publish_at((datetime.now(timezone.utc) + timedelta(days=1)).isoformat())
    body = youtube.build_body({"title": "x" * 150, "tags": ["a"], "made_for_kids": False}, "public", when)
    assert body["status"]["privacyStatus"] == "private" and body["status"]["publishAt"] == when
    assert len(body["snippet"]["title"]) == 100 and body["status"]["selfDeclaredMadeForKids"] is False


def test_not_connected_is_explained():
    st = youtube.status()
    assert st["connected"] is False and st["client_secrets_found"] is False
    with pytest.raises(youtube.YouTubeError, match="OAuth client file not found"):
        youtube.connect(open_browser=False)


# ---------------- providers ----------------
@pytest.mark.parametrize("prov", ["openai", "stability", "replicate"])
def test_paid_image_providers_need_keys(tmp_path, prov):
    with pytest.raises(MissingCredentials):
        image_p.generate(prov, "a cat", tmp_path / "x.png")


@pytest.mark.parametrize("prov", ["runway", "luma", "replicate"])
def test_paid_video_providers_need_keys(tmp_path, prov):
    img = tmp_path / "i.png"
    img.write_bytes(b"x")
    with pytest.raises(MissingCredentials):
        video_p.generate(prov, "a cat", img, tmp_path / "x.mp4")


@pytest.mark.parametrize("prov", ["elevenlabs", "openai"])
def test_paid_tts_need_keys(tmp_path, prov):
    from ytauto import characters
    with pytest.raises(MissingCredentials):
        tts_p.synthesize(prov, "hello", characters.lookup("biscuit"), tmp_path / "v")


def test_kenburns_needs_no_call(tmp_path):
    assert video_p.generate("kenburns", "x", None, tmp_path / "x.mp4") is None


# ---------------- HTTP API ----------------
@pytest.fixture(scope="module")
def client():
    from ytauto.server import app
    with TestClient(app) as c:
        yield c


def test_api_basics(client):
    assert client.get("/api/health").json()["ok"]
    s = client.get("/api/settings").json()
    assert "storyboard" in s["options"]["image"]
    sec = client.get("/api/secrets").json()
    assert all("masked" in x for x in sec["secrets"])
    assert all(len(x["masked"]) <= 10 for x in sec["secrets"])
    assert client.put("/api/settings/nope", json={}).status_code == 404
    assert client.get("/api/overview").status_code == 200


def test_api_pipeline_job_and_file_safety(client, free_providers):
    p = client.post("/api/projects", json={"title": "API test", "format": "short"}).json()
    jid = client.post(f"/api/projects/{p['id']}/run", json={"stages": ["research", "script", "characters", "images"]}).json()["job_id"]
    for _ in range(120):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed"):
            break
        time.sleep(0.5)
    assert j["status"] == "done", j
    proj = client.get(f"/api/projects/{p['id']}").json()
    rel = proj["assets"]["images"]["1"]
    assert client.get(f"/api/projects/{p['id']}/file/{rel}").status_code == 200
    assert client.get(f"/api/projects/{p['id']}/file/../../data/ytauto.db").status_code == 404
    # cannot approve before rendering, cannot upload before approval
    assert client.post(f"/api/projects/{p['id']}/approve").status_code == 400
    assert client.post(f"/api/projects/{p['id']}/upload", json={}).status_code == 400


def test_api_ideas_and_characters(client, free_providers):
    jid = client.post("/api/ideas", json={"n": 4, "use_trends": False}).json()["job_id"]
    for _ in range(60):
        j = client.get(f"/api/jobs/{jid}").json()
        if j["status"] in ("done", "failed"):
            break
        time.sleep(0.3)
    assert j["status"] == "done", j
    assert len(client.get("/api/ideas").json()) >= 4
    c = client.post("/api/characters", json={"name": "Pickles", "species": "hamster", "visual_dna": "a tiny hamster"}).json()
    assert c["id"] == "pickles" and c["seed"] > 0
    assert any(x["id"] == "pickles" for x in client.get("/api/characters").json())
    assert client.delete("/api/characters/pickles").status_code == 200
