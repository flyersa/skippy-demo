#!/usr/bin/env python3
"""Ingest legally-owned ebooks into a local vector index for Skippy demo RAG.

Offline, one-time. Extracts text from PDFs, cleans, chunks, embeds via a local
Ollama embedding model, and writes a normalized float32 matrix + chunk texts.
NO page/book citation is kept in the queryable payload — retrieval is meant to
enrich the persona's "memory", never to quote or cite sources.

    python rag_ingest.py --books ./books --out ./index

Env: OLLAMA_URL (default http://127.0.0.1:11434), RAG_EMBED_MODEL (default bge-m3).
"""
import argparse, hashlib, json, os, re, sys, time, urllib.request
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np

OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "bge-m3")
CHUNK_WORDS = int(os.environ.get("RAG_CHUNK_WORDS", "220"))
CHUNK_OVERLAP = int(os.environ.get("RAG_CHUNK_OVERLAP", "40"))
EMBED_BATCH = int(os.environ.get("RAG_EMBED_BATCH", "64"))

_WS = re.compile(r"[ \t]+")
_PAGENUM = re.compile(r"^\s*\d{1,4}\s*$")


def extract_text(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    out = []
    for page in doc:
        txt = page.get_text("text")
        for line in txt.splitlines():
            s = line.strip()
            if not s:
                continue
            if "oceanofpdf" in s.lower():
                continue
            if _PAGENUM.match(s):              # bare page numbers
                continue
            out.append(s)
    doc.close()
    # join, normalize whitespace, repair hyphenated line breaks
    text = "\n".join(out)
    text = text.replace("-\n", "")            # de-hyphenate across line breaks
    text = text.replace("\n", " ")
    text = _WS.sub(" ", text)
    return text.strip()


def chunk_words(text: str, size: int, overlap: int):
    words = text.split(" ")
    step = max(1, size - overlap)
    for i in range(0, len(words), step):
        piece = words[i:i + size]
        if len(piece) < 30:                   # drop tiny tail fragments
            continue
        yield " ".join(piece)


def embed_batch(texts):
    body = json.dumps({"model": EMBED_MODEL, "input": texts}).encode()
    req = urllib.request.Request(f"{OLLAMA}/api/embed", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.loads(r.read())
    return data["embeddings"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", default="./books")
    ap.add_argument("--out", default="./index")
    args = ap.parse_args()

    books_dir, out_dir = Path(args.books), Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(books_dir.glob("*.pdf"))
    print(f"found {len(pdfs)} pdfs")

    seen_hashes = set()
    chunks = []            # list[str]
    titles = []            # parallel list[str] (internal only, NOT served)
    for pdf in pdfs:
        h = hashlib.md5(pdf.read_bytes()).hexdigest()
        if h in seen_hashes:
            print(f"  skip dup: {pdf.name}")
            continue
        seen_hashes.add(h)
        title = re.sub(r"_OceanofPDF\.com_|_-_.*|\.pdf|\s*\(\d+\)", "",
                       pdf.stem).replace("_", " ").strip()
        text = extract_text(pdf)
        n0 = len(chunks)
        for c in chunk_words(text, CHUNK_WORDS, CHUNK_OVERLAP):
            chunks.append(c)
            titles.append(title)
        print(f"  {pdf.name}: {len(text.split())} words -> {len(chunks)-n0} chunks  [{title}]")

    print(f"total chunks: {len(chunks)}  — embedding with {EMBED_MODEL} ...")
    vecs = []
    t0 = time.time()
    for i in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[i:i + EMBED_BATCH]
        vecs.extend(embed_batch(batch))
        if (i // EMBED_BATCH) % 10 == 0:
            print(f"  {i+len(batch)}/{len(chunks)}  ({time.time()-t0:.0f}s)")
    mat = np.asarray(vecs, dtype=np.float32)
    # L2-normalize so cosine similarity == dot product
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    mat = mat / norms

    np.save(out_dir / "embeddings.npy", mat)
    (out_dir / "chunks.json").write_text(
        json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
    (out_dir / "titles.json").write_text(
        json.dumps(titles, ensure_ascii=False), encoding="utf-8")
    meta = {"model": EMBED_MODEL, "dim": int(mat.shape[1]),
            "count": int(mat.shape[0]), "chunk_words": CHUNK_WORDS,
            "overlap": CHUNK_OVERLAP, "built": int(time.time())}
    (out_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    print(f"done: {mat.shape[0]} vectors x {mat.shape[1]} dims in {time.time()-t0:.0f}s")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
