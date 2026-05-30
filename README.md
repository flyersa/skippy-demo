# Skippy the Magnificent — demo

online as demo here: https://skippy.thinknerd.de

A small, self-contained voice + text chat demo of **Skippy the Magnificent**: an
animated avatar you can talk to (push-to-talk) or type to, powered by a local
open LLM (via [Ollama](https://ollama.com)) for the words and XTTS v2 for the
voice. No cloud APIs, no accounts, no tracking.

> ⚠️ **Please read [DISCLAIMER.md](DISCLAIMER.md).** Skippy, Expeditionary Force,
> and the voice are the creative work of **Craig Alanson** (author) and
> **R.C. Bray** (narrator). This is a non-commercial fan/technical demo for
> personal use only — support the creators and buy the books & audiobooks:
> https://www.craigalanson.com/

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for how the pieces fit together.

## What's in here

```
brain/     the orchestrator + web server (no GPU needed)
voice/     speech-to-text + Skippy text-to-speech (needs a CUDA GPU)
web/        the PWA front-end (avatar, push-to-talk, captions)
assets/     avatar clips + sprites (bring your own voice reference; bridges are generated)
```

Three moving parts: a browser talks **only** to the **brain**; the brain calls an
**Ollama** server (text) and the **voice** server (speech). They can all run on
one machine or be split across several — just point them at each other with env
vars.

## Requirements

- A machine with an **NVIDIA CUDA GPU** for the voice server (and to run the LLM
  on GPU). VRAM needed depends on the model you pick (a ~30B model at 4–5 bit ≈
  20–30 GB; smaller models work fine and are faster).
- [Ollama](https://ollama.com) and a pulled instruct model.
- Python 3.12+ (manual run) or Docker + the NVIDIA Container Toolkit (compose).

## Quick start (Docker Compose)

```bash
# 1) bring it up (builds brain + voice; starts Ollama)
docker compose up -d --build

# 2) pull an instruct model into Ollama (any chat model; default expects this one)
docker compose exec ollama ollama pull qwen2.5:32b-instruct-q5_K_M

# 3) open the demo
#    http://localhost:8080
```

First voice start downloads the XTTS v2 model automatically (a few minutes).

## Manual run (no Docker)

Three terminals (or three hosts):

```bash
# --- Ollama ---
ollama serve
ollama pull qwen2.5:32b-instruct-q5_K_M
#   tip: keep the model fully on GPU + fast:
#   OLLAMA_NUM_PARALLEL=2 OLLAMA_CONTEXT_LENGTH=8192 OLLAMA_KEEP_ALIVE=24h

# --- voice server (GPU) ---  see voice/README.md for the CUDA setup
cd voice && . .venv/bin/activate
COQUI_TOS_AGREED=1 VOICE_REF=../assets/voice/skippy-voice-ref.wav python voice_server.py

# --- brain ---
cd brain && pip install -r requirements.txt
OLLAMA_URL=http://localhost:11434 VOICE_URL=http://localhost:8770 \
  DEMO_STATIC=../web DEMO_ASSETS=../assets python server.py
# open http://localhost:8080
```

## Using it

Open the URL, read & accept the disclaimer, then **tap "Talk"** to speak
(tap again to send) or use the keyboard button to type. Skippy answers in
voice + text. (Optional "bridge" filler phrases can play during generation to
mask latency — **disabled by default**; enable with `DEMO_BRIDGES_ENABLED=1` if
your model/TTS are slow.)

> **First run:** drop a voice reference clip at `assets/voice/skippy-voice-ref.wav`
> (XTTS clones it — see `assets/voice/README.md`); none is shipped.

> Push-to-talk uses the microphone, which browsers only allow over **HTTPS** (or
> `http://localhost`). If you expose this beyond localhost, put it behind TLS
> (any reverse proxy / tunnel of your choice).

## Configuration

**Brain** (`brain/server.py`):

| var | default | meaning |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Ollama server |
| `VOICE_URL` | `http://localhost:8770` | voice server |
| `DEMO_MODEL` | `qwen2.5:32b-instruct-q5_K_M` | Ollama model to use |
| `DEMO_STATIC` / `DEMO_ASSETS` | `web` / `assets` | static + asset dirs |
| `DEMO_NUM_PREDICT` | `160` | max reply tokens (lower = snappier) |
| `DEMO_BRIDGES_ENABLED` | `0` | play instant "bridge" filler audio while generating |
| `DEMO_LORE_FILE` | `brain/lore.txt` | universe-knowledge block prepended to the persona |
| `DEMO_MAX_CONCURRENCY` | `6` | global in-flight turn cap |
| `DEMO_RATE_MAX` / `DEMO_RATE_WINDOW` | `20` / `60` | per-IP rate limit |
| `DEMO_CLIENT_IP_HEADER` | _(unset)_ | real-client-IP header if behind a proxy |

**Voice** (`voice/voice_server.py`): see [voice/README.md](voice/README.md).

## Customizing

- **Model / personality:** change `DEMO_MODEL`, or edit the `PERSONA` string in
  `brain/server.py`. The model has **no tools** — it only chats (it can't browse
  the web or take actions).
- **Voice:** none is shipped — drop your own ~10–20s reference clip at
  `assets/voice/skippy-voice-ref.wav` (XTTS clones it). If you enable bridges,
  regenerate them for the new voice with `voice/gen_bridges.py`.
- **Avatar:** drop your own clips into `assets/clips/` and adjust the clip pool
  in `web/app.js`.

## Notes

- The model is given a persona but **cannot call tools or reach the internet** —
  ask it for the weather and it will *invent* a sarcastic answer, not fetch one.
- Replies stream sentence-by-sentence so the first audio plays quickly.
- It's a public-friendly demo: per-IP rate limiting, a global concurrency cap,
  hard input-size caps, and per-visitor conversation isolation are built in.

## Credits & license

The character, story, and voice belong to their creators — see
[DISCLAIMER.md](DISCLAIMER.md). The demo **code** is provided as-is for personal,
non-commercial use.
