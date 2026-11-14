---
name: yt-upload
description: >-
  Upload an approved video project to YouTube with the official Data API v3 - private by default, custom thumbnail, title, description, tags, category, audience settings - and record the result. Use for "upload it", "post to YouTube", /yt-upload.
---

# yt-upload

STEP 9. One-time: the user creates a Desktop-app OAuth client and saves it as
`data/secrets/client_secret.json` (docs/YOUTUBE_OAUTH.md), then:

```bash
ytauto youtube connect              # Google sign-in in the browser; token saved in data/secrets/
ytauto approve <project>            # ONLY after the user says they watched it and approve
ytauto upload <project>             # private by default
ytauto upload <project> --privacy unlisted
```

Never run `ytauto approve` without an explicit yes from the user in this conversation. Never pass
`--yes-public`; if they want public, let the CLI ask them to type PUBLISH. Report the URL, privacy and
whether the custom thumbnail was accepted (custom thumbnails need a phone-verified channel).

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
