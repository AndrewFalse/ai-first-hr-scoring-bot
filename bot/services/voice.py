"""Транскрибация голосовых сообщений через OpenRouter (аудио-модель)."""
from __future__ import annotations

import asyncio
import base64
import logging
from io import BytesIO

from openai import AsyncOpenAI

from bot.config import settings

logger = logging.getLogger(__name__)

_TRANSCRIBE_PROMPT = (
    "Транскрибируй это голосовое сообщение дословно на русском языке. "
    "Верни только текст транскрипции без пояснений и без кавычек."
)


async def _ogg_to_mp3(ogg_bytes: bytes) -> bytes:
    """Конвертирует OGG/Opus → MP3 через ffmpeg."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", "pipe:0", "-f", "mp3", "-ab", "64k", "pipe:1",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    stdout, _ = await proc.communicate(input=ogg_bytes)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg conversion failed")
    return stdout


class VoiceService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.OPENROUTER_API_KEY,
            base_url="https://openrouter.ai/api/v1",
        )

    async def transcribe(self, audio: BytesIO, filename: str = "audio.ogg") -> str | None:
        try:
            audio.seek(0)
            mp3_bytes = await _ogg_to_mp3(audio.read())
            audio_b64 = base64.b64encode(mp3_bytes).decode("utf-8")
            response = await self._client.chat.completions.create(
                model=settings.OPENROUTER_AUDIO_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": _TRANSCRIBE_PROMPT,
                            },
                            {
                                "type": "input_audio",
                                "input_audio": {
                                    "data": audio_b64,
                                    "format": "mp3",
                                },
                            },
                        ],
                    }
                ],
            )
            text = response.choices[0].message.content or ""
            return text.strip() or None
        except Exception:
            logger.exception("Voice transcription failed")
            return None
