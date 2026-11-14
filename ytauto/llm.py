"""LLM layer: Anthropic Claude (official SDK, structured JSON output) or the free offline writer.

provider setting "llm": auto (Claude if ANTHROPIC_API_KEY is set, else offline) | anthropic | offline
"""
from __future__ import annotations

import json
import random
import time

from . import config, db


class LLMError(RuntimeError):
    pass


def active_provider() -> str:
    choice = db.get_setting("providers").get("llm", "auto")
    if choice == "offline":
        return "offline"
    if choice == "anthropic" and not config.has_secret("ANTHROPIC_API_KEY"):
        raise LLMError("LLM provider is set to 'anthropic' but ANTHROPIC_API_KEY is not configured. "
                       "Add it in API Settings (or .env), or switch the LLM provider to 'offline'.")
    return "anthropic" if config.has_secret("ANTHROPIC_API_KEY") else "offline"


def active_model() -> str:
    try:
        return config.env("ANTHROPIC_MODEL") if active_provider() == "anthropic" else "offline"
    except LLMError:
        return config.env("ANTHROPIC_MODEL")


SYSTEM = (
    "You are the head writer of an ORIGINAL family-friendly animated comedy YouTube channel for a US and "
    "English-speaking audience. You write fast, clean, genuinely funny material with a strong hook in the "
    "first 3 seconds and an unexpected twist ending. Rules: everything must be original - never copy or "
    "imitate other creators' videos, scripts, characters, catchphrases or any copyrighted material or brand; "
    "no real celebrities; no misleading claims; keep it safe for all ages. Never invent statistics."
)


def generate_json(prompt: str, schema: dict, project_id: str | None = None, stage: str = "llm",
                  max_tokens: int = 16000) -> dict:
    """Call Claude with a JSON schema and return the parsed object. Retries transient errors."""
    import anthropic

    model = config.env("ANTHROPIC_MODEL")
    client = anthropic.Anthropic(api_key=config.env("ANTHROPIC_API_KEY"), max_retries=3, timeout=600)
    kwargs = dict(model=model, max_tokens=max_tokens, system=SYSTEM,
                  messages=[{"role": "user", "content": prompt}],
                  output_config={"format": {"type": "json_schema", "schema": schema}})
    last = None
    for attempt in range(3):
        try:
            if model in ("claude-opus-5-5", "claude-fable-5-1", "claude-sonnet-5-5"):
                # Server-side fallback if a request is declined by a safety classifier.
                resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"],
                                                   fallbacks="default", **kwargs)
            else:
                resp = client.messages.create(**kwargs)
            break
        except anthropic.AuthenticationError as e:
            raise LLMError("Anthropic rejected the API key (401). Check ANTHROPIC_API_KEY.") from e
        except anthropic.PermissionDeniedError as e:
            raise LLMError(f"Anthropic permission error: {e.message}") from e
        except anthropic.NotFoundError as e:
            raise LLMError(f"Model '{model}' not found. Set ANTHROPIC_MODEL in .env.") from e
        except anthropic.BadRequestError as e:
            msg = str(e.message)
            if "credit" in msg.lower() or "billing" in msg.lower():
                raise LLMError("Anthropic says the account has no API credits. Add credits at "
                               "console.anthropic.com (a Claude Pro chat plan does not include API credits).") from e
            raise LLMError(f"Anthropic request error: {msg}") from e
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.InternalServerError) as e:
            last = e
            time.sleep(2 ** attempt * 3)
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                last = e
                time.sleep(2 ** attempt * 3)
            else:
                raise LLMError(f"Anthropic API error {e.status_code}: {e.message}") from e
    else:
        raise LLMError(f"Anthropic API unavailable after retries: {last}")

    if resp.stop_reason == "refusal":
        raise LLMError("Claude declined this request. Rephrase the topic and try again.")
    if resp.stop_reason == "max_tokens":
        raise LLMError("Claude's answer was cut off (max_tokens). Try a shorter format.")
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    usage = getattr(resp, "usage", None)
    if usage is not None:
        from .costs import pricing
        pin, pout = pricing()["llm"].get(model, (4.0, 20.0))
        usd = (usage.input_tokens * pin + usage.output_tokens * pout) / 1e6
        db.log_cost(project_id, "anthropic", stage, usage.input_tokens + usage.output_tokens, usd, model)
    try:
        return json.loads(text)
    except ValueError as e:
        raise LLMError(f"Claude returned invalid JSON: {text[:300]}") from e


def rng(seed: str | int | None = None) -> random.Random:
    return random.Random(seed if seed is not None else time.time_ns())
