"""
RAG Evaluation Pipeline.

Local, deterministic evaluator for the group RAG pipeline. It avoids external LLM
judge dependencies so the report can be reproduced during demo/grading.

Metrics implemented:
    - Faithfulness: answer tokens grounded in retrieved contexts + citation bonus
    - Answer Relevance: overlap between question/expected answer and actual answer
    - Context Recall: expected keywords/context covered by retrieved contexts
    - Context Precision: fraction of retrieved chunks containing expected evidence

A/B comparison:
    - Config A: hybrid retrieval + reranking
    - Config B: hybrid retrieval without reranking
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.task9_retrieval_pipeline import retrieve

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"
RESULTS_PATH = Path(__file__).parent / "results.md"
TOKEN_RE = re.compile(r"\w+", re.UNICODE)


@dataclass
class EvalCaseResult:
    id: str
    category: str
    question: str
    answer: str
    faithfulness: float
    answer_relevance: float
    context_recall: float
    context_precision: float
    average: float
    retrieval_source: str
    source_count: int
    failure_stage: str
    root_cause: str


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def token_set(text: str) -> set[str]:
    return set(tokenize(text))


def load_golden_dataset() -> list[dict]:
    """Load golden dataset từ JSON file."""
    with open(GOLDEN_DATASET_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def make_extractive_answer(chunks: list[dict], max_chunks: int = 3) -> str:
    """Create a deterministic cited answer from retrieved chunks for evaluation."""
    if not chunks:
        return "Tôi chưa tìm thấy đủ thông tin trong nguồn hiện có."

    parts = []
    for index, chunk in enumerate(chunks[:max_chunks], 1):
        metadata = chunk.get("metadata", {})
        source = metadata.get("source") or metadata.get("path") or f"Source {index}"
        snippet = " ".join(chunk.get("content", "").split())[:300]
        parts.append(f"{snippet} [{source}]")
    return "\n".join(parts)


def joined_context(chunks: list[dict]) -> str:
    return "\n".join(chunk.get("content", "") for chunk in chunks)


def expected_terms(item: dict) -> list[str]:
    terms = []
    terms.extend(item.get("expected_keywords", []))
    context = item.get("expected_context", [])
    if isinstance(context, str):
        terms.append(context)
    else:
        terms.extend(context)
    return [term.lower() for term in terms if term]


def phrase_coverage(terms: list[str], text: str) -> float:
    if not terms:
        return 0.0
    normalized = text.lower()
    hits = 0
    for term in terms:
        term_tokens = token_set(term)
        if term in normalized or (term_tokens and len(term_tokens & token_set(text)) / len(term_tokens) >= 0.6):
            hits += 1
    return hits / len(terms)


def context_recall(item: dict, chunks: list[dict]) -> float:
    return phrase_coverage(expected_terms(item), joined_context(chunks))


def context_precision(item: dict, chunks: list[dict]) -> float:
    if not chunks:
        return 0.0
    terms = expected_terms(item)
    relevant = sum(1 for chunk in chunks if phrase_coverage(terms, chunk.get("content", "")) > 0)
    return relevant / len(chunks)


def answer_relevance(item: dict, answer: str) -> float:
    expected = token_set(item.get("expected_answer", ""))
    question = token_set(item.get("question", ""))
    answer_tokens = token_set(answer)
    target = expected | question
    if not target or not answer_tokens:
        return 0.0
    return min(1.0, len(target & answer_tokens) / max(1, len(target) * 0.45))


def faithfulness(answer: str, chunks: list[dict]) -> float:
    context_tokens = token_set(joined_context(chunks))
    answer_tokens = token_set(answer)
    content_tokens = {token for token in answer_tokens if len(token) > 2}
    if not content_tokens:
        return 0.0

    grounded = len(content_tokens & context_tokens) / len(content_tokens)
    citation_bonus = 0.15 if "[" in answer and "]" in answer else 0.0
    return min(1.0, grounded + citation_bonus)


def diagnose(result: EvalCaseResult) -> tuple[str, str]:
    scores = {
        "retrieval": min(result.context_recall, result.context_precision),
        "generation": min(result.faithfulness, result.answer_relevance),
    }
    if result.source_count == 0:
        return "retrieval", "No source chunks were retrieved."
    if scores["retrieval"] < 0.4:
        return "retrieval", "Retrieved chunks did not cover enough expected evidence."
    if result.faithfulness < 0.5:
        return "generation", "Answer used terms not well grounded in retrieved contexts."
    if result.answer_relevance < 0.5:
        return "generation", "Answer did not match the expected answer/question keywords closely enough."
    return "none", "Acceptable result."


def evaluate_config(name: str, dataset: list[dict], retriever: Callable[[str], list[dict]]) -> dict:
    case_results: list[EvalCaseResult] = []

    for item in dataset:
        chunks = retriever(item["question"])
        answer = make_extractive_answer(chunks)
        faith = faithfulness(answer, chunks)
        relevance = answer_relevance(item, answer)
        recall = context_recall(item, chunks)
        precision = context_precision(item, chunks)
        avg = statistics.mean([faith, relevance, recall, precision])
        retrieval_source = chunks[0].get("source", "none") if chunks else "none"

        result = EvalCaseResult(
            id=item.get("id", ""),
            category=item.get("category", "unknown"),
            question=item["question"],
            answer=answer,
            faithfulness=faith,
            answer_relevance=relevance,
            context_recall=recall,
            context_precision=precision,
            average=avg,
            retrieval_source=retrieval_source,
            source_count=len(chunks),
            failure_stage="",
            root_cause="",
        )
        result.failure_stage, result.root_cause = diagnose(result)
        case_results.append(result)

    summary = {
        "faithfulness": statistics.mean(r.faithfulness for r in case_results),
        "answer_relevance": statistics.mean(r.answer_relevance for r in case_results),
        "context_recall": statistics.mean(r.context_recall for r in case_results),
        "context_precision": statistics.mean(r.context_precision for r in case_results),
        "average": statistics.mean(r.average for r in case_results),
    }

    return {"name": name, "summary": summary, "cases": case_results}


def compare_configs(golden_dataset: list[dict]) -> dict:
    """So sánh A/B giữa hybrid+rering và hybrid không rerank."""
    configs = {
        "Config A — Hybrid + Reranking": lambda q: retrieve(q, top_k=5, use_reranking=True),
        "Config B — Hybrid without Reranking": lambda q: retrieve(q, top_k=5, use_reranking=False),
    }
    return {name: evaluate_config(name, golden_dataset, fn) for name, fn in configs.items()}


def fmt(value: float) -> str:
    return f"{value:.3f}"


def export_results(comparison: dict):
    """Export evaluation results to results.md."""
    config_names = list(comparison.keys())
    a = comparison[config_names[0]]["summary"]
    b = comparison[config_names[1]]["summary"]

    rows = [
        ("Faithfulness", a["faithfulness"], b["faithfulness"]),
        ("Answer Relevance", a["answer_relevance"], b["answer_relevance"]),
        ("Context Recall", a["context_recall"], b["context_recall"]),
        ("Context Precision", a["context_precision"], b["context_precision"]),
        ("Average", a["average"], b["average"]),
    ]

    all_cases = comparison[config_names[0]]["cases"]
    worst = sorted(all_cases, key=lambda r: r.average)[:3]

    content = "# RAG Evaluation Results\n\n"
    content += "## Framework sử dụng\n\n"
    content += "Sử dụng **local deterministic evaluation** để đánh giá RAG mà không cần LLM judge/API. Metrics được tính bằng token/phrase overlap giữa câu trả lời, expected answer và retrieved contexts. Cách này tái lập được khi demo và phù hợp khi API judge không ổn định.\n\n"
    content += "---\n\n"
    content += "## Dataset Summary\n\n"
    content += f"- Tổng số test cases: **{len(all_cases)}**\n"
    categories = sorted({case.category for case in all_cases})
    for category in categories:
        count = sum(1 for case in all_cases if case.category == category)
        content += f"- {category}: **{count}** câu\n"

    content += "\n---\n\n## Overall Scores\n\n"
    content += "| Metric | Config A (hybrid + rerank) | Config B (hybrid no rerank) | Δ |\n"
    content += "|--------|-----------------------------|------------------------------|---|\n"
    for metric, score_a, score_b in rows:
        content += f"| {metric} | {fmt(score_a)} | {fmt(score_b)} | {fmt(score_a - score_b)} |\n"

    winner = "Config A" if a["average"] >= b["average"] else "Config B"
    content += "\n---\n\n## A/B Comparison Analysis\n\n"
    content += "**Config A:** Hybrid retrieval gồm semantic search + BM25, gộp bằng RRF và reranking lại candidates trước khi trả kết quả.\n\n"
    content += "**Config B:** Hybrid retrieval gồm semantic search + BM25, gộp bằng RRF nhưng không chạy bước reranking cuối.\n\n"
    content += f"**Kết luận:** {winner} có average score cao hơn trong bộ golden dataset hiện tại. Nếu Config A tốt hơn, reranking giúp ưu tiên chunks khớp trực tiếp với query; nếu Config B tốt hơn, RRF ban đầu đã đủ ổn và reranking offline có thể làm giảm đa dạng kết quả.\n\n"

    content += "---\n\n## Worst Performers (Bottom 3 — Config A)\n\n"
    content += "| # | Question | Faithfulness | Relevance | Recall | Precision | Failure Stage | Root Cause |\n"
    content += "|---|----------|--------------|-----------|--------|-----------|---------------|------------|\n"
    for index, case in enumerate(worst, 1):
        question = case.question.replace("|", " ")
        content += (
            f"| {index} | {question} | {fmt(case.faithfulness)} | {fmt(case.answer_relevance)} | "
            f"{fmt(case.context_recall)} | {fmt(case.context_precision)} | {case.failure_stage} | {case.root_cause} |\n"
        )

    content += "\n---\n\n## Recommendations\n\n"
    content += "### Cải tiến 1 — Thêm dữ liệu legal/news chất lượng hơn\n"
    content += "**Action:** Bổ sung thêm văn bản luật theo từng điều và bài báo có metadata sạch.  \n"
    content += "**Expected impact:** Tăng context recall và giúp chatbot trích nguồn chính xác hơn.\n\n"
    content += "### Cải tiến 2 — Dùng vector database thật khi dữ liệu lớn\n"
    content += "**Action:** Thay local JSON vector store bằng Weaviate/Chroma/FAISS khi corpus mở rộng.  \n"
    content += "**Expected impact:** Search nhanh hơn, hỗ trợ metadata filtering và hybrid retrieval tốt hơn.\n\n"
    content += "### Cải tiến 3 — Dùng LLM-as-a-judge hoặc RAGAS/DeepEval khi có API ổn định\n"
    content += "**Action:** Thay local overlap metrics bằng FaithfulnessMetric/AnswerRelevancyMetric của DeepEval hoặc RAGAS.  \n"
    content += "**Expected impact:** Đánh giá được ngữ nghĩa sâu hơn, đặc biệt cho faithfulness và answer relevance.\n\n"

    content += "---\n\n## How to Reproduce\n\n"
    content += "```powershell\n"
    content += ".\\.venv\\Scripts\\python.exe group_project\\evaluation\\eval_pipeline.py\n"
    content += "```\n"

    RESULTS_PATH.write_text(content, encoding="utf-8")


def main():
    golden_dataset = load_golden_dataset()
    print(f"Loaded {len(golden_dataset)} test cases")
    comparison = compare_configs(golden_dataset)
    export_results(comparison)

    for name, result in comparison.items():
        print(f"\n{name}")
        for metric, score in result["summary"].items():
            print(f"  {metric}: {score:.3f}")
    print(f"\n[OK] Wrote report: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
