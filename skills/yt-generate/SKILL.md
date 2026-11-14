---
name: yt-generate
description: >-
  Generate the scene images (and optional AI video clips) for a video project from its script, with consistent characters. Use for "generate the visuals", "make the scenes", "create images for my video", /yt-generate.
---

# yt-generate

STEP 4. Image providers: `storyboard` (free, offline cartoon frames), `pollinations` (free community AI,
rate-limited), `openai` / `stability` / `replicate` (paid, need keys). Video providers: `kenburns` (free -
stills animated with pan/zoom), `runway` / `luma` / `replicate` (paid). Choose them in the dashboard.

```bash
ytauto estimate <project>            # cost first
ytauto generate <project>            # characters + images + clips with the selected providers
ytauto generate <project> --force    # regenerate everything
```

If the run pauses for cost approval, show the estimate and ask the user before `ytauto approve-cost`.
A missing key gives a clear error and no request is sent - report that honestly, do not retry in a loop.

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
