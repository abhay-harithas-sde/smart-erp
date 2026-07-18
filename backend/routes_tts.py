"""ElevenLabs text-to-speech for AI insights read-aloud.

Free-tier note: ElevenLabs free accounts cannot use pre-made library voices via API
(returns 402). Two options:
  1. Set ELEVENLABS_VOICE_ID to a voice you cloned/created in ElevenLabs Voice Lab.
  2. Leave ELEVENLABS_VOICE_ID unset — the endpoint returns a 402 with a clear message,
     and the frontend falls back to the browser's built-in Web Speech API.
"""
import os
import asyncio
import functools
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from elevenlabs import ElevenLabs
from auth import get_current, AuthContext

router = APIRouter(prefix="/tts", tags=["tts"])

# Rachel (21m00Tcm4TlvDq8ikWAM) is a library voice — blocked on free tier.
# Users should set ELEVENLABS_VOICE_ID to their own cloned voice.
_voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "")
_model_id = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# Known library/pre-made voice IDs that are blocked on free tier
_FREE_TIER_BLOCKED_VOICES = {
    "21m00Tcm4TlvDq8ikWAM",  # Rachel
    "AZnzlk1XvdvUeBnXmlld",  # Domi
    "EXAVITQu4vr4xnSDxMaL",  # Bella
    "ErXwobaYiN019PkySvjV",  # Antoni
    "MF3mGyEYCl7XYWbV9V6O",  # Elli
    "TxGEqnHWrfWFTfGW9XjX",  # Josh
    "VR6AewLTigWG4xSOukaG",  # Arnold
    "pNInz6obpgDQGcFmaJgB",  # Adam
    "yoZ06aMxZJJ28mfd3POQ",  # Sam
}


@functools.lru_cache(maxsize=1)
def _get_tts_client():
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        raise HTTPException(500, "ELEVENLABS_API_KEY not configured")
    return ElevenLabs(api_key=api_key)


class TTSIn(BaseModel):
    text: str
    voice_id: str | None = None


@router.post("/speak")
async def speak(inp: TTSIn, ctx: AuthContext = Depends(get_current)):
    if not inp.text or len(inp.text) > 5000:
        raise HTTPException(400, "Text must be 1-5000 chars")

    voice = inp.voice_id or _voice_id

    # Warn early if the configured voice is a known blocked library voice
    if not voice or voice in _FREE_TIER_BLOCKED_VOICES:
        raise HTTPException(
            402,
            detail={
                "error": "elevenlabs_free_tier",
                "message": (
                    "ElevenLabs free tier does not allow pre-made library voices via API. "
                    "Clone your own voice in ElevenLabs Voice Lab and set ELEVENLABS_VOICE_ID "
                    "in your .env, or upgrade to the Starter plan. "
                    "The browser's built-in speech synthesis will be used as a fallback."
                ),
                "use_browser_tts": True,
            },
        )

    try:
        client = _get_tts_client()
        audio_stream = client.text_to_speech.convert(
            voice_id=voice,
            model_id=_model_id,
            text=inp.text,
            output_format="mp3_44100_128",
        )

        def _collect_audio():
            buf = BytesIO()
            for chunk in audio_stream:
                if chunk:
                    buf.write(chunk)
            return buf.getvalue()

        audio_bytes = await asyncio.to_thread(_collect_audio)
        buf = BytesIO(audio_bytes)
        buf.seek(0)
    except HTTPException:
        raise
    except Exception as e:
        msg = str(e)
        if "paid_plan_required" in msg or "voice_not_found" in msg or "401" in msg or "402" in msg:
            raise HTTPException(
                402,
                detail={
                    "error": "elevenlabs_free_tier",
                    "message": (
                        "ElevenLabs free tier does not allow this voice via API. "
                        "Clone your own voice in ElevenLabs Voice Lab and set ELEVENLABS_VOICE_ID, "
                        "or upgrade to the Starter plan."
                    ),
                    "use_browser_tts": True,
                },
            )
        raise HTTPException(500, f"TTS failed: {msg[:200]}")

    return StreamingResponse(
        buf,
        media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/voices")
async def list_voices(ctx: AuthContext = Depends(get_current)):
    try:
        client = _get_tts_client()
        result = client.voices.get_all()
        voices = [
            {
                "voice_id": v.voice_id,
                "name": v.name,
                "category": getattr(v, "category", None),
                "free_tier_blocked": v.voice_id in _FREE_TIER_BLOCKED_VOICES,
            }
            for v in result.voices
        ]
        return {"voices": voices, "default": _voice_id or None}
    except Exception as e:
        raise HTTPException(500, f"Failed to list voices: {e}")


@router.get("/status")
async def tts_status(ctx: AuthContext = Depends(get_current)):
    """Returns whether TTS is usable with the current configuration."""
    voice = _voice_id
    if not voice or voice in _FREE_TIER_BLOCKED_VOICES:
        return {
            "available": False,
            "reason": "elevenlabs_free_tier",
            "message": (
                "The configured voice is a pre-made library voice blocked on the ElevenLabs free tier. "
                "Set ELEVENLABS_VOICE_ID to a voice you own, or upgrade to Starter."
            ),
            "use_browser_tts": True,
        }
    return {"available": True, "voice_id": voice, "model": _model_id}
