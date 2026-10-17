"""Knowledge base: ingest PDF/TXT/MD files into a persistent ChromaDB collection.

Embeddings use ChromaDB's built-in default embedding function (a small ONNX
MiniLM model), so no torch / sentence-transformers is needed.
"""
import hashlib
import re
from collections import Counter
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "chroma_db"
COLLECTION = "studypilot"
CHUNK_SIZE = 800     # characters per chunk
CHUNK_OVERLAP = 150  # characters shared between neighbouring chunks
SUPPORTED = {".pdf", ".txt", ".md"}

_client = None


def get_collection():
    """Open (or create) the persistent collection. The client is created once per process."""
    global _client
    if _client is None:
        # telemetry off: the knowledge base stays fully private / local
        _client = chromadb.PersistentClient(path=str(DB_DIR), settings=Settings(anonymized_telemetry=False))
    return _client.get_or_create_collection(
        name=COLLECTION,
        embedding_function=embedding_functions.DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},  # distance = 1 - cosine similarity
    )


# ---------- reading & chunking ----------

def read_pages(path: Path) -> list[tuple[int, str]]:
    """Return [(page_number, text)]. Text/Markdown files count as a single page 1."""
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
    # utf-8-sig strips the BOM that Windows editors / PowerShell often add
    return [(1, path.read_text(encoding="utf-8-sig", errors="ignore"))]


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into ~size-char chunks with overlap, preferring to cut at a newline/sentence/space."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window = text[start + size // 2:end]
            for sep in ("\n\n", "\n", ". ", " "):
                cut = window.rfind(sep)
                if cut != -1:
                    end = start + size // 2 + cut + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        next_start = max(end - overlap, start + 1)  # always move forward
        space = text.find(" ", next_start, end)     # begin the next chunk on a whole word
        start = space + 1 if space != -1 else next_start
    return chunks


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------- public API ----------

def ingest_file(path) -> dict:
    """Ingest one file. Skips it if the exact same content was ingested before."""
    path = Path(path)
    if path.suffix.lower() not in SUPPORTED:
        return {"source": path.name, "status": "unsupported", "chunks": 0}

    col = get_collection()
    digest = file_hash(path)
    if col.get(where={"file_hash": digest}, limit=1)["ids"]:
        return {"source": path.name, "status": "skipped (already ingested)", "chunks": 0}

    # Same file name but new content -> replace the old version.
    col.delete(where={"source": path.name})

    ids, docs, metas = [], [], []
    for page, text in read_pages(path):
        for i, chunk in enumerate(chunk_text(text)):
            ids.append(f"{path.name}:{digest[:8]}:p{page}:c{i}")
            docs.append(chunk)
            metas.append({"source": path.name, "page": page, "chunk": i, "file_hash": digest})
    if not docs:
        return {"source": path.name, "status": "empty (no extractable text)", "chunks": 0}

    col.add(ids=ids, documents=docs, metadatas=metas)
    return {"source": path.name, "status": "ingested", "chunks": len(docs)}


def ingest_folder(folder) -> list[dict]:
    """Ingest every supported file in a folder (non-recursive)."""
    folder = Path(folder)
    files = sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED)
    return [ingest_file(p) for p in files]


def search(query: str, k: int = 4) -> list[dict]:
    """Semantic search. Returns [{text, source, page, distance}] – lower distance = closer."""
    col = get_collection()
    total = col.count()
    if total == 0 or not query.strip():
        return []
    res = col.query(query_texts=[query], n_results=min(k, total))
    hits = []
    for text, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append({"text": text, "source": meta.get("source"), "page": meta.get("page"),
                     "distance": round(float(dist), 4)})
    return hits


def list_documents() -> list[dict]:
    """[{source, chunks}] for every document in the knowledge base."""
    metas = get_collection().get(include=["metadatas"])["metadatas"]
    counts = Counter(m["source"] for m in metas)
    return [{"source": s, "chunks": n} for s, n in sorted(counts.items())]


def delete_document(name: str) -> int:
    """Remove every chunk of a document. Returns how many chunks were deleted."""
    col = get_collection()
    ids = col.get(where={"source": name})["ids"]
    if ids:
        col.delete(ids=ids)
    return len(ids)


def get_document_text(name: str, max_chars: int = 6000) -> str:
    """Rebuild a document's text (in page/chunk order) for the automation workflow."""
    res = get_collection().get(where={"source": name}, include=["documents", "metadatas"])
    pairs = sorted(zip(res["metadatas"], res["documents"]), key=lambda x: (x[0]["page"], x[0]["chunk"]))
    text = "\n".join(doc for _, doc in pairs)
    return text[:max_chars]


def stats() -> dict:
    docs = list_documents()
    return {"documents": len(docs), "chunks": sum(d["chunks"] for d in docs)}
