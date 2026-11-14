# Installation

## Requirements

- Windows 10/11 (primary), or Linux / macOS
- Python 3.10 or newer (tested with 3.12)
- ~600 MB disk for packages (FFmpeg is bundled through `imageio-ffmpeg`)
- Internet for installing packages, Edge voices, Pollinations and paid APIs (the offline providers work without)
- Node.js is **not** required (dashboard is pre-built). Only needed to modify the dashboard.

## Windows

1. Extract the ZIP to e.g. `C:\AI-YouTube-Automation-Pro` (avoid OneDrive-synced folders for big renders).
2. Double-click `setup.bat`. It:
   - finds Python (`py -3` or `python`),
   - creates `.venv` and installs `requirements.txt`,
   - copies `.env.example` → `.env`,
   - creates `data\secrets` and `projects`,
   - runs `ytauto doctor`,
   - optionally installs the Claude Code skills into `%USERPROFILE%\.claude\skills`.
3. Double-click `start.bat` → browser opens http://localhost:8000. Keep the window open.
4. `stop.bat` (or close the window) stops it.
5. Command line: open Command Prompt in the folder and use `ytauto.bat <command>` (`ytauto.bat --help`).

## Linux / macOS

```bash
chmod +x *.sh
./setup.sh
./start.sh      # runs in background, log in data/server.log
./stop.sh
./ytauto.sh today
```

For offline system voices on Linux: `sudo apt install espeak-ng`.

## Configure

1. **API Settings**: choose free or paid providers, paste keys you have ([API_SETUP.md](API_SETUP.md)).
2. **Channel Settings**: channel name, audience, tone, made-for-kids (legal setting), default privacy.
3. **Character Library**: review the 5 original recurring characters; add your own.
4. **YouTube Upload Manager**: connect your channel ([YOUTUBE_OAUTH.md](YOUTUBE_OAUTH.md)).

## Verify

```bash
ytauto.bat doctor
.venv\Scripts\python -m pytest        # 43 tests, ~1 minute, renders real MP4s
```

## Updating

Extract the new version over the old folder (keep `.env`, `data\` and `projects\`), then run `setup.bat`
again.

## Claude Code

- Skills: `python scripts/install_skills.py` copies all 20 skills to `~/.claude/skills` with the install path
  filled in. Then `/yt-today`, `/yt-ideas`, … work in any Claude Code session.
- Or open this folder in Claude Code; `CLAUDE.md` explains the CLI.
- Or install as a plugin from the folder (`.claude-plugin/`).

## Developing the dashboard

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173, proxies /api to the running server on :8000
npm run build    # writes ../ytauto/web/dist
```
