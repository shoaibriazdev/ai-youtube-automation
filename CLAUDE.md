# AI YouTube Automation Pro - notes for Claude Code

This folder is an original animated-comedy YouTube production platform plus the original YouTube skill pack.

- CLI: `ytauto.bat <cmd>` (Windows) / `./ytauto.sh <cmd>` (Linux/macOS), or `.venv\Scripts\python -m ytauto <cmd>`.
  Main commands: `today`, `ideas`, `new --idea N`, `script|characters|generate|voice|edit|thumbnail|seo <project>`,
  `run <project> [stages]`, `estimate`, `approve-cost`, `approve`, `youtube connect`, `upload`, `schedule`,
  `analytics`, `doctor`, `serve`.
- Skills: `skills/*/SKILL.md` (11 original + 9 production skills). Regenerate the production ones with
  `python scripts/make_skills.py`; install for the user with `python scripts/install_skills.py`.
- Code: `ytauto/` (pipeline.py orchestrates; providers/ for image/video/tts; editor.py = FFmpeg; youtube.py = upload).
- Dashboard source `frontend/` (React+Vite) builds into `ytauto/web/dist` (`npm run build`).
- Tests: `.venv\Scripts\python -m pytest` (uses a temp data dir; never calls paid APIs).

Rules that must hold in any change:
1. Never upload, approve, publish or schedule without the user's explicit yes. Uploads default to private.
2. Never spend money without approval: paid providers go through `pipeline.check_costs`.
3. Never put secrets in code or commands; they live in `.env` / `data/secrets/`.
4. Generated content must be original - no copying creators, characters, brands or real people.
5. Do not claim a feature works unless a command actually ran successfully.
