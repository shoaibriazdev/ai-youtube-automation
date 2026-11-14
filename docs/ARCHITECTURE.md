# Architecture

```
React dashboard (frontend/ → ytauto/web/dist)          Claude Code skills (skills/*/SKILL.md)
              │  fetch /api/...                                     │  run
              ▼                                                     ▼
     FastAPI server (ytauto/server.py) ──── jobs.py ──────►  CLI (ytauto/cli.py)
              │                    (1 worker thread,                 │
              │                     progress in SQLite)              │
              ▼                                                     ▼
                         pipeline.py  (stages, cost gate, resumable)
   research → script → characters → images → video → voice → edit → thumbnail → seo → review
      │          │          │           │        │       │       │        │        │
 research.py scriptgen.py characters.py providers/ providers/ editor.py thumbnail.py seo.py
      │          │                   image.py video.py tts.py  audio.py     │
      └── llm.py (Claude SDK, JSON schema) / offline_writer.py            legacy.py ──► original tools
                                                                          (hookscore, title, swipe)
                         youtube.py (OAuth, upload, thumbnail, schedule, analytics)
storage: data/ytauto.db (settings, characters, projects index, jobs, events, uploads, cost_log, ideas)
         projects/<id>/project.json + assets      secrets: .env, data/secrets/
```

## Key decisions

- **Every stage is resumable.** Results are written to `project.json` after each step; re-running skips
  completed work unless forced. Failures are logged with the stage and message; nothing is lost.
- **Cost gate before work.** `pipeline.check_costs` runs before any stage and again after the script, so
  no paid call happens without approval.
- **Approval gate before upload.** `projects.approved` must be set by the user; public/scheduled needs an
  extra `confirm_public` flag that only the UI confirmation / CLI prompt sends.
- **Audio is mixed in numpy**, not an FFmpeg filter graph: voices at exact timeline offsets, SFX at cue
  points, music ducked under speech with an O(n) moving-average envelope, then normalised. Simpler to test,
  identical on every platform.
- **Video in FFmpeg**: per-scene clips (zoompan Ken Burns or AI clip cover-cropped), joined with `xfade`
  (offsets computed so audio and video stay in sync), captions burned with libass (`ass` filter, run with a
  relative path to avoid Windows path escaping), H.264/AAC, `+faststart`.
- **Captions** are chunked to a few words, coloured per character, placed above the characters on 9:16 and
  low on 16:9; an `.srt` sidecar is also written.
- **FFmpeg comes from `imageio-ffmpeg`** unless `FFMPEG_BINARY` or a PATH ffmpeg exists — no manual install.
- **Character consistency** = exact visual DNA text in every prompt + fixed seed + reference sheet.
- **Original content**: the system prompt and every generation prompt require originality; trend research
  only passes public titles as theme inspiration and tells the model not to copy them.

## Data model (project.json)

```
id, title, format (short|long), idea{}, script{title, hook, hook_options, hook_scores, scenes[{n, setting,
visual, camera, action, on_screen_text, dialogue[{character, line, emotion, delivery}], sfx[{name, cue}]}]},
assets{images{n: path}, images_alt{aspect:{n: path}}, prompts{}, clips{}, voice{"n-i": {file, duration}}},
render{outputs{aspect: {file, srt, width, height, duration}}, timeline{}}, thumbnail{}, seo{}, youtube{},
stages{stage: {done, seconds}}, estimate{}
```
