"""
Task 6 — Lexical Search Module (BM25).

BM25 scores documents by keyword overlap, inverse document frequency, and document
length normalization. This implementation builds an in-memory BM25 index from the
chunks created in Task 4 so it works without an external service.
"""

from math import log
from pathlib import Path
import re

try:
    from .task4_chunking_indexing import load_documents, chunk_documents
except ImportError:  # Allow running as a script
    from task4_chunking_indexing import load_documents, chunk_documents


TOKEN_RE = re.compile(r"\w+", re.UNICODE)
CORPUS: list[dict] = []
BM25_INDEX = None


def tokenize(text: str) -> list[str]:
    """Tokenize Vietnamese text with a simple Unicode word regex."""
    return TOKEN_RE.findall(text.lower())


class SimpleBM25:
    """Small BM25Okapi-compatible implementation to avoid hard dependency issues."""

    def __init__(self, tokenized_corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.tokenized_corpus = tokenized_corpus
        self.k1 = k1
        self.b = b
        self.doc_len = [len(doc) for doc in tokenized_corpus]
        self.avgdl = sum(self.doc_len) / len(self.doc_len) if self.doc_len else 0
        self.doc_freqs: list[dict[str, int]] = []
        self.idf: dict[str, float] = {}
        self._initialize()

    def _initialize(self):
        df: dict[str, int] = {}
        for doc in self.tokenized_corpus:
            freqs: dict[str, int] = {}
            for token in doc:
                freqs[token] = freqs.get(token, 0) + 1
            self.doc_freqs.append(freqs)
            for token in freqs:
                df[token] = df.get(token, 0) + 1

        total_docs = len(self.tokenized_corpus)
        for token, freq in df.items():
            self.idf[token] = log(1 + (total_docs - freq + 0.5) / (freq + 0.5))

    def get_scores(self, query_tokens: list[str]) -> list[float]:
        scores = []
        for idx, freqs in enumerate(self.doc_freqs):
            score = 0.0
            doc_len = self.doc_len[idx]
            for token in query_tokens:
                if token not in freqs:
                    continue
                tf = freqs[token]
                denom = tf + self.k1 * (1 - self.b + self.b * doc_len / (self.avgdl or 1))
                score += self.idf.get(token, 0.0) * (tf * (self.k1 + 1)) / denom
            scores.append(score)
        return scores


def _load_corpus() -> list[dict]:
    documents = load_documents()
    return chunk_documents(documents)


def build_bm25_index(corpus: list[dict]):
    """Xây dựng BM25 index từ corpus."""
    tokenized_corpus = [tokenize(doc["content"]) for doc in corpus]
    return SimpleBM25(tokenized_corpus)


def _ensure_index():
    global CORPUS, BM25_INDEX
    if BM25_INDEX is None:
        CORPUS = _load_corpus()
        BM25_INDEX = build_bm25_index(CORPUS)
    return CORPUS, BM25_INDEX


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    """
    Tìm kiếm từ khóa sử dụng BM25.

    Returns list of {'content': str, 'score': float, 'metadata': dict}, sorted by
    score descending and limited to top_k.
    """
    corpus, bm25 = _ensure_index()
    if not corpus:
        return []

    scores = bm25.get_scores(tokenize(query))
    ranked_indices = sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)

    results = []
    for idx in ranked_indices[:top_k]:
        if scores[idx] <= 0:
            continue
        item = corpus[idx]
        results.append({
            "content": item["content"],
            "score": float(scores[idx]),
            "metadata": item.get("metadata", {}),
        })
    return results


if __name__ == "__main__":
    results = lexical_search("Điều 248 tàng trữ trái phép chất ma tuý", top_k=5)
    for r in results:
        print(f"[{r['score']:.3f}] {r['content'][:100]}...")
