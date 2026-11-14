"""FFmpeg integration, audio synthesis, storyboard images, thumbnails and real end-to-end renders."""
import re
import subprocess

import numpy as np
import pytest
from PIL import Image

from ytauto import audio, editor, ffmpeg, pipeline, projects, thumbnail
from ytauto.providers import image as image_p


def probe(path):
    """Return (width, height, duration) by asking ffmpeg to read the file."""
    p = subprocess.run([ffmpeg.binary(), "-hide_banner", "-i", str(path)], capture_output=True, text=True)
    m = re.search(r"Video:.*?(\d{3,4})x(\d{3,4})", p.stderr)
    has_audio = "Audio:" in p.stderr
    return int(m.group(1)), int(m.group(2)), ffmpeg.media_duration(path), has_audio


def test_ffmpeg_available():
    assert "ffmpeg version" in ffmpeg.version()
    assert ffmpeg.has_filter("xfade") and ffmpeg.has_filter("zoompan")


def test_sfx_and_music():
    for name in audio.SFX_NAMES:
        x = audio.synth_sfx(name)
        assert x.size > 1000 and np.max(np.abs(x)) <= 1.0
    m = audio.synth_music("sneaky", 5)
    assert abs(m.size / audio.SR - 5) < 0.01


def test_mix_ducks_music_under_voice():
    tone = (np.sin(np.arange(audio.SR) * 2 * np.pi * 220 / audio.SR) * 0.5).astype(np.float32)
    out, info = audio.mix(6.0, [(2.0, tone)], [(0.5, "pop")], "playful", music_volume=0.3)
    assert out.size == 6 * audio.SR and np.max(np.abs(out)) <= 0.9
    assert info["music"].startswith("synth:")


def test_moving_average_matches_numpy():
    x = np.random.default_rng(0).random(5000)
    ma = audio.moving_average(x, 101)
    ref = np.convolve(x, np.ones(101) / 101, mode="same")
    assert np.allclose(ma[200:-200], ref[200:-200])


@pytest.mark.parametrize("aspect,size", [("9:16", (1080, 1920)), ("16:9", (1920, 1080))])
def test_storyboard_images(tmp_path, aspect, size):
    from ytauto import characters
    cast = [characters.lookup("biscuit"), characters.lookup("boss_hoot")]
    scene = {"n": 1, "setting": "office", "on_screen_text": "CODE RED",
             "dialogue": [{"character": "biscuit", "emotion": "shocked"}]}
    out = image_p.generate("storyboard", "prompt", tmp_path / "a.png", aspect, 7, {"scene": scene, "cast": cast})
    assert Image.open(out).size == size


def test_thumbnail_spec(tmp_path):
    bg = tmp_path / "bg.png"
    Image.new("RGB", (1920, 1080), (200, 120, 40)).save(bg)
    r = thumbnail.make(bg, "WAIT WHAT NOW EXTRA", tmp_path, title="Biscuit vs the Vacuum")
    im = Image.open(r["jpg"])
    assert im.size == (1280, 720) and r["size_kb"] < 2000
    assert r["text"] == "WAIT WHAT NOW" and r["warnings"]
    # centre must stay bright (vignette darkens edges only)
    px = np.asarray(im.convert("L"))
    assert px[200:300, 500:700].mean() > px[:40, :40].mean()


def test_end_to_end_render_both_aspects(free_providers):
    """Real pipeline: offline script -> storyboard -> silent voices -> FFmpeg 9:16 + 16:9 MP4s."""
    p = projects.create("e2e", "short")
    p["export_aspects"] = ["9:16", "16:9"]
    projects.save(p)
    res = pipeline.run(p["id"], pipeline.STAGES)
    assert res["ok"], res
    p = projects.load(p["id"])
    outs = p["render"]["outputs"]
    assert set(outs) == {"9:16", "16:9"}
    tl = p["render"]["timeline"]
    for asp, (w, h) in {"9:16": (720, 1280), "16:9": (1280, 720)}.items():
        f = projects.abspath(p["id"], outs[asp]["file"])
        W, H, dur, has_audio = probe(f)
        assert (W, H) == (w, h) and has_audio
        assert abs(dur - tl["duration"]) < 0.6
        srt = projects.abspath(p["id"], outs[asp]["srt"]).read_text(encoding="utf-8")
        assert "-->" in srt
    assert projects.abspath(p["id"], p["thumbnail"]["jpg"]).exists()
    assert p["seo"]["title"] and "#Shorts" in p["seo"]["hashtags"]
    assert projects.row(p["id"])["status"] == "ready_for_review"
    assert (projects.project_dir(p["id"]) / "script.md").exists()


def test_timeline_requires_voice():
    p = projects.create("novoice", "short")
    p["script"] = {"scenes": [{"n": 1, "dialogue": [{"character": "biscuit", "line": "hi"}], "sfx": []}]}
    with pytest.raises(editor.EditError, match="voice"):
        editor.build_timeline(p)
