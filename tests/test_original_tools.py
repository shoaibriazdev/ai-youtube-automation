"""The six original skill-pack tools must keep working unchanged (clean Python, no dependencies)."""
import json
import subprocess
import sys

from conftest import ROOT

SRT = """1
00:00:00,000 --> 00:00:04,000
Your first thirty seconds are why nobody finishes your videos.

2
00:00:04,500 --> 00:00:08,000
um

3
00:00:10,500 --> 00:00:14,000
Here is the thing about thumbnails and titles together.

4
00:00:14,200 --> 00:00:19,000
Here is the thing about thumbnails and titles together, again.

5
00:00:22,000 --> 00:00:30,000
Retention graphs show exactly where viewers leave the video.

6
00:00:33,000 --> 00:00:41,000
Chapters must start at zero and each one needs ten seconds.

7
00:00:44,000 --> 00:00:52,000
Comments are a retention surface, reply in the first hours.

8
00:00:55,000 --> 00:01:05,000
That is the whole system, the prompt is in the description.
"""


def run(script, *args):
    p = subprocess.run([sys.executable, str(ROOT / "skills" / script), *map(str, args)],
                       capture_output=True, text=True, timeout=60)
    return p


def test_hookscore():
    p = run("yt-script/hookscore.py", "--json", "--hook", "Your first 30 seconds are why nobody finishes your videos.")
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout)
    assert 0 <= data[0]["verdict"] <= 100 and data[0]["formula"]


def test_title_lint():
    p = run("yt-package/title.py", "--json", "--title", "I Tried 7 Days of AI Comedy", "--thumb", "IT WORKED")
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)[0]["score"] > 0


def test_deadair_and_chapters(tmp_path):
    f = tmp_path / "t.srt"
    f.write_text(SRT, encoding="utf-8")
    p = run("yt-edit/deadair.py", f, "--json")
    assert p.returncode == 0, p.stderr
    p = run("yt-chapters/chapters.py", f, "--json", "--target", "4")
    assert p.returncode == 0, p.stderr
    assert "chapters" in json.loads(p.stdout)


def test_retention(tmp_path):
    f = tmp_path / "r.csv"
    f.write_text("position,retention\n" + "\n".join(f"{i},{100 - i * 0.6 - (15 if i > 40 else 0)}" for i in range(0, 101, 2)))
    p = run("yt-retention/retention.py", f, "--json", "--duration", "300")
    assert p.returncode == 0, p.stderr


def test_swipe(tmp_path):
    vids = [{"channel": c, "title": f"{c} video {i}: 97% of people fail this", "views": v, "url": "u", "duration": 600}
            for c, base in (("A", 1000), ("B", 50000)) for i, v in enumerate([base, base * 1.1, base * 0.9, base * 6])]
    f = tmp_path / "s.json"
    f.write_text(json.dumps(vids))
    p = run("yt-viral/swipe.py", f, "--json", "--min", "2.0")
    assert p.returncode == 0, p.stderr
