#!/usr/bin/env python3
"""Skippy demo — voice server (GPU).

A small async API exposing:
  POST /asr    -> {"text": "..."}   English speech-to-text (faster-whisper)
  POST /synth  -> raw L16 PCM       Skippy text-to-speech (XTTS v2, voice-cloned
                                    from a short reference clip)
  GET  /healthz

Runs on a CUDA GPU. The XTTS v2 model is downloaded automatically by
coqui-tts on first start (set COQUI_TOS_AGREED=1). The brain calls this; it
holds no conversation state. At most DEMO_TTS_CONCURRENCY synths run at once
(GPU-overload guard) and ASR audio is hard-capped in duration.
"""
from __future__ import annotations

import asyncio
import io
import logging
import os

import numpy as np
import torch  # noqa: F401  (ensures CUDA libs load before TTS)
from aiohttp import web
from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio
from TTS.api import TTS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("skippy.voice")

PORT = int(os.environ.get("VOICE_PORT", "8770"))
BIND = os.environ.get("VOICE_BIND", "0.0.0.0")
ASR_MODEL = os.environ.get("ASR_MODEL", "small.en")
DEVICE = os.environ.get("VOICE_DEVICE", "cuda")
COMPUTE_TYPE = os.environ.get("ASR_COMPUTE_TYPE", "float16")
VOICE_REF = os.environ.get("VOICE_REF", "assets/voice/skippy-voice-ref.wav")
TTS_LANG = os.environ.get("TTS_LANG", "en")
MAX_TTS = int(os.environ.get("DEMO_TTS_CONCURRENCY", "2"))
MAX_ASR = int(os.environ.get("DEMO_ASR_CONCURRENCY", "3"))
MAX_AUDIO = int(os.environ.get("DEMO_MAX_AUDIO", str(1024 * 1024)))
MAX_ASR_SECONDS = int(os.environ.get("DEMO_MAX_ASR_SECONDS", "45"))
TTS_RATE = 24000

log.info("loading Whisper '%s' on %s ...", ASR_MODEL, DEVICE)
_asr = WhisperModel(ASR_MODEL, device=DEVICE, compute_type=COMPUTE_TYPE)
log.info("loading XTTS v2 on %s ...", DEVICE)
_xtts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2").to(DEVICE)
log.info("models loaded; ASR<=%d TTS<=%d", MAX_ASR, MAX_TTS)

_tts_sem = asyncio.Semaphore(MAX_TTS)
_asr_sem = asyncio.Semaphore(MAX_ASR)


def _transcribe(blob: bytes) -> str:
    audio = decode_audio(io.BytesIO(blob), sampling_rate=16000)
    cap = MAX_ASR_SECONDS * 16000
    if len(audio) > cap:
        audio = audio[:cap]
    segments, _ = _asr.transcribe(audio, language="en", beam_size=1)
    return " ".join(s.text for s in segments).strip()


def _synth(text: str) -> bytes:
    wav = _xtts.tts(text=text, speaker_wav=VOICE_REF, language=TTS_LANG)
    arr = np.clip(np.asarray(wav, dtype=np.float32), -1.0, 1.0)
    return (arr * 32767.0).astype("<i2").tobytes()  # L16 little-endian, 24 kHz mono


async def asr(request: web.Request) -> web.Response:
    blob = await request.read()
    if not blob:
        return web.json_response({"error": "empty audio"}, status=400)
    async with _asr_sem:
        try:
            text = await asyncio.to_thread(_transcribe, blob)
        except Exception as e:
            log.warning("asr failed: %s", e)
            return web.json_response({"error": "asr failed"}, status=500)
    return web.json_response({"text": text})


async def synth(request: web.Request) -> web.Response:
    try:
        text = ((await request.json()).get("text") or "").strip()[:1200]
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    if not text:
        return web.json_response({"error": "no text"}, status=400)
    async with _tts_sem:
        try:
            pcm = await asyncio.to_thread(_synth, text)
        except Exception as e:
            log.warning("synth failed: %s", e)
            return web.json_response({"error": "synth failed"}, status=500)
    return web.Response(body=pcm, content_type="audio/L16",
                        headers={"X-Sample-Rate": str(TTS_RATE), "Cache-Control": "no-store"})


async def healthz(request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "asr_model": ASR_MODEL, "tts_slots": MAX_TTS})


def main() -> None:
    app = web.Application(client_max_size=MAX_AUDIO)
    app.router.add_post("/asr", asr)
    app.router.add_post("/synth", synth)
    app.router.add_get("/healthz", healthz)
    log.info("skippy demo voice on %s:%d", BIND, PORT)
    web.run_app(app, host=BIND, port=PORT, print=None)


if __name__ == "__main__":
    main()
