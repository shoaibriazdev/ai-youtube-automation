---
name: yt-voice
description: >-
  Create character voiceovers for a video project - one consistent voice per character, emotion-aware delivery - with ElevenLabs, OpenAI TTS, free Edge voices or offline system voices. Use for "voice it", "generate voiceover", "TTS", /yt-voice.
---

# yt-voice

STEP 5. Providers: `edge` (free, needs internet), `sapi` (free, offline, robotic), `elevenlabs` (paid / small
free tier - set each character's voice_id in the Character Library), `openai` (paid). Switching provider
regenerates all lines; each line is trimmed of silence and timed for the editor.

```bash
ytauto voice <project>            # all dialogue lines
ytauto voice <project> --force    # regenerate
```

Report the number of lines. If a line fails (network, quota, missing voice_id) say which and why.

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
