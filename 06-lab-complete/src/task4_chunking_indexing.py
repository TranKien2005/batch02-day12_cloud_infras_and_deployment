"""
Task 4 — Chunking & Indexing vào Vector Store.

Hướng dẫn:
    1. Đọc toàn bộ markdown files từ data/standardized/
    2. Chọn 1 chunking strategy (giải thích lý do)
    3. Chọn 1 embedding model (giải thích lý do)
    4. Index vào vector store (Weaviate khuyến cáo)
"""

import hashlib
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

PROJECT_DIR = Path(__file__).parent.parent
STANDARDIZED_DIR = PROJECT_DIR / "data" / "standardized"
VECTORSTORE_DIR = PROJECT_DIR / "data" / "vectorstore"
LOCAL_INDEX_PATH = VECTORSTORE_DIR / "chunks_with_embeddings.json"


# =============================================================================
# CONFIGURATION — Giải thích lựa chọn
# =============================================================================

# RecursiveCharacterTextSplitter phù hợp với dữ liệu hỗn hợp legal/news vì nó ưu
# tiên cắt theo đoạn, dòng, câu, từ rồi mới tới ký tự. Cách này an toàn hơn
# MarkdownHeaderTextSplitter khi file markdown được convert từ PDF/HTML không có
# heading ổn định.
CHUNK_SIZE = 500

# Overlap 50 ký tự giữ lại một phần ngữ cảnh giữa hai chunk liền kề, giúp không
# mất ý ở ranh giới chunk nhưng vẫn không làm trùng lặp quá nhiều dữ liệu.
CHUNK_OVERLAP = 50
CHUNKING_METHOD = "recursive"

# Dùng cloud embedding qua OpenAI-compatible router để không cần tải model local
# nặng. Model openrouter/openai/text-embedding-3-small có 1536 dimensions,
# chi phí thấp và chất lượng đủ tốt cho semantic search. Cần API key trong .env
# khi chạy embed_chunks().
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "openrouter/openai/text-embedding-3-small")
EMBEDDING_DIM = 1536

# Lưu local JSON trước để dễ làm Task 5 semantic_search mà chưa cần setup
# Weaviate/Docker. Có thể đổi sang Weaviate sau nếu muốn dùng hybrid built-in.
VECTOR_STORE = "local_json"


# =============================================================================
# IMPLEMENTATION
# =============================================================================

def load_documents() -> list[dict]:
    """
    Đọc toàn bộ markdown files từ data/standardized/.

    Returns:
        List of {'content': str, 'metadata': {'source': str, 'type': str}}
    """
    documents = []

    for md_file in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8").strip()
        if not content:
            continue

        relative_path = md_file.relative_to(PROJECT_DIR)
        parent_names = {part.lower() for part in md_file.parts}
        if "legal" in parent_names:
            doc_type = "legal"
        elif "news" in parent_names:
            doc_type = "news"
        else:
            doc_type = "unknown"

        documents.append({
            "content": content,
            "metadata": {
                "source": md_file.name,
                "path": str(relative_path).replace("\\", "/"),
                "type": doc_type,
            },
        })

    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """
    Chunk documents bằng RecursiveCharacterTextSplitter.

    Returns:
        List of {'content': str, 'metadata': dict} — mỗi item là 1 chunk
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks = []
    for doc_index, doc in enumerate(documents):
        splits = splitter.split_text(doc["content"])
        for chunk_index, chunk_text in enumerate(splits):
            chunk_text = chunk_text.strip()
            if not chunk_text:
                continue

            chunks.append({
                "content": chunk_text,
                "metadata": {
                    **doc.get("metadata", {}),
                    "doc_index": doc_index,
                    "chunk_index": chunk_index,
                },
            })

    return chunks


def _get_embedding_api_config() -> tuple[str, str]:
    """Chọn embedding API config theo thứ tự: 9router → OpenRouter → OpenAI."""
    if os.getenv("NINEROUTER_API_KEY"):
        return os.getenv("NINEROUTER_API_KEY"), os.getenv("EMBEDDING_BASE_URL", "https://api.9router.com/v1")
    if os.getenv("OPENROUTER_API_KEY"):
        return os.getenv("OPENROUTER_API_KEY"), os.getenv("EMBEDDING_BASE_URL", "https://openrouter.ai/api/v1")
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENAI_API_KEY"), os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1")
    raise RuntimeError(
        "Thiếu API key trong .env. Hãy thêm NINEROUTER_API_KEY, "
        "OPENROUTER_API_KEY hoặc OPENAI_API_KEY rồi chạy lại Task 4 để tạo embeddings."
    )


def _embed_with_openai(texts: list[str]) -> list[list[float]]:
    """Embed texts bằng OpenAI-compatible cloud embedding API."""
    api_key, base_url = _get_embedding_api_config()

    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=5.0)
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def embed_texts_locally(texts: list[str]) -> list[list[float]]:
    """
    Tạo hashing embeddings local, deterministic, không cần API.

    Đây là fallback khi cloud embedding bị chặn hoặc thiếu key. Vector vẫn được
    lưu trong local JSON và Task 5 vẫn dùng cosine similarity để search.
    """
    return [_hashing_embedding(text) for text in texts]


def _hashing_embedding(text: str, dim: int = 384) -> list[float]:
    tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
    vector = [0.0] * dim
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign

    norm = sum(value * value for value in vector) ** 0.5
    if norm:
        vector = [value / norm for value in vector]
    return vector


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Embed toàn bộ chunks bằng model đã chọn.

    Returns:
        Mỗi chunk dict được thêm key 'embedding': list[float]
    """
    if not chunks:
        return []

    texts = [chunk["content"] for chunk in chunks]
    embedded_chunks = []

    # Chia batch nhỏ để tránh request quá lớn và dễ retry nếu cần.
    batch_size = 64
    for start in range(0, len(texts), batch_size):
        end = start + batch_size
        batch_texts = texts[start:end]
        try:
            batch_embeddings = _embed_with_openai(batch_texts)
            embedding_source = "cloud"
        except Exception as exc:
            print(f"  ⚠ Cloud embedding failed ({exc}). Falling back to local hashing embeddings.")
            batch_embeddings = embed_texts_locally(batch_texts)
            embedding_source = "local_hashing"

        for chunk, embedding in zip(chunks[start:end], batch_embeddings):
            embedded_chunks.append({
                **chunk,
                "embedding": embedding,
                "embedding_source": embedding_source,
            })

        print(f"  Embedded {min(end, len(texts))}/{len(texts)} chunks")

    return embedded_chunks


def index_to_vectorstore(chunks: list[dict]):
    """
    Lưu chunks + embeddings vào local JSON vector store.

    File này sẽ được dùng tiếp ở Task 5 để semantic_search bằng cosine similarity.
    """
    VECTORSTORE_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_INDEX_PATH.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✓ Saved local vector index: {LOCAL_INDEX_PATH}")


def run_pipeline():
    """Chạy toàn bộ pipeline: load → chunk → embed → index."""
    print("=" * 50)
    print("Task 4: Chunking & Indexing")
    print(f"  Chunking: {CHUNKING_METHOD} (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    print(f"  Embedding: {EMBEDDING_MODEL} (dim={EMBEDDING_DIM})")
    print(f"  Vector Store: {VECTOR_STORE}")
    print("=" * 50)

    docs = load_documents()
    print(f"\n✓ Loaded {len(docs)} documents")

    chunks = chunk_documents(docs)
    print(f"✓ Created {len(chunks)} chunks")

    chunks = embed_chunks(chunks)
    print(f"✓ Embedded {len(chunks)} chunks")

    index_to_vectorstore(chunks)
    print("✓ Indexed to vector store")


if __name__ == "__main__":
    run_pipeline()
