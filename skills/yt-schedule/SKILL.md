---
name: yt-schedule
description: >-
  Schedule an approved video to go public at a chosen time (uploads private with publishAt), or change the publish time of an uploaded private video. Use for "schedule this", "publish Friday 5pm", "content calendar", /yt-schedule.
---

# yt-schedule

Pair with `/yt-plan` for what to post when. Times need a timezone offset:

```bash
ytauto upload <project> --publish-at 2026-11-20T17:00:00-05:00   # not uploaded yet: private + scheduled
ytauto schedule <project> 2026-11-20T17:00:00-05:00              # already uploaded: sets publishAt
```

Both ask the user to type PUBLISH because the video becomes public at that time. Ask the user for the time
and timezone (channel default is in Channel Settings) - do not assume. The dashboard's Publishing Schedule
page lists everything scheduled.

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
