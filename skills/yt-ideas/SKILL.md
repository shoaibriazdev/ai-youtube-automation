---
name: yt-ideas
description: >-
  Research what is working in funny animated comedy on YouTube and generate 10 ORIGINAL, scored video ideas for the channel (audience appeal + production feasibility). Use for "video ideas", "what should I make", "find trending comedy topics", /yt-ideas.
---

# yt-ideas

STEP 1 of the production platform: optional live YouTube trend signals (free `YOUTUBE_API_KEY`), then
Claude (if `ANTHROPIC_API_KEY` is set) or the free offline writer produces original ideas that use the
channel's recurring characters. Each idea is scored for appeal and feasibility; hooks are scored with the
original `skills/yt-script/hookscore.py` and titles with `skills/yt-package/title.py`.

```bash
ytauto ideas -n 10 --format short      # --no-trends to skip YouTube, --hint "topic" to steer
ytauto ideas --list                    # previously generated ideas
ytauto new --idea <id>                 # make it a video project (--both = 9:16 and 16:9)
```

Present the top five with score, hook and cast. Trending titles are inspiration for THEMES only - never copy
a title, joke, character or plot from another creator. If Claude is configured, mention it costs a few cents.

## Running the platform

The production platform lives at `<YTAUTO_HOME>` (written by `scripts/install_skills.py`; if you still see the
placeholder, use the folder that contains `ytauto/` and `setup.bat`). Run commands from that folder:

- Windows: `<YTAUTO_HOME>\ytauto.bat <command>`
- Linux/macOS: `<YTAUTO_HOME>/ytauto.sh <command>`

If `.venv` does not exist yet, tell the user to run `setup.bat` (Windows) or `./setup.sh` first. Never claim a
step worked unless the command printed success - read its output. Never put API keys in commands; keys live
in `.env` or the dashboard's API Settings page (http://localhost:8000/#api).

## The gate

Nothing is published without the user. Uploads default to private; public or scheduled publishing needs the
user to type PUBLISH (CLI) or confirm in the dashboard. Paid providers pause for cost approval - run
`ytauto approve-cost <project>` only after the user says yes to the amount shown. End every run with the
question: **ship it, or change it?**
