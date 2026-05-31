#!/usr/bin/env python3
"""Skippy demo RAG retrieval service (runs alongside Ollama).

Loads the prebuilt vector index into RAM and answers /retrieve with the top-k
canon passages for a query. Brute-force cosine over a normalized float32 matrix
(index is small — a few thousand chunks — so no vector DB needed).

The response intentionally returns ONLY chunk text + score: no book title, no
page, no source. Retrieval enriches the persona's "memory"; it must never become
a citation or a verbatim reproduction channel.

    python rag_server.py            # binds 0.0.0.0:8771

Env: RAG_INDEX_DIR (./index), OLLAMA_URL, RAG_EMBED_MODEL (bge-m3),
     RAG_BIND (0.0.0.0), RAG_PORT (8771), RAG_MAX_K (8), RAG_CHARS (900).
"""
import json, logging, os
from pathlib import Path

import aiohttp
import numpy as np
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("skippy-rag")

INDEX_DIR = Path(os.environ.get("RAG_INDEX_DIR", "./index"))
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "bge-m3")
BIND = os.environ.get("RAG_BIND", "0.0.0.0")
PORT = int(os.environ.get("RAG_PORT", "8771"))
MAX_K = int(os.environ.get("RAG_MAX_K", "8"))
CHARS = int(os.environ.get("RAG_CHARS", "900"))   # hard per-chunk cap (anti-verbatim)
TIMEOUT = aiohttp.ClientTimeout(total=15)

_MAT: np.ndarray | None = None
_CHUNKS: list[str] = []
_META: dict = {}
_http: aiohttp.ClientSession | None = None


def _load():
    global _MAT, _CHUNKS, _META
    _MAT = np.load(INDEX_DIR / "embeddings.npy")
    _CHUNKS = json.loads((INDEX_DIR / "chunks.json").read_text(encoding="utf-8"))
    _META = json.loads((INDEX_DIR / "meta.json").read_text(encoding="utf-8"))
    log.info("loaded %d chunks x %d dims (model=%s)",
             _MAT.shape[0], _MAT.shape[1], _META.get("model"))


async def _embed(text: str) -> np.ndarray:
    body = {"model": EMBED_MODEL, "input": [text]}
    async with _http.post(f"{OLLAMA}/api/embed", json=body) as r:
        data = await r.json()
    v = np.asarray(data["embeddings"][0], dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n else v


async def healthz(_req: web.Request) -> web.Response:
    return web.json_response({"ok": _MAT is not None, "chunks": len(_CHUNKS),
                              "model": _META.get("model")})


async def retrieve(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"error": "bad json"}, status=400)
    q = (data.get("q") or "").strip()
    k = min(int(data.get("k", 4) or 4), MAX_K)
    if not q:
        return web.json_response({"results": []})
    try:
        qv = await _embed(q[:1000])
    except Exception as e:
        log.warning("embed failed: %s", e)
        return web.json_response({"error": "embed failed"}, status=502)
    sims = _MAT @ qv                      # cosine (matrix is pre-normalized)
    idx = np.argpartition(-sims, range(min(k, len(sims))))[:k]
    idx = idx[np.argsort(-sims[idx])]
    results = [{"text": _CHUNKS[i][:CHARS], "score": float(sims[i])} for i in idx]
    return web.json_response({"results": results})


async def _on_start(app):
    global _http
    _http = aiohttp.ClientSession(timeout=TIMEOUT)


async def _on_stop(app):
    if _http:
        await _http.close()


def main():
    _load()
    app = web.Application()
    app.router.add_get("/healthz", healthz)
    app.router.add_post("/retrieve", retrieve)
    app.on_startup.append(_on_start)
    app.on_cleanup.append(_on_stop)
    log.info("skippy-rag on %s:%d  index=%s", BIND, PORT, INDEX_DIR)
    web.run_app(app, host=BIND, port=PORT, access_log=None)


if __name__ == "__main__":
    main()
