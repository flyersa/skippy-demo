# Voice server (GPU)

English speech-to-text (faster-whisper) + Skippy text-to-speech (XTTS v2,
voice-cloned from `assets/voice/skippy-voice-ref.wav`). Needs a CUDA GPU.

## Quick setup (virtualenv)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install --upgrade pip

# 1) Install a CUDA-enabled PyTorch matching YOUR GPU/driver.
#    Pick the right CUDA index for your card from pytorch.org. Examples:
#      older/most cards (CUDA 12.x):
#        pip install torch --index-url https://download.pytorch.org/whl/cu121
#      newest cards needing CUDA 13 (what this demo was validated on):
#        pip install torch==2.11.0 --index-url https://download.pytorch.org/whl/cu130
pip install torch  # (or the pinned/index form above)

# 2) The rest of the stack
pip install -r requirements.txt

# 3) Run
export COQUI_TOS_AGREED=1          # accept the coqui XTTS license (auto-downloads the model)
export VOICE_REF=../assets/voice/skippy-voice-ref.wav
python voice_server.py             # serves :8770
```

## Known-good versions (validated)

This demo was validated with:
`torch 2.11 (CUDA 13)`, `coqui-tts 0.26.0`, `faster-whisper 1.2.1`,
`ctranslate2 4.7.1`, `numpy<2`, `torchcodec 0.11.1`. On older GPUs use a CUDA
12.x torch build; the rest are the same.

## CUDA library gotcha

`ctranslate2` (faster-whisper's backend) needs cuDNN/cuBLAS at runtime. If you
see `Library libcublas.so.12 ... not found`, make the cu12 libraries visible,
e.g. install `nvidia-cudnn-cu12` + `nvidia-cublas-cu12` and add them to the
library path:

```bash
export LD_LIBRARY_PATH="$(python -c 'import nvidia.cublas, nvidia.cudnn, os; \
  print(os.path.dirname(nvidia.cublas.__file__)+"/lib:"+os.path.dirname(nvidia.cudnn.__file__)+"/lib")')"
```

## Bridges (optional but recommended)

Short pre-rendered "thinking" phrases that play instantly to hide latency. After
the voice server is up:

```bash
VOICE_URL=http://localhost:8770 OUT=../assets/bridges python gen_bridges.py
```

Bridges are NOT shipped (they would be in a cloned voice). Generate them once
your voice reference is in place and the voice server is running. They are
optional and off by default (`DEMO_BRIDGES_ENABLED=1` to enable).

## Environment variables

| var | default | meaning |
|---|---|---|
| `VOICE_PORT` | `8770` | listen port |
| `VOICE_BIND` | `0.0.0.0` | bind address |
| `ASR_MODEL` | `small.en` | faster-whisper model |
| `VOICE_REF` | `assets/voice/skippy-voice-ref.wav` | XTTS speaker reference |
| `DEMO_TTS_CONCURRENCY` | `2` | max simultaneous TTS generations (GPU guard) |
| `DEMO_MAX_ASR_SECONDS` | `45` | hard cap on transcribed audio length |
