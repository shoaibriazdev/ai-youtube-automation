---
name: yt-thumbnail
description: >-
  Generate an original 1280x720 YouTube thumbnail for a video project - bold 3-word text that does not repeat the title, colour grade, accent burst - and lint the title+thumbnail pairing. Use for "make a thumbnail", "thumbnail text", /yt-thumbnail.
---

# yt-thumbnail

STEP 7. Uses the dedicated thumbnail background from the image step (or the hook scene), then checks the
pairing with the original `skills/yt-package/title.py` (no shared words, max 3 words).

```bash
ytauto thumbnail <project> --text "WAIT WHAT" --style pop     # styles: pop | clean | shock
```

Show the output path and the lint result. Offer three alternative 3-word texts and say which to test first,
following the `/yt-package` rules.

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
