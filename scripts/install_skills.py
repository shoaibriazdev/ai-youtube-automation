"""Copy every skill in skills/ to ~/.claude/skills/ so /yt-* commands work in any Claude Code session.

The <YTAUTO_HOME> placeholder in the production skills is replaced with this folder's absolute path,
and templates/voice.md is copied to ~/.claude/youtube/voice.md if you do not have one yet.

    python scripts/install_skills.py            # install / update
    python scripts/install_skills.py --dest DIR # somewhere else (e.g. a project's .claude/skills)
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", default=str(Path.home() / ".claude" / "skills"))
    a = ap.parse_args()
    dest = Path(a.dest)
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for src in sorted((ROOT / "skills").iterdir()):
        if not (src / "SKILL.md").exists():
            continue
        out = dest / src.name
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(src, out, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        f = out / "SKILL.md"
        f.write_text(f.read_text(encoding="utf-8").replace("<YTAUTO_HOME>", str(ROOT)), encoding="utf-8")
        n += 1
    voice = Path.home() / ".claude" / "youtube" / "voice.md"
    if not voice.exists():
        voice.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(ROOT / "templates" / "voice.md", voice)
        print(f"Copied the voice template to {voice} - fill it in.")
    print(f"Installed {n} skills into {dest}. Restart Claude Code, then try /yt-today or /yt-ideas.")


if __name__ == "__main__":
    main()
