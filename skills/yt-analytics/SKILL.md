---
name: yt-analytics
description: >-
  Show channel and per-video performance for videos uploaded by the platform (views, likes, comments, daily views, average view duration) via the YouTube Data and Analytics APIs. Use for "how are my videos doing", "analytics", "stats", /yt-analytics.
---

# yt-analytics

```bash
ytauto analytics --days 28
```

Needs `ytauto youtube connect` and the YouTube Analytics API enabled in the Google Cloud project. Summarise
the best and worst video by views, the trend over the period, and ONE thing to change next. For
second-by-second drop-off ask for the retention CSV and use `/yt-retention`. Never invent a number the
command did not print.

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
