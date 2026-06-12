# RAG Evaluation Results

## Framework sử dụng

Sử dụng **local deterministic evaluation** để đánh giá RAG mà không cần LLM judge/API. Metrics được tính bằng token/phrase overlap giữa câu trả lời, expected answer và retrieved contexts. Cách này tái lập được khi demo và phù hợp khi API judge không ổn định.

---

## Dataset Summary

- Tổng số test cases: **15**
- legal: **8** câu
- mixed: **2** câu
- news: **5** câu

---

## Overall Scores

| Metric | Config A (hybrid + rerank) | Config B (hybrid no rerank) | Δ |
|--------|-----------------------------|------------------------------|---|
| Faithfulness | 1.000 | 1.000 | 0.000 |
| Answer Relevance | 0.992 | 0.992 | -0.000 |
| Context Recall | 0.868 | 0.837 | 0.031 |
| Context Precision | 0.960 | 0.947 | 0.013 |
| Average | 0.955 | 0.944 | 0.011 |

---

## A/B Comparison Analysis

**Config A:** Hybrid retrieval gồm semantic search + BM25, gộp bằng RRF và reranking lại candidates trước khi trả kết quả.

**Config B:** Hybrid retrieval gồm semantic search + BM25, gộp bằng RRF nhưng không chạy bước reranking cuối.

**Kết luận:** Config A có average score cao hơn trong bộ golden dataset hiện tại. Nếu Config A tốt hơn, reranking giúp ưu tiên chunks khớp trực tiếp với query; nếu Config B tốt hơn, RRF ban đầu đã đủ ổn và reranking offline có thể làm giảm đa dạng kết quả.

---

## Worst Performers (Bottom 3 — Config A)

| # | Question | Faithfulness | Relevance | Recall | Precision | Failure Stage | Root Cause |
|---|----------|--------------|-----------|--------|-----------|---------------|------------|
| 1 | Vì sao câu trả lời RAG về ma túy cần citation? | 1.000 | 1.000 | 0.556 | 0.800 | none | Acceptable result. |
| 2 | Bộ luật Hình sự quy định xử lý hành vi liên quan đến ma túy ở nhóm tội nào? | 1.000 | 1.000 | 0.667 | 1.000 | none | Acceptable result. |
| 3 | Tệ nạn ma túy được hiểu như thế nào? | 1.000 | 1.000 | 0.875 | 0.800 | none | Acceptable result. |

---

## Recommendations

### Cải tiến 1 — Thêm dữ liệu legal/news chất lượng hơn
**Action:** Bổ sung thêm văn bản luật theo từng điều và bài báo có metadata sạch.  
**Expected impact:** Tăng context recall và giúp chatbot trích nguồn chính xác hơn.

### Cải tiến 2 — Dùng vector database thật khi dữ liệu lớn
**Action:** Thay local JSON vector store bằng Weaviate/Chroma/FAISS khi corpus mở rộng.  
**Expected impact:** Search nhanh hơn, hỗ trợ metadata filtering và hybrid retrieval tốt hơn.

### Cải tiến 3 — Dùng LLM-as-a-judge hoặc RAGAS/DeepEval khi có API ổn định
**Action:** Thay local overlap metrics bằng FaithfulnessMetric/AnswerRelevancyMetric của DeepEval hoặc RAGAS.  
**Expected impact:** Đánh giá được ngữ nghĩa sâu hơn, đặc biệt cho faithfulness và answer relevance.

---

## How to Reproduce

```powershell
.\.venv\Scripts\python.exe group_project\evaluation\eval_pipeline.py
```
