# Bridge phrases (generated, not shipped)

These short "thinking" filler clips are in the cloned demo voice, so they are
not shipped. After you provide your own voice reference and start the voice
server, generate them:

    VOICE_URL=http://localhost:8770 OUT=../assets/bridges python ../voice/gen_bridges.py

They are optional and OFF by default (set `DEMO_BRIDGES_ENABLED=1` to use them).
