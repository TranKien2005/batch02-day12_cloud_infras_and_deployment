"""
Task 5 — Semantic Search Module.

This module prefers the local JSON vector index produced by Task 4. If embeddings
have not been created yet, it falls back to a deterministic lexical-overlap
similarity so the pipeline still works offline for tests and demos.
"""

import json
import math
import re
from pathlib import Path

try:
    from .task4_chunking_indexing import LOCAL_INDEX_PATH, load_documents, chunk_documents, embed_texts_locally
    from .task6_lexical_search import tokenize
except ImportError:  # Allow running as a script
    from task4_chunking_indexing import LOCAL_INDEX_PATH, load_documents, chunk_documents, embed_texts_locally
    from task6_lexical_search import tokenize


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


def _load_index() -> list[dict]:
    if LOCAL_INDEX_PATH.exists():
        return json.loads(LOCAL_INDEX_PATH.read_text(encoding="utf-8"))
    return chunk_documents(load_documents())


def _embed_query(query: str, embedding_source: str | None = None) -> list[float] | None:
    if embedding_source == "local_hashing":
        return embed_texts_locally([query])[0]

    try:
        from .task4_chunking_indexing import _embed_with_openai
    except ImportError:
        from task4_chunking_indexing import _embed_with_openai

    try:
        return _embed_with_openai([query])[0]
    except Exception:
        if embedding_source:
            return embed_texts_locally([query])[0]
        return None


def _overlap_score(query: str, content: str) -> float:
    query_tokens = set(tokenize(query))
    content_tokens = tokenize(content)
    if not query_tokens or not content_tokens:
        return 0.0
    content_set = set(content_tokens)
    overlap = len(query_tokens & content_set)
    density = overlap / len(query_tokens)
    frequency = sum(1 for token in content_tokens if token in query_tokens) / len(content_tokens)
    return density + frequency


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa sử dụng vector similarity nếu có embeddings, fallback sang
    overlap similarity nếu chưa tạo index embedding.
    """
    items = _load_index()
    if not items:
        return []

    query_embedding = None
    if items and "embedding" in items[0]:
        query_embedding = _embed_query(query, items[0].get("embedding_source"))

    results = []
    for item in items:
        if query_embedding is not None and "embedding" in item:
            score = _cosine_similarity(query_embedding, item["embedding"])
        else:
            score = _overlap_score(query, item["content"])

        if score > 0:
            results.append({
                "content": item["content"],
                "score": float(score),
                "metadata": item.get("metadata", {}),
            })

    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


if __name__ == "__main__":
    results = semantic_search("hình phạt cho tội tàng trữ ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
