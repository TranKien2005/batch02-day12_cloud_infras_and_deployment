"""
Task 10 — Generation Có Citation.

Uses retrieval from Task 9, reorders context to reduce lost-in-the-middle, and
returns a Vietnamese answer with citations. If no generation API key is present,
it falls back to an extractive cited answer so tests and demos still run offline.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from .task9_retrieval_pipeline import retrieve


TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.3

# User-selected generation model via OpenAI-compatible router. The model can be
# overridden in .env with GENERATION_MODEL. If no key is present, generation uses
# a local extractive fallback with citations.
GENERATION_MODEL = os.getenv("GENERATION_MODEL", "groq/llama-3.3-70b-versatile")
GENERATION_BASE_URL = os.getenv("GENERATION_BASE_URL", "https://api.9router.com/v1")


SYSTEM_PROMPT = """Bạn là chatbot RAG tiếng Việt về pháp luật ma túy và tin tức liên quan.
Trả lời tự nhiên, ngắn gọn vừa đủ, không quá cứng nhắc.

Quy tắc bắt buộc:
- Chỉ dùng thông tin trong Context để trả lời các câu hỏi kiến thức/pháp luật/tin tức.
- Mỗi ý quan trọng phải có citation trong ngoặc vuông, ví dụ [Luật-73-2021-QH14].
- Nếu Context không đủ bằng chứng, nói rõ: "Tôi chưa tìm thấy đủ thông tin trong nguồn hiện có".
- Với lời chào/xã giao, hãy chào lại thân thiện và gợi ý người dùng hỏi về pháp luật ma túy hoặc tin tức liên quan; không cần citation.
- Trả lời bằng tiếng Việt."""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Sắp xếp chunks để tránh lost-in-the-middle effect."""
    if len(chunks) <= 2:
        return chunks

    reordered = []
    for i in range(0, len(chunks), 2):
        reordered.append(chunks[i])

    last_even_index = len(chunks) - 1 if (len(chunks) - 1) % 2 == 1 else len(chunks) - 2
    for i in range(last_even_index, 0, -2):
        reordered.append(chunks[i])

    return reordered


def _citation_label(chunk: dict, index: int) -> str:
    metadata = chunk.get("metadata", {})
    source = metadata.get("source") or metadata.get("path") or f"Source {index}"
    return source.replace(".md", "").replace(".html", "").replace(".pdf", "").replace(".docx", "")


def format_context(chunks: list[dict]) -> str:
    """Format chunks thành context string cho prompt, kèm source labels."""
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        source = _citation_label(chunk, i)
        doc_type = metadata.get("type", "unknown")
        context_parts.append(
            f"[Document {i} | Source: {source} | Type: {doc_type}]\n"
            f"{chunk.get('content', '')}\n"
        )
    return "\n---\n".join(context_parts)


def _get_generation_api_key() -> str | None:
    return os.getenv("NINEROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")


def _call_llm(query: str, context: str) -> str | None:
    api_key = _get_generation_api_key()
    if not api_key:
        return None

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=GENERATION_BASE_URL, timeout=10.0)
        user_message = f"Context:\n{context}\n\n---\n\nQuestion: {query}"
        response = client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=TEMPERATURE,
            top_p=TOP_P,
        )
        return response.choices[0].message.content
    except Exception:
        return None


def _is_greeting(query: str) -> bool:
    normalized = query.strip().lower()
    greetings = {"hi", "hello", "hey", "xin chào", "chào", "chao", "alo"}
    return normalized in greetings or normalized.startswith("xin chào")


def _extractive_answer(query: str, chunks: list[dict]) -> str:
    if not chunks:
        return "Tôi chưa tìm thấy đủ thông tin trong nguồn hiện có. Bạn có thể hỏi cụ thể hơn về điều luật, nghị định hoặc sự việc cần tra cứu."

    answer_parts = ["Mình tìm thấy một số thông tin liên quan trong nguồn dữ liệu:"]
    for i, chunk in enumerate(chunks[:3], 1):
        source = _citation_label(chunk, i)
        snippet = " ".join(chunk.get("content", "").split())[:320]
        answer_parts.append(f"- {snippet} [{source}]")
    answer_parts.append("\nBạn có thể hỏi cụ thể hơn, ví dụ: 'Điều luật nào quy định về tàng trữ ma túy?' để mình trả lời sát nguồn hơn.")
    return "\n".join(answer_parts)


def condense_query(query: str, history: list[dict] | None = None) -> str:
    """Nén câu hỏi dựa trên lịch sử trò chuyện để tạo câu hỏi độc lập."""
    if not history:
        return query

    # Lọc ra các tin nhắn hợp lệ
    valid_history = [msg for msg in history if msg.get("role") in ("user", "assistant")]
    if not valid_history:
        return query

    api_key = _get_generation_api_key()
    if not api_key:
        return query

    # Định dạng lịch sử trò chuyện
    history_parts = []
    for msg in valid_history:
        role = "Người dùng" if msg["role"] == "user" else "Chatbot"
        content = msg.get("content", "")
        history_parts.append(f"{role}: {content}")
    chat_history_str = "\n".join(history_parts)

    prompt = (
        "Cho lịch sử cuộc trò chuyện sau và một câu hỏi mới của người dùng, "
        "hãy tạo ra một câu hỏi độc lập (standalone question) bằng tiếng Việt "
        "để thực hiện tìm kiếm tài liệu. Không trả lời câu hỏi, chỉ trả về câu hỏi độc lập duy nhất.\n\n"
        f"Lịch sử cuộc trò chuyện:\n{chat_history_str}\n\n"
        f"Câu hỏi mới: {query}\n"
        "Câu hỏi độc lập:"
    )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=GENERATION_BASE_URL, timeout=5.0)
        response = client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=[
                {"role": "system", "content": "Bạn là trợ lý giúp viết lại câu hỏi độc lập bằng tiếng Việt."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            top_p=0.9,
        )
        condensed = response.choices[0].message.content.strip()
        condensed = condensed.strip("\"'")
        if condensed:
            return condensed
    except Exception:
        pass

    return query


def generate_with_citation(query: str, history: list[dict] | None = None, top_k: int = TOP_K) -> dict:
    """End-to-end RAG generation có citation và conversation memory."""
    if _is_greeting(query):
        return {
            "answer": "Chào bạn! Mình có thể hỗ trợ hỏi đáp về pháp luật ma túy, các văn bản như Luật Phòng chống ma túy, Bộ luật Hình sự, Nghị định 105/2021/NĐ-CP, hoặc các bài báo liên quan. Bạn muốn hỏi nội dung nào?",
            "sources": [],
            "retrieval_source": "none",
        }

    search_query = condense_query(query, history)
    chunks = retrieve(search_query, top_k=top_k)
    reordered = reorder_for_llm(chunks)
    context = format_context(reordered)

    answer = _call_llm(query, context)
    if not answer:
        answer = _extractive_answer(query, reordered)

    return {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": chunks[0].get("source", "hybrid") if chunks else "none",
    }


if __name__ == "__main__":
    test_queries = [
        "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam?",
        "Những nghệ sĩ nào đã bị bắt vì liên quan tới ma tuý?",
        "Quy trình cai nghiện bắt buộc theo Luật Phòng chống ma tuý 2021?",
    ]

    for q in test_queries:
        print(f"\n{'='*70}")
        print(f"Q: {q}")
        print("=" * 70)
        result = generate_with_citation(q)
        print(f"\nA: {result['answer']}")
        print(f"\n[Sources: {len(result['sources'])} chunks | via {result['retrieval_source']}]")
