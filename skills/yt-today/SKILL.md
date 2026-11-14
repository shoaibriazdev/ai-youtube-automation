---
name: yt-today
description: >-
  CREATE TODAY'S VIDEO end to end: pick a topic, write the script, create scenes, generate visuals and voices, edit the MP4, make the thumbnail and SEO, then stop for the user's review and approval before any upload. Use for "create today's video", "make a video for today", "run the whole pipeline", /yt-today.
---

# yt-today

The full pipeline in one command:

```bash
ytauto today --format short            # or --format long; --hint "optional topic"
```

1 topic (best unused idea or fresh research) -> 2 script -> 3 scenes -> 4 visuals -> 5 voiceovers ->
6 FFmpeg edit (music, SFX, subtitles, transitions) -> 7 thumbnail -> 8 SEO -> 9 **stops** and prints the file
paths for the user to watch. Then, only after the user has watched it and says yes:

```bash
ytauto approve <project>
ytauto upload <project>                # private
```

With the default free providers it costs nothing and takes 1-3 minutes. With paid providers it pauses and
prints the estimate; ask the user before `ytauto approve-cost <project>` and `ytauto run <project>`.
Report the project id, title, video path(s), thumbnail path and the hook score.

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
