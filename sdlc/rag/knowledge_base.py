"""Lightweight, dependency-free RAG knowledge base for uploaded coding
standards documents. Chunks are scored with a simple TF-IDF style
lexical match - no embedding model or vector DB needed for this scale."""
import json
import math
import os
import re
from collections import Counter

from sdlc.config import KNOWLEDGE_BASE_FILE, ensure_output_dir

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120

_cache: list[dict] | None = None


def _load() -> list[dict]:

    global _cache

    if _cache is not None:
        return _cache

    if os.path.isfile(KNOWLEDGE_BASE_FILE):
        try:
            with open(KNOWLEDGE_BASE_FILE, "r", encoding="utf-8") as file:
                _cache = json.load(file)
        except (OSError, json.JSONDecodeError):
            _cache = []
    else:
        _cache = []

    return _cache


def _save() -> None:

    ensure_output_dir()

    with open(KNOWLEDGE_BASE_FILE, "w", encoding="utf-8") as file:
        json.dump(_cache or [], file)


def _extract_text(filename: str, raw: bytes) -> str:

    extension = os.path.splitext(filename)[1].lower()

    if extension == ".pdf":
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if extension in (".docx", ".doc"):
        try:
            # python-docx extracts text from .docx files. Fall back to
            # binary decode if the library is not available.
            from docx import Document
            from io import BytesIO

            doc = Document(BytesIO(raw))
            paragraphs = [p.text for p in doc.paragraphs]
            return "\n".join(paragraphs)
        except Exception:
            pass

    # Default: treat as utf-8 text and ignore decode errors
    return raw.decode("utf-8", errors="ignore")


def _chunk_text(text: str) -> list[str]:

    text = re.sub(r"\r\n", "\n", text).strip()
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = end - CHUNK_OVERLAP

    return chunks


def add_document(filename: str, raw: bytes, category: str | None = None) -> int:
    """Extracts, chunks and persists one uploaded document. Returns the
    number of chunks added. When `category` is provided the stored source
    name is prefixed with `<category>:` so callers can filter retrievals by
    category (for example 'engineering' or 'design')."""

    text = _extract_text(filename, raw)
    chunks = _chunk_text(text)

    source_name = f"{category}:{filename}" if category else filename

    store = _load()
    store[:] = [c for c in store if c["source"] != source_name]
    store.extend({"source": source_name, "text": chunk} for chunk in chunks)
    _save()

    return len(chunks)


def category_summary(category: str, top_k: int = 4) -> str:
    """Return a short concatenated excerpt summary from the knowledge base
    for the given category. Returns an empty string when nothing is found."""

    store = _load()
    prefix = f"{category}:"
    filtered = [c for c in store if c.get("source", "").startswith(prefix)]
    if not filtered:
        return ""

    # Include each source, selecting evenly spaced chunks when a page is long.
    # Bound the complete prompt while avoiding navigation-heavy first-chunk bias.
    sources = list(dict.fromkeys(c["source"] for c in filtered))
    per_source = max(900, 24000 // len(sources))
    excerpts = []
    for source in sources:
        chunks = [c["text"] for c in filtered if c["source"] == source]
        count = max(1, per_source // CHUNK_SIZE)
        if len(chunks) > count:
            indices = [round(i * (len(chunks) - 1) / max(1, count - 1)) for i in range(count)]
            chunks = [chunks[i] for i in indices]
        excerpts.append(f"[{source}]\n" + "\n".join(chunks)[:per_source])
    return "\n\n".join(excerpts)[:28000]


def replace_category(category: str, documents: list[tuple[str, str]]) -> int:
    """Replace a URL import only after all fetched documents are available."""
    global _cache
    chunks = [
        {"source": f"{category}:{source}", "text": chunk}
        for source, text in documents for chunk in _chunk_text(text)
    ]
    if not chunks:
        raise ValueError("No guidance was extracted")
    _cache = [c for c in _load() if not c["source"].startswith(f"{category}:")] + chunks
    _save()
    return len(chunks)



def get_status() -> dict:

    store = _load()
    sources = sorted({chunk["source"] for chunk in store})

    return {"documents": sources, "chunk_count": len(store)}


def clear() -> None:

    global _cache

    _cache = []
    _save()


def _tokenize(text: str) -> list[str]:

    return re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower())


def retrieve(query: str, top_k: int = 4, category: str | None = None) -> list[dict]:
    """Returns the top_k most relevant chunks for the query using a
    simple TF-IDF lexical score. Returns an empty list if the knowledge
    base is empty or nothing matches."""
    store = _load()
    if category:
        prefix = f"{category}:"
        store = [c for c in store if c.get("source", "").startswith(prefix)]
    query_terms = set(_tokenize(query))

    if not store or not query_terms:
        return []

    doc_tokens = [_tokenize(chunk["text"]) for chunk in store]
    doc_freq = Counter()
    for tokens in doc_tokens:
        doc_freq.update(set(tokens))

    n_docs = len(store)
    idf = {
        term: math.log((n_docs + 1) / (doc_freq.get(term, 0) + 1)) + 1
        for term in query_terms
    }

    scored = []
    for chunk, tokens in zip(store, doc_tokens):
        if not tokens:
            continue
        term_counts = Counter(tokens)
        total = sum(term_counts.values())
        score = sum(
            (term_counts.get(term, 0) / total) * idf[term]
            for term in query_terms
        )
        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)

    return [chunk for _, chunk in scored[:top_k]]
