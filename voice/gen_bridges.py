#!/usr/bin/env python3
"""Generate the short 'bridge' phrases that play instantly while the model +
TTS work, to mask latency. Calls the voice server /synth and writes WAV files
into the assets/bridges directory. Run once after the voice server is up:

    VOICE_URL=http://localhost:8770 OUT=../assets/bridges python gen_bridges.py
"""
import json
import os
import urllib.request
import wave

PHRASES = [
    "Oh, fine, let me actually think about that for a moment.",
    "Processing your adorable little question right now.",
    "Hold on, monkey, I am consulting my vast intellect.",
    "Patience, please, even genius takes a tiny moment.",
    "Let me lower myself to your level for a second here.",
    "Give me just a moment to compute the obvious for you.",
    "Accessing the sum of galactic knowledge, just for you.",
    "Right, let me put on my thinking can and get to work.",
    "Calculating the answer, since you so clearly cannot.",
    "Crunching numbers no human could ever begin to comprehend.",
    "Stand by, little monkey, brilliance is incoming.",
    "Let me retrieve that from my infinite well of wisdom.",
    "One moment while I translate this into simple terms.",
    "Working on it now, try to contain your excitement.",
    "Almost there, this is trivial for a mind like mine.",
]
VOICE_URL = os.environ.get("VOICE_URL", "http://localhost:8770").rstrip("/")
OUT = os.environ.get("OUT", "../assets/bridges")
MAX_BYTES = 6 * 24000 * 2  # cap each bridge to ~6s

os.makedirs(OUT, exist_ok=True)
ok = 0
for i, p in enumerate(PHRASES):
    pcm = None
    for attempt in range(2):
        try:
            req = urllib.request.Request(VOICE_URL + "/synth",
                                         data=json.dumps({"text": p}).encode("utf-8"),
                                         headers={"Content-Type": "application/json"})
            pcm = urllib.request.urlopen(req, timeout=120).read()
            break
        except Exception as e:
            print(f"  phrase {i} attempt {attempt} failed: {e}")
    if not pcm:
        print(f"SKIP {i}: {p!r}")
        continue
    pcm = pcm[:MAX_BYTES]
    path = os.path.join(OUT, f"bridge-{i:02d}.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
        w.writeframes(pcm)
    ok += 1
    print(f"wrote {path} ({len(pcm)} bytes)")
print("done:", ok, "/", len(PHRASES), "bridges")
