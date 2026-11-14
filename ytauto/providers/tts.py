"""STEP 5 - Text-to-speech providers, one voice per character.

edge        free (unofficial Microsoft Edge online voices, needs internet)  package: edge-tts
elevenlabs  paid / limited free tier                                         ELEVENLABS_API_KEY
openai      paid                                                             OPENAI_API_KEY
sapi        free, offline system voices (Windows SAPI5 / espeak)             package: pyttsx3
silent      free, writes silence of the estimated length (pipeline testing only)

Every provider writes the file it gets; the caller converts it to 16-bit mono WAV.
"""
from __future__ import annotations

import asyncio
import threading
from pathlib import Path

from .. import db
from .base import ProviderError, request, require

PROVIDERS = ["edge", "elevenlabs", "openai", "sapi", "silent"]
EMOTION_RATE = {"panicked": "+12%", "excited": "+12%", "shocked": "+6%", "tired": "-8%", "deadpan": "-5%",
                "suspicious": "-6%", "sad": "-8%"}


def voice_for(character: dict, provider: str) -> dict:
    v = (character.get("voice") or {}).get(provider) or {}
    defaults = {"edge": {"voice": "en-US-AndrewNeural"}, "openai": {"voice": "alloy"},
                "elevenlabs": {"voice_id": ""}, "sapi": {}}
    return {**defaults.get(provider, {}), **v}


def synthesize(provider: str, text: str, character: dict, out_base: Path, emotion: str = "",
               delivery: str = "") -> Path:
    """Write speech for `text`. Returns the produced file (extension depends on provider)."""
    out_base = Path(out_base)
    out_base.parent.mkdir(parents=True, exist_ok=True)
    v = voice_for(character, provider)
    if provider == "edge":
        return _edge(text, v, out_base.with_suffix(".mp3"), emotion)
    if provider == "elevenlabs":
        return _elevenlabs(text, v, out_base.with_suffix(".mp3"), emotion)
    if provider == "openai":
        return _openai(text, v, out_base.with_suffix(".mp3"), emotion, delivery)
    if provider == "sapi":
        return _sapi(text, v, out_base.with_suffix(".wav"))
    if provider == "silent":
        from ..audio import silence, write_wav
        return write_wav(out_base.with_suffix(".wav"), silence(max(0.8, len(text.split()) / 2.6)))
    raise ProviderError(f"unknown TTS provider '{provider}'. Choose one of {PROVIDERS}")


def _edge(text, v, out, emotion):
    try:
        import edge_tts
    except ImportError as e:
        raise ProviderError("edge-tts is not installed. Run setup.bat again.") from e
    rate = v.get("rate", "+0%")
    if emotion in EMOTION_RATE and rate in ("+0%", None):
        rate = EMOTION_RATE[emotion]

    async def go():
        comm = edge_tts.Communicate(text, v.get("voice", "en-US-AndrewNeural"), rate=rate,
                                    pitch=v.get("pitch", "+0Hz"), volume=v.get("volume", "+0%"))
        await comm.save(str(out))

    err: list[Exception] = []

    def runner():  # run in a fresh event loop (safe inside FastAPI / threads)
        try:
            asyncio.run(go())
        except Exception as e:  # noqa: BLE001
            err.append(e)

    for attempt in range(3):
        err.clear()
        t = threading.Thread(target=runner)
        t.start()
        t.join(120)
        if not err and out.exists() and out.stat().st_size > 500:
            return out
    raise ProviderError(f"Edge TTS failed (needs internet; the free service can change without notice): "
                        f"{err[0] if err else 'no audio returned'}. Switch TTS to 'sapi' for offline voices.")


def _elevenlabs(text, v, out, emotion):
    key = require("ELEVENLABS_API_KEY", "ElevenLabs")
    vid = v.get("voice_id")
    if not vid:
        raise ProviderError("This character has no ElevenLabs voice_id. Pick one in Voiceover Studio "
                            "(the list comes from your ElevenLabs account).")
    model = db.get_setting("provider_options").get("elevenlabs_model", "eleven_multilingual_v2")
    style = 0.6 if emotion in ("panicked", "excited", "shocked", "angry") else 0.3
    r = request("POST", f"https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128",
                headers={"xi-api-key": key, "Accept": "audio/mpeg"}, timeout=180,
                json={"text": text, "model_id": model,
                      "voice_settings": {"stability": v.get("stability", 0.4), "similarity_boost": 0.8,
                                         "style": style, "use_speaker_boost": True}})
    out.write_bytes(r.content)
    return out


def elevenlabs_voices() -> list[dict]:
    key = require("ELEVENLABS_API_KEY", "ElevenLabs")
    r = request("GET", "https://api.elevenlabs.io/v1/voices", headers={"xi-api-key": key}, timeout=60)
    return [{"voice_id": v["voice_id"], "name": v["name"], "labels": v.get("labels", {})} for v in r.json().get("voices", [])]


def _openai(text, v, out, emotion, delivery):
    key = require("OPENAI_API_KEY", "OpenAI TTS")
    model = db.get_setting("provider_options").get("openai_tts_model", "gpt-4o-mini-tts")
    instr = " ".join(x for x in [v.get("instructions", ""), f"Emotion: {emotion}." if emotion else "", delivery] if x)
    body = {"model": model, "voice": v.get("voice", "alloy"), "input": text, "response_format": "mp3"}
    if instr and "tts-1" not in model:
        body["instructions"] = instr
    r = request("POST", "https://api.openai.com/v1/audio/speech", headers={"Authorization": f"Bearer {key}"},
                json=body, timeout=180)
    out.write_bytes(r.content)
    return out


_SAPI_LOCK = threading.Lock()


def _sapi(text, v, out):
    try:
        import pyttsx3
    except ImportError as e:
        raise ProviderError("pyttsx3 is not installed. Run setup.bat again.") from e
    with _SAPI_LOCK:
        eng = pyttsx3.init()
        if v.get("rate"):
            eng.setProperty("rate", int(v["rate"]))
        voices = eng.getProperty("voices") or []
        want = (v.get("voice") or "").lower()
        if want:
            for vo in voices:
                if want in (vo.name or "").lower() or want in (vo.id or "").lower():
                    eng.setProperty("voice", vo.id)
                    break
        eng.save_to_file(text, str(out))
        eng.runAndWait()
        eng.stop()
    if not out.exists() or out.stat().st_size < 100:
        raise ProviderError("System TTS produced no audio. On Linux install espeak-ng; on Windows check speech settings.")
    return out


def sapi_voices() -> list[str]:
    try:
        import pyttsx3
        with _SAPI_LOCK:
            eng = pyttsx3.init()
            names = [v.name for v in eng.getProperty("voices") or []]
            eng.stop()
        return names
    except Exception:  # noqa: BLE001
        return []


EDGE_VOICES = ["en-US-AndrewNeural", "en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-EricNeural",
               "en-US-RogerNeural", "en-US-SteffanNeural", "en-US-BrianNeural", "en-US-JennyNeural",
               "en-US-AriaNeural", "en-US-AnaNeural", "en-US-EmmaNeural", "en-US-MichelleNeural",
               "en-GB-RyanNeural", "en-GB-SoniaNeural", "en-GB-ThomasNeural", "en-AU-WilliamNeural",
               "en-AU-NatashaNeural", "en-CA-LiamNeural", "en-IE-ConnorNeural"]
