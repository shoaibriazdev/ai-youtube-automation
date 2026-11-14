"""Configuration: paths, environment variables (.env) and provider settings.

Secrets (API keys, OAuth client files, tokens) are NEVER stored in source code. They come from
environment variables / the local `.env` file, and OAuth tokens live in `data/secrets/`, which is
git-ignored. Non-secret preferences (which provider to use, channel settings) live in SQLite.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(os.environ.get("YTAUTO_HOME") or Path(__file__).resolve().parent.parent)
ENV_FILE = Path(os.environ.get("YTAUTO_ENV_FILE") or ROOT / ".env")  # cloud: put it on the persistent volume
load_dotenv(ENV_FILE, override=False)

DATA_DIR = Path(os.environ.get("YTAUTO_DATA_DIR") or ROOT / "data")
SECRETS_DIR = DATA_DIR / "secrets"
PROJECTS_DIR = Path(os.environ.get("YTAUTO_PROJECTS_DIR") or ROOT / "projects")
ASSETS_DIR = ROOT / "assets"
CACHE_DIR = DATA_DIR / "cache"
SKILLS_DIR = ROOT / "skills"
WEB_DIST = ROOT / "ytauto" / "web" / "dist"
DB_PATH = DATA_DIR / "ytauto.db"

for _d in (DATA_DIR, SECRETS_DIR, PROJECTS_DIR, CACHE_DIR, ASSETS_DIR / "music", ASSETS_DIR / "sfx"):
    _d.mkdir(parents=True, exist_ok=True)

# Every secret the platform knows about: env var -> (label, what it unlocks, paid?)
SECRET_KEYS: dict[str, dict] = {
    "ANTHROPIC_API_KEY": {"label": "Anthropic Claude API key", "group": "LLM",
                          "paid": True, "url": "https://console.anthropic.com/settings/keys",
                          "note": "Pay-as-you-go API credits. A Claude Pro/Max chat subscription does NOT include API credits."},
    "ELEVENLABS_API_KEY": {"label": "ElevenLabs API key", "group": "Voice", "paid": True,
                           "url": "https://elevenlabs.io/app/settings/api-keys",
                           "note": "Free tier has a small monthly character allowance; more needs a subscription."},
    "OPENAI_API_KEY": {"label": "OpenAI API key (images / TTS)", "group": "Images / Voice", "paid": True,
                       "url": "https://platform.openai.com/api-keys", "note": "Pay-as-you-go."},
    "STABILITY_API_KEY": {"label": "Stability AI API key", "group": "Images", "paid": True,
                          "url": "https://platform.stability.ai/account/keys", "note": "Credits-based."},
    "REPLICATE_API_TOKEN": {"label": "Replicate API token", "group": "Images / Video", "paid": True,
                            "url": "https://replicate.com/account/api-tokens", "note": "Pay per prediction."},
    "RUNWAY_API_KEY": {"label": "Runway API key", "group": "Video", "paid": True,
                       "url": "https://dev.runwayml.com/", "note": "Credits-based (pre-paid)."},
    "LUMA_API_KEY": {"label": "Luma Dream Machine API key", "group": "Video", "paid": True,
                     "url": "https://lumalabs.ai/dream-machine/api/keys", "note": "Credits-based."},
    "POLLINATIONS_TOKEN": {"label": "Pollinations token (optional)", "group": "Images", "paid": False,
                           "url": "https://auth.pollinations.ai/", "note": "Optional; raises free rate limits."},
    "YOUTUBE_API_KEY": {"label": "YouTube Data API key (research)", "group": "YouTube", "paid": False,
                        "url": "https://console.cloud.google.com/apis/credentials",
                        "note": "Free, quota-limited (10,000 units/day by default). Used for trend research."},
}

NON_SECRET_ENV = {
    "ANTHROPIC_MODEL": "claude-opus-5-5",
    "GOOGLE_CLIENT_SECRETS_FILE": str(SECRETS_DIR / "client_secret.json"),
    "YTAUTO_HOST": "127.0.0.1",
    "YTAUTO_PORT": "8000",
    "MONTHLY_BUDGET_USD": "10",
    "FFMPEG_BINARY": "",
}


def env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    if val is None or val.strip() == "":
        return default if default is not None else NON_SECRET_ENV.get(name)
    return val.strip()


def has_secret(name: str) -> bool:
    return bool(env(name))


def mask(value: str | None) -> str:
    if not value:
        return ""
    return ("*" * 6) + value[-4:] if len(value) > 8 else "*" * len(value)


def secrets_status() -> list[dict]:
    out = []
    for key, meta in SECRET_KEYS.items():
        out.append({"key": key, **meta, "configured": has_secret(key), "masked": mask(env(key))})
    return out


_ENV_LINE = re.compile(r"^\s*([A-Z0-9_]+)\s*=")


def write_env_values(values: dict[str, str]) -> list[str]:
    """Write keys into the local .env file (creating it from .env.example if needed).

    Only known keys are accepted. Values are written to the user's own machine and are also put
    in os.environ for the running process. Returns the list of keys written.
    """
    allowed = set(SECRET_KEYS) | set(NON_SECRET_ENV)
    values = {k: v.strip() for k, v in values.items() if k in allowed and v is not None}
    for k, v in values.items():
        if "\n" in v or "\r" in v:
            raise ValueError(f"{k}: value must be a single line")
    if not ENV_FILE.exists():
        example = ROOT / ".env.example"
        ENV_FILE.write_text(example.read_text(encoding="utf-8") if example.exists() else "", encoding="utf-8")
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    seen = set()
    for i, line in enumerate(lines):
        m = _ENV_LINE.match(line)
        if m and m.group(1) in values:
            lines[i] = f"{m.group(1)}={values[m.group(1)]}"
            seen.add(m.group(1))
    for k, v in values.items():
        if k not in seen:
            lines.append(f"{k}={v}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for k, v in values.items():
        if v:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)
    return sorted(values)
