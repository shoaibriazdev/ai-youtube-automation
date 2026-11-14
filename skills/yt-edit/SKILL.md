---
name: yt-edit
description: >-
  Turn a raw recording's transcript into an edit decision list - dead air,
  filler cues and retakes, with timecodes. Use for "edit this", "cut the
  dead space", "tighten this video", "I rambled", or any request to shorten
  footage from a transcript.
---

# yt-edit

An edit decision list from a timestamped transcript. It prints the cuts. You apply them.

```bash
python3 deadair.py transcript.srt              # srt, vtt or whisper json
python3 deadair.py transcript.srt --floor 0.35 --json
```

No transcript yet? Ask for one, or produce one first - `whisper`, `faster-whisper`, or the caption
track YouTube generates on an unlisted upload all work. Do not guess at timings.

## What it finds

- **DEAD** - gaps longer than the floor, trimmed from the MIDDLE so both sides keep a breath.
  Cutting flush against speech is what makes a tightened take sound gasping.
- **FILLER** - cues that are nothing but "um", "so yeah", "basically".
- **REPEAT** - a sentence restarted. Compared against the last cue that was actually speech, not
  the literal previous cue, because most retakes have an "um" between the two attempts.

## What it will not do

It does not touch media. It has no opinion about your B-roll. A 40% cut on the report is a 40% cut
of SPEECH, and if the video has a long silent demo in it that number is wrong - check the report
against the footage before you trust the runtime at the bottom.

## Production mode: automatic video editing (AI YouTube Automation Pro)

The transcript EDL above is for footage you recorded. For AI-produced projects the platform edits the video
itself with FFmpeg: scene clips (AI clip or Ken Burns motion on stills), xfade transitions, voices on a
timeline, synthesized or your own SFX and music (ducked under dialogue), burned-in captions + .srt, and
export at 9:16 (1080x1920) and/or 16:9 (1920x1080):

```bash
ytauto edit <project>           # primary format
ytauto edit <project> --both    # 9:16 and 16:9
```

Report the output paths, durations and sizes, and ask the user to watch before anything is uploaded.

## Running the platform

The production platform lives at `<YTAUTO_HOME>` (written by `scripts/install_skills.py`; if you still see the
placeholder, use the folder that contains `ytauto/` and `setup.bat`). Run commands from that folder:

- Windows: `<YTAUTO_HOME>\ytauto.bat <command>`
- Linux/macOS: `<YTAUTO_HOME>/ytauto.sh <command>`

If `.venv` does not exist yet, tell the user to run `setup.bat` (Windows) or `./setup.sh` first. Never claim a
step worked unless the command printed success - read its output. Never put API keys in commands; keys live
in `.env` or the dashboard's API Settings page (http://localhost:8000/#api).

## The gate

Nothing here publishes. This skill writes and you publish. Every output ends in a block the user
copies, and the last line of every run is the question: **ship it, or change it?**
