"""Config, storage, characters, research, scripts, costs and the approval gates."""
import pytest

from ytauto import characters, config, costs, db, legacy, pipeline, projects, research, scriptgen


def test_imports_and_paths():
    import ytauto.cli, ytauto.server, ytauto.youtube, ytauto.editor  # noqa: F401
    assert config.DB_PATH.parent.exists()
    assert "ytauto_test_" in str(config.DATA_DIR), "tests must not use the real data folder"


def test_settings_merge_defaults():
    db.set_setting("channel", {"name": "Test Channel"})
    ch = db.get_setting("channel")
    assert ch["name"] == "Test Channel" and ch["category_id"] == "23" and ch["default_privacy"] == "private"


def test_env_writer_whitelist(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    written = config.write_env_values({"YOUTUBE_API_KEY": "abc12345678", "EVIL_KEY": "x"})
    assert written == ["YOUTUBE_API_KEY"]
    text = (tmp_path / ".env").read_text()
    assert "YOUTUBE_API_KEY=abc12345678" in text and "EVIL_KEY" not in text
    with pytest.raises(ValueError):
        config.write_env_values({"YOUTUBE_API_KEY": "a\nINJECT=1"})
    config.write_env_values({"YOUTUBE_API_KEY": ""})
    assert config.mask("abcdefghijkl").endswith("ijkl")


def test_default_characters():
    chars = characters.all_characters()
    ids = {c["id"] for c in chars}
    assert {"biscuit", "waffles", "nugget", "gary", "boss_hoot", "narrator"} <= ids
    b = characters.lookup("Biscuit")
    assert b["seed"] == characters.lookup("biscuit")["seed"]
    assert b["visual_dna"] in characters.image_prompt(b)


def test_legacy_bridge():
    h = legacy.score_hook("You are losing viewers in the first 3 seconds, and here is why.")
    assert h["band"] in ("STRONG", "WORKABLE", "WEAK")
    t = legacy.lint_title("Biscuit vs the Robot Vacuum", "WHO WON")
    assert isinstance(t["issues"], list)


def test_offline_ideas_scored(free_providers):
    r = research.generate_ideas(10, "short", use_trends=False, seed=42)
    assert r["provider"] == "offline" and len(r["ideas"]) == 10
    scores = [i["total_score"] for i in r["ideas"]]
    assert scores == sorted(scores, reverse=True)
    for i in r["ideas"]:
        assert 0 <= i["appeal_score"] <= 100 and 0 <= i["feasibility_score"] <= 100
        assert all(characters.lookup(c) for c in i["characters"])
    assert research.trend_signals()["available"] is False  # no key -> honest "not available"


def test_offline_script_structure(free_providers):
    idea = research.generate_ideas(3, "short", use_trends=False, seed=1)["ideas"][0]
    s = scriptgen.generate(idea, "short")
    assert s["hook"] and s["scenes"][0]["dialogue"][0]["line"] == s["hook"]
    assert 5 <= len(s["scenes"]) <= 8
    for sc in s["scenes"]:
        assert sc["visual"] and sc["dialogue"]
        for d in sc["dialogue"]:
            assert characters.lookup(d["character"]) and d["delivery"] is not None
    assert "Scene 1" in scriptgen.to_text(s)
    long = scriptgen.generate(idea, "long")
    assert len(long["scenes"]) > len(s["scenes"])


def test_cost_estimates():
    free = costs.estimate(providers={"llm": "offline", "image": "storyboard", "video": "kenburns", "tts": "edge"})
    assert free["total_usd"] == 0 or free["llm_model"] != "offline"
    paid = costs.estimate(providers={"llm": "offline", "image": "openai", "video": "runway", "tts": "elevenlabs"})
    assert paid["total_usd"] > 0
    stages = {i["stage"] for i in paid["items"]}
    assert {"images", "video", "voice"} <= stages


def test_paid_provider_pauses_for_approval(free_providers):
    """Selecting a paid provider must stop BEFORE any paid call, until the user approves."""
    db.set_setting("providers", {"llm": "offline", "image": "openai", "video": "kenburns", "tts": "silent"})
    p = projects.create("gate test", "short")
    res = pipeline.run(p["id"], ["research", "script", "images"])
    assert res.get("needs_approval") and res["estimate"]["total_usd"] > 0
    assert projects.row(p["id"])["status"] == "awaiting_cost_approval"
    assert not projects.load(p["id"])["assets"]["images"], "no image may be generated before approval"
    pipeline.approve_cost(p["id"])
    # approved -> runs, and the missing key now fails with a clear message instead of spending
    with pytest.raises(Exception) as e:
        pipeline.run(p["id"], ["research", "script", "images"])
    assert "OPENAI_API_KEY" in str(e.value)
    assert projects.row(p["id"])["status"] == "failed"


def test_anthropic_selected_without_key_is_clear():
    from ytauto import llm
    db.set_setting("providers", {**db.get_setting("providers"), "llm": "anthropic"})
    with pytest.raises(llm.LLMError, match="ANTHROPIC_API_KEY"):
        llm.active_provider()
    db.set_setting("providers", {**db.get_setting("providers"), "llm": "auto"})
    assert llm.active_provider() == "offline"


def test_project_lifecycle():
    p = projects.create("Lifecycle", "long")
    assert projects.row(p["id"])["status"] == "draft"
    with pytest.raises(ValueError):
        projects.create("bad", "square")
    projects.delete(p["id"])
    with pytest.raises(KeyError):
        projects.load(p["id"])
