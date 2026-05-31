# Optional RAG — enrich answers from your own ebooks

This is an **optional** retrieval layer. With it enabled, the brain looks up
relevant background passages for each question and feeds them to the model as
"memory" so answers stay accurate to deep canon. It is **off by default**.

> ⚠️ **Copyright.** Only ingest books you legally own, for personal/internal use.
> The index is a derived copy of the source text — it is **git-ignored** and must
> never be committed, published, or redistributed. The persona is instructed to
> **paraphrase only and never quote, recite, or cite** sources; keep it that way.

## How it works

1. **`ingest.py`** — extracts text from PDFs, cleans, chunks (~220 words, 40
   overlap), embeds each chunk with a local Ollama embedding model, and writes a
   normalized `embeddings.npy` + `chunks.json` to `index/`.
2. **`server.py`** — loads that index into RAM and serves `POST /retrieve`
   (`{"q": "...", "k": 4}` → top-k passages by cosine similarity). Brute-force
   over the matrix; no vector DB needed at this scale (tens of thousands of
   chunks). Response is **text + score only** — no titles, pages, or sources.
3. The brain calls `/retrieve` per turn (fail-open) and injects the passages as
   a transient "CANON MEMORY" system message with strict paraphrase-only rules.

## Setup

```bash
# 1. pull an embedding model in Ollama
ollama pull bge-m3

# 2. put YOUR legally-owned PDFs here
mkdir -p rag/books && cp /path/to/your/*.pdf rag/books/

# 3. build the index (one-time)
python -m venv .venv && . .venv/bin/activate
pip install pymupdf numpy aiohttp
python rag/ingest.py --books rag/books --out rag/index

# 4. run the retrieval service
python rag/server.py            # binds 0.0.0.0:8771

# 5. enable RAG in the brain
export DEMO_RAG_ENABLED=1
export RAG_URL=http://localhost:8771
```

## Guardrails (keep these if exposing publicly)

- Small chunks + low `k` so no single retrieval is a long passage; injected
  context is hard-capped.
- Persona refuses verbatim recitation and paraphrases everything in voice.
- Never cites books/pages/sources.
- `DEMO_RAG_ENABLED=0` turns the whole thing off instantly (brain falls back to
  the built-in `lore.txt`).

## Tunables (env)

| var | default | meaning |
|-----|---------|---------|
| `RAG_EMBED_MODEL` | `bge-m3` | Ollama embedding model |
| `RAG_CHUNK_WORDS` | `220` | words per chunk (ingest) |
| `RAG_CHUNK_OVERLAP` | `40` | overlap words (ingest) |
| `RAG_MAX_K` | `8` | server cap on k |
| `RAG_CHARS` | `900` | per-chunk char cap returned (anti-verbatim) |
| `DEMO_RAG_K` | `4` | passages injected per turn (brain) |
