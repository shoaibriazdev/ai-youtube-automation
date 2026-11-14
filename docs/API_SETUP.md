# API configuration guide

All keys are optional. Without any, the platform runs on free providers. Add a key in the dashboard
(**API Settings** → paste → *Save keys*) or edit `.env` in the install folder and restart. Keys are only
stored in your local `.env`; the dashboard shows the last 4 characters.

After adding a key, select that provider (API Settings → *Providers*). Then the next run shows a cost
estimate and waits for your approval.

| Service | Env var | Used for | Free? | Where to get it |
|---|---|---|---|---|
| Anthropic Claude | `ANTHROPIC_API_KEY` | ideas, scripts, SEO (much better than the offline writer) | **Paid** API credits | https://console.anthropic.com/settings/keys |
| ElevenLabs | `ELEVENLABS_API_KEY` | best character voices | small free tier, then paid plan | https://elevenlabs.io/app/settings/api-keys |
| OpenAI | `OPENAI_API_KEY` | images (gpt-image-1) and/or voices (gpt-4o-mini-tts) | Paid | https://platform.openai.com/api-keys |
| Stability AI | `STABILITY_API_KEY` | images (Stable Image Core) | Paid credits | https://platform.stability.ai/account/keys |
| Replicate | `REPLICATE_API_TOKEN` | images (FLUX schnell) and video models | Paid per run | https://replicate.com/account/api-tokens |
| Runway | `RUNWAY_API_KEY` | image-to-video clips (gen4_turbo) | Paid credits | https://dev.runwayml.com/ |
| Luma | `LUMA_API_KEY` | text-to-video clips (ray-2) | Paid credits | https://lumalabs.ai/dream-machine/api/keys |
| Pollinations | `POLLINATIONS_TOKEN` | optional, removes watermark / raises limits | Free | https://auth.pollinations.ai/ |
| YouTube Data API | `YOUTUBE_API_KEY` | trend research | Free (quota) | Google Cloud → Credentials → *API key* (enable YouTube Data API v3) |
| Google OAuth client | `GOOGLE_CLIENT_SECRETS_FILE` | upload / schedule / analytics | Free | see [YOUTUBE_OAUTH.md](YOUTUBE_OAUTH.md) |

## Claude

- **A Claude Pro or Max subscription (claude.ai) does not include API credits.** Create an API key in the
  Anthropic Console and add credits there.
- Model (`ANTHROPIC_MODEL`): `claude-opus-5-5` (default, best writing, $4 / $20 per million input/output
  tokens), `claude-sonnet-5-5` ($2 / $10), `claude-haiku-5-5` ($0.10 / $0.50). One video uses roughly
  15–25k tokens across research, script and SEO.
- Provider setting `auto` uses Claude when a key is present, otherwise the offline writer. `anthropic`
  forces Claude (and errors clearly if the key is missing). `offline` never calls Claude.
- Structured JSON output is used, so scripts always have the expected shape.

## ElevenLabs voices

1. Add the key, choose **elevenlabs** as the voice provider.
2. **Character Library → Edit** each character → pick an *ElevenLabs voice* (the list comes from your
   ElevenLabs account; add voices from their Voice Library first).
3. Use **▶ Voice** to test. Model: `eleven_multilingual_v2` (change in `provider_options`).

## Image providers

- `storyboard` – offline cartoon frames. Useful for previews and testing; not final quality.
- `pollinations` – free AI images, no key; quality varies, rate-limited, small watermark without a token.
- `openai` – `gpt-image-1`, quality `medium` by default (≈$0.04–0.07/image).
- `stability` – Stable Image Core (≈$0.03/image), supports seeds for consistency.
- `replicate` – default `black-forest-labs/flux-schnell` (≈$0.003/image), seeds supported.

Character consistency: each prompt includes the character's exact *visual DNA* sentence and a fixed seed.
Seed-based providers (Stability, Replicate, Pollinations) stay the most consistent.

## Video providers

- `kenburns` – free; animates stills (zoom/pan) during editing.
- `runway` – sends each scene image to `image_to_video` (gen4_turbo, 5 or 10 s, 1280:720 or 720:1280).
- `luma` – text-to-video from the scene prompt (ray-2, 720p).
- `replicate` – any model; set `replicate_video_model` and the image input field name
  (`first_frame_image` for `minimax/video-01`) in Video Generation.

`max_ai_video_scenes` limits how many scenes get AI clips (cost control). If a clip fails, that scene falls
back to Ken Burns and the log says so.

## What was tested without credentials

Paid providers were implemented against their public API documentation but **could not be tested here
without keys**. The free providers (offline writer, storyboard, Pollinations, Ken Burns, Edge, system voices),
the cost gate and every "missing key" path were tested. If a paid provider returns an error, the exact
message from the provider is shown in the dashboard and in Production History.
