# Template image for the voice server. CUDA/PyTorch MUST match your GPU — adjust
# the base image and the torch index URL accordingly. The venv route in
# voice/README.md is the validated path; this Dockerfile is a starting point.
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# 1) CUDA-enabled torch matching the base image's CUDA version:
RUN pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu121
# 2) the rest of the stack
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY voice_server.py gen_bridges.py ./
ENV COQUI_TOS_AGREED=1 VOICE_REF=/app/assets/voice/skippy-voice-ref.wav
EXPOSE 8770
CMD ["python3", "voice_server.py"]
