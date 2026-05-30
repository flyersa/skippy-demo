# Architecture

Three small pieces. The **brain** is the only thing a browser talks to; it
calls the **Ollama** server (text) and the **voice** server (speech) over plain
HTTP. Point them at each other with env vars — they can run on one box or be
split across machines (e.g. the GPU work on a machine with a CUDA card, the
brain anywhere).

```
                        ┌──────────────────────────────────────────────┐
                        │                  browser (PWA)                 │
                        │   push-to-talk / text  +  avatar video player  │
                        └───────────────┬───────────────▲────────────────┘
                            audio/text  │               │  reply text (header)
                                        │               │  + streamed L16 audio
                                        ▼               │
                        ┌──────────────────────────────────────────────┐
                        │                    BRAIN                       │
                        │  • serves the PWA + avatar assets              │
                        │  • per-visitor conversation (in-memory)        │
                        │  • rate limit / caps / streaming               │
                        └───────┬───────────────────────────┬───────────┘
                       ASR/TTS  │                            │  chat
                                ▼                            ▼
              ┌───────────────────────────┐   ┌───────────────────────────┐
              │        VOICE (GPU)         │   │          OLLAMA           │
              │  faster-whisper  (ASR)     │   │  open instruct model      │
              │  XTTS v2         (TTS)     │   │  (e.g. a ~30B model)      │
              └───────────────────────────┘   └───────────────────────────┘
```

### Request flow (one turn)
1. Browser records a short clip (push-to-talk) or sends typed text to the brain.
2. **Talk:** brain → voice `/asr` → transcript.
3. Brain appends the transcript to *this visitor's* message history and calls
   Ollama `/api/chat` (the model is given the Skippy persona; it has **no tools**,
   so it can only chat — it cannot browse the web or take actions).
4. Brain splits the reply into sentences and, for each, calls voice `/synth`,
   **streaming** the audio back so the first sentence plays while the rest render.
5. The browser plays the streamed audio and shows the reply text. A short
   pre-rendered "bridge" phrase plays instantly to cover the first-token latency.

### Isolation between users
Each browser gets a random device id (stored locally) sent as `X-Device-Id`.
The brain keeps a separate, in-memory message history per device id, guarded by a
per-device lock, and sends only that history to Ollama. Ollama itself is
stateless, so conversations never bleed between visitors. Sessions are LRU-capped
and expire after inactivity.

### Notes
- The brain holds no secrets and needs no GPU.
- The voice server needs a CUDA GPU; the model VRAM footprint depends on the
  Ollama model + context length you choose.
- Scaling the brain horizontally would require moving per-device session state to
  a shared store; the demo runs a single brain instance.
