"""
Task 8 — PageIndex Vectorless RAG.

The real PageIndex integration can be enabled with PAGEINDEX_API_KEY. For local
assignment tests, this module provides a vectorless fallback over standardized
Markdown chunks using lexical overlap.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

try:
    from .task4_chunking_indexing import load_documents, chunk_documents
    from .task6_lexical_search import tokenize
except ImportError:
    from task4_chunking_indexing import load_documents, chunk_documents
    from task6_lexical_search import tokenize

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
STANDARDIZED_DIR = Path(__file__).parent.parent / "data" / "standardized"


def upload_documents():
    """Placeholder for real PageIndex upload; local fallback needs no upload."""
    docs = load_documents()
    return {"uploaded": len(docs), "mode": "local_fallback"}


def _score(query: str, content: str) -> float:
    query_tokens = set(tokenize(query))
    content_tokens = tokenize(content)
    if not query_tokens or not content_tokens:
        return 0.0
    content_set = set(content_tokens)
    return len(query_tokens & content_set) / len(query_tokens)


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Vectorless retrieval fallback using local document structure and terms."""
    chunks = chunk_documents(load_documents())
    results = []
    for chunk in chunks:
        score = _score(query, chunk["content"])
        if score > 0:
            results.append({
                "content": chunk["content"],
                "score": float(score),
                "metadata": chunk.get("metadata", {}),
                "source": "pageindex",
            })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    results = pageindex_search("hình phạt sử dụng ma tuý", top_k=3)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
