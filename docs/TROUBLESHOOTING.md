# Troubleshooting

Start with the built-in check: dashboard **Overview → System check**, or `ytauto doctor`.
Every failure is also logged in **Production History → Event log** with the exact error.

| Problem | Fix |
|---|---|
| `setup.bat` says Python not found | Install Python 3.10+ from python.org with *Add python.exe to PATH*, or `winget install Python.Python.3.12`, then reopen setup.bat. If the Microsoft Store opens instead, disable *App execution aliases* for python in Windows Settings. |
| `pip install` fails | Check internet/proxy. Re-run `setup.bat`. Corporate proxies: `set HTTPS_PROXY=http://proxy:port` before running it. |
| Dashboard says "Dashboard not built" | The pre-built files in `ytauto/web/dist` are missing. Re-extract the ZIP, or build: `cd frontend && npm install && npm run build` (needs Node 18+). |
| Port 8000 already in use | Set `YTAUTO_PORT=8010` in `.env` and restart. |
| `start.bat` window closes immediately | Run `ytauto.bat doctor` in a Command Prompt from the install folder to see the error. |
| FFmpeg not found | setup installs `imageio-ffmpeg`, which bundles FFmpeg. Re-run setup, or install FFmpeg and add it to PATH, or set `FFMPEG_BINARY=C:\path\to\ffmpeg.exe` in `.env`. |
| No burned-in subtitles | `doctor` shows "FFmpeg libass" missing - use a full FFmpeg build via `FFMPEG_BINARY`. The `.srt` caption file is still produced. |
| Edge voices fail | Needs internet; the free endpoint can change. Update with `.venv\Scripts\python -m pip install -U edge-tts`, or switch voice provider to `sapi` (offline) or a paid one. |
| `sapi` voices fail on Linux | `sudo apt install espeak-ng`. |
| Run stops at "awaiting cost approval" | Paid providers are selected. Review the estimate and click *Approve*, or switch to free providers in API Settings. |
| "... needs XYZ_API_KEY" | Add the key in API Settings, or choose a free provider. No request was sent. |
| Claude error about credits | Add credits at console.anthropic.com. A Claude Pro chat plan does not include API credits. |
| Claude "model not found" | Set `ANTHROPIC_MODEL` to `claude-opus-5-5`, `claude-sonnet-5-5` or `claude-haiku-5-5`. |
| Pollinations returns errors / slow | It's a free shared service. Retry later, add a free token, or use storyboard. |
| AI video clip failed | The scene falls back to Ken Burns automatically; the event log shows the provider's message. |
| "YouTube is not connected" | Upload Manager → Connect YouTube. See YOUTUBE_OAUTH.md. |
| "OAuth client file not found" | Save the Desktop-app client JSON as `data\secrets\client_secret.json`. |
| `access_denied` / "app not verified" at sign-in | Add your Google account as a *test user* on the consent screen; click *Continue* on the unverified warning. |
| Sign-in worked last week, now fails | Testing-mode tokens can expire after 7 days. Click Connect again. |
| `quotaExceeded` | Daily API quota used up; try tomorrow or request more quota in Google Cloud. |
| Thumbnail "failed" after upload | Verify your channel by phone at youtube.com/verify; re-upload the thumbnail in Studio. |
| Uploaded video is locked private | Unaudited API projects can be restricted to private by YouTube. Publish from YouTube Studio, or request the API audit. |
| Render is slow | Use *draft* quality in Video Editor for previews, then HD for the final. |
| Job stuck after restarting the PC | Jobs that were running when the server stopped are marked failed on next start; run the stage again (completed stages are kept). |

## Reset

- Reset settings/history: stop the server and delete `data\ytauto.db` (projects folders stay).
- Remove all videos: delete folders inside `projects\`.
- Disconnect YouTube: Upload Manager → Disconnect (deletes `data\secrets\youtube_token.json`).

## Logs

- Server window output (Windows) or `data/server.log` (Linux/macOS).
- Per-project: Production History → Event log; `projects\<id>\project.json`.
