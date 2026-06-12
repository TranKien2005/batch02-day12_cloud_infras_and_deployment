# BÃ i Táº­p NhÃ³m â€” Search Engine / RAG Chatbot

## Má»¥c TiÃªu

Sau khi hoÃ n thÃ nh bÃ i cÃ¡ nhÃ¢n, nhÃ³m ngá»“i láº¡i Ä‘á»ƒ xÃ¢y dá»±ng **1 trong 2 sáº£n pháº©m**:

---

## YÃªu cáº§u 1:  Sáº£n pháº©m nhÃ³m RAG Chatbot

XÃ¢y dá»±ng chatbot tráº£ lá»i cÃ¢u há»i vá» phÃ¡p luáº­t ma tuÃ½ vÃ  tin tá»©c liÃªn quan.

**YÃªu cáº§u:**
- Giao diá»‡n chat (Streamlit / Gradio / Chainlit)
- Tráº£ lá»i cÃ³ citation (dá»±a trÃªn Task 10)
- Há»— trá»£ follow-up questions (conversation memory)
- Hiá»ƒn thá»‹ source documents Ä‘Ã£ dÃ¹ng

**Stack gá»£i Ã½:**
```
Chainlit/Streamlit â†’ Retrieval (Task 9) â†’ Generation (Task 10) â†’ Display
```

---

## YÃªu cáº§u 2: RAG Evaluation Pipeline

Sá»­ dá»¥ng **1 trong 3 framework** sau Ä‘á»ƒ evaluate pipeline RAG cá»§a nhÃ³m:

### Framework lá»±a chá»n

| Framework | CÃ i Ä‘áº·t | Äáº·c Ä‘iá»ƒm |
|-----------|---------|-----------|
| [DeepEval](https://github.com/confident-ai/deepeval) | `pip install deepeval` | Nhiá»u metric built-in, dá»… integrate vá»›i pytest |
| [RAGAS](https://github.com/explodinggradients/ragas) | `pip install ragas` | Chuáº©n industry cho RAG eval, 3 trá»¥c chÃ­nh |
| [TruLens](https://github.com/truera/trulens) | `pip install trulens` | Dashboard UI, feedback functions máº¡nh |

### YÃªu cáº§u Evaluation

1. **Táº¡o Golden Dataset** â€” tá»‘i thiá»ƒu 15 cáº·p Q&A (question, expected_answer, expected_context)
2. **Cháº¡y evaluation** trÃªn toÃ n bá»™ golden dataset vá»›i cÃ¡c metrics sau:
   - **Faithfulness** â€” cÃ¢u tráº£ lá»i cÃ³ bÃ¡m Ä‘Ãºng context khÃ´ng?
   - **Answer Relevance** â€” cÃ¢u tráº£ lá»i cÃ³ Ä‘Ãºng cÃ¢u há»i khÃ´ng?
   - **Context Recall** â€” retriever cÃ³ láº¥y Ä‘á»§ evidence khÃ´ng?
   - **Context Precision** â€” trong context láº¥y vá», bao nhiÃªu % thá»±c sá»± há»¯u Ã­ch?
3. **So sÃ¡nh A/B** â€” cháº¡y eval trÃªn Ã­t nháº¥t 2 config khÃ¡c nhau (vÃ­ dá»¥: cÃ³ reranking vs khÃ´ng reranking, hoáº·c hybrid vs dense-only)
4. **BÃ¡o cÃ¡o** â€” báº£ng Ä‘iá»ƒm + phÃ¢n tÃ­ch worst performers + Ä‘á» xuáº¥t cáº£i tiáº¿n

### Code máº«u â€” DeepEval

```python
from deepeval import evaluate
from deepeval.metrics import (
    FaithfulnessMetric,
    AnswerRelevancyMetric,
    ContextualRecallMetric,
    ContextualPrecisionMetric,
)
from deepeval.test_case import LLMTestCase

# Táº¡o test cases tá»« golden dataset
test_cases = []
for item in golden_dataset:
    result = rag_pipeline.generate_with_citation(item["question"])
    test_case = LLMTestCase(
        input=item["question"],
        actual_output=result["answer"],
        expected_output=item["expected_answer"],
        retrieval_context=[c["content"] for c in result["sources"]],
    )
    test_cases.append(test_case)

# Cháº¡y evaluation
metrics = [
    FaithfulnessMetric(threshold=0.7),
    AnswerRelevancyMetric(threshold=0.7),
    ContextualRecallMetric(threshold=0.7),
    ContextualPrecisionMetric(threshold=0.7),
]

results = evaluate(test_cases, metrics)
```

### Code máº«u â€” RAGAS

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_recall,
    context_precision,
)
from datasets import Dataset

# Chuáº©n bá»‹ data
eval_data = {
    "question": [],
    "answer": [],
    "contexts": [],
    "ground_truth": [],
}

for item in golden_dataset:
    result = rag_pipeline.generate_with_citation(item["question"])
    eval_data["question"].append(item["question"])
    eval_data["answer"].append(result["answer"])
    eval_data["contexts"].append([c["content"] for c in result["sources"]])
    eval_data["ground_truth"].append(item["expected_answer"])

dataset = Dataset.from_dict(eval_data)

# Cháº¡y evaluation
result = evaluate(
    dataset,
    metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
)
print(result.to_pandas())
```

### Code máº«u â€” TruLens

```python
from trulens.apps.custom import TruCustomApp, instrument
from trulens.core import Feedback
from trulens.providers.openai import OpenAI as TruOpenAI

provider = TruOpenAI()

# Define feedback functions
f_faithfulness = Feedback(provider.groundedness_measure_with_cot_reasons).on_output()
f_relevance = Feedback(provider.relevance).on_input_output()
f_context_relevance = Feedback(provider.context_relevance).on_input()

# Wrap RAG pipeline
tru_rag = TruCustomApp(
    rag_pipeline,
    app_name="DrugLaw_RAG",
    feedbacks=[f_faithfulness, f_relevance, f_context_relevance],
)

# Run evaluation
with tru_rag as recording:
    for item in golden_dataset:
        rag_pipeline.generate_with_citation(item["question"])

# View dashboard
from trulens.dashboard import run_dashboard
run_dashboard()
```

### Deliverable Evaluation

- [ ] File `group_project/evaluation/golden_dataset.json` â€” 15+ cáº·p Q&A
- [ ] File `group_project/evaluation/eval_pipeline.py` â€” script cháº¡y evaluation
- [ ] File `group_project/evaluation/results.md` â€” báº£ng Ä‘iá»ƒm + phÃ¢n tÃ­ch
- [ ] So sÃ¡nh A/B Ã­t nháº¥t 2 configs

---

## YÃªu Cáº§u Chung

1. **TÃ­ch há»£p pipeline** tá»« bÃ i cÃ¡ nhÃ¢n cá»§a cÃ¡c thÃ nh viÃªn
2. **Demo hoáº¡t Ä‘á»™ng Ä‘Æ°á»£c** trong buá»•i trÃ¬nh bÃ y (cháº¡y local hoáº·c deploy)
3. **Evaluation pipeline** cháº¡y Ä‘Æ°á»£c vÃ  cÃ³ bÃ¡o cÃ¡o káº¿t quáº£
4. **Code push lÃªn repository** chung cá»§a nhÃ³m
5. **README** mÃ´ táº£ kiáº¿n trÃºc vÃ  phÃ¢n cÃ´ng (Ä‘iá»n bÃªn dÆ°á»›i)

---

## Kiáº¿n TrÃºc Há»‡ Thá»‘ng

Sáº£n pháº©m nhÃ³m hiá»‡n dÃ¹ng kiáº¿n trÃºc chatbot RAG vá»›i giao diá»‡n Node.js vÃ  backend Python FastAPI Ä‘á»ƒ tÃ¡i sá»­ dá»¥ng pipeline Ä‘Ã£ lÃ m á»Ÿ bÃ i cÃ¡ nhÃ¢n.

```text
Node.js / React UI (web/)
  â”‚
  â””â”€â”€ POST http://127.0.0.1:8000/chat
        â”‚
        â–¼
Python FastAPI backend (api/main.py)
  â”‚
  â””â”€â”€ src.task10_generation.generate_with_citation()
        â”‚
        â””â”€â”€ src.task9_retrieval_pipeline.retrieve()
              â”œâ”€â”€ semantic_search
              â”œâ”€â”€ lexical_search / BM25
              â”œâ”€â”€ RRF fusion + reranking
              â””â”€â”€ PageIndex-like fallback
```

Ghi chÃº: báº£n demo khÃ´ng yÃªu cáº§u cháº¡y vector database/Docker. Pipeline hiá»‡n dÃ¹ng Markdown chunks local vÃ  cÃ³ thá»ƒ dÃ¹ng local JSON embedding index náº¿u Ä‘Ã£ táº¡o. CÃ³ thá»ƒ nÃ¢ng cáº¥p sang Weaviate báº±ng Docker sau náº¿u cáº§n hybrid vector database tháº­t.

---

## PhÃ¢n CÃ´ng CÃ´ng Viá»‡c

| ThÃ nh viÃªn | MSSV | Nhiá»‡m vá»¥ | Tráº¡ng thÃ¡i |
|-----------|------|----------|------------|
| | | | |
| | | | |
| | | | |
| | | | |

---

## HÆ°á»›ng Dáº«n Cháº¡y

### 1. CÃ i Ä‘áº·t backend Python

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Táº¡o `.env` tá»« `.env.example` náº¿u muá»‘n dÃ¹ng API generation tháº­t. Náº¿u khÃ´ng cÃ³ API key, chatbot váº«n tráº£ lá»i báº±ng fallback extractive cÃ³ citation.

### 2. Cháº¡y RAG API backend

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

Kiá»ƒm tra backend:

```powershell
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health"
```

### 3. Cháº¡y giao diá»‡n Node.js

```powershell
cd web
npm install
npm run dev
```

Má»Ÿ URL Vite hiá»ƒn thá»‹ trong terminal, thÆ°á»ng lÃ  `http://127.0.0.1:5173`.

### 4. CÃ¢u há»i demo gá»£i Ã½

- `HÃ¬nh pháº¡t cho tá»™i tÃ ng trá»¯ trÃ¡i phÃ©p cháº¥t ma tÃºy lÃ  gÃ¬?`
- `Luáº­t phÃ²ng chá»‘ng ma tÃºy quy Ä‘á»‹nh gÃ¬ vá» cai nghiá»‡n?`
- `CÃ¡c bÃ i bÃ¡o nÃ³i gÃ¬ vá» nghá»‡ sÄ© liÃªn quan Ä‘áº¿n ma tÃºy?`

### 5. Kiá»ƒm tra test cÃ¡ nhÃ¢n khÃ´ng regression

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

### 6. Cháº¡y vÃ  kiá»ƒm tra Evaluation Pipeline

Äá»ƒ Ä‘Ã¡nh giÃ¡ cháº¥t lÆ°á»£ng há»‡ thá»‘ng RAG vÃ  so sÃ¡nh A/B giá»¯a 2 cáº¥u hÃ¬nh (Config A: CÃ³ Reranking vs Config B: KhÃ´ng Reranking), cháº¡y script sau:

```powershell
.\.venv\Scripts\python.exe group_project/evaluation/eval_pipeline.py
```

Káº¿t quáº£ Ä‘Ã¡nh giÃ¡ chi tiáº¿t cho 15 cÃ¢u há»i trong Golden Dataset vÃ  phÃ¢n tÃ­ch so sÃ¡nh A/B sáº½ tá»± Ä‘á»™ng Ä‘Æ°á»£c ghi Ä‘Ã¨/cáº­p nháº­t vÃ o file [results.md](file:///d:/My%20Works/Coding/Practice/Day08_RAG_pipeline_cohort2/group_project/evaluation/results.md).

CÃ¡c metric Ä‘Ã¡nh giÃ¡ bao gá»“m:
- **Faithfulness (Äá»™ trung thá»±c):** ÄÃ¡nh giÃ¡ xem cÃ¢u tráº£ lá»i cÃ³ hoÃ n toÃ n dá»±a trÃªn vÃ  Ä‘Æ°á»£c cá»§ng cá»‘ bá»Ÿi ngá»¯ cáº£nh tÃ¬m Ä‘Æ°á»£c hay khÃ´ng.
- **Answer Relevance (Äá»™ liÃªn quan):** ÄÃ¡nh giÃ¡ xem cÃ¢u tráº£ lá»i cÃ³ khá»›p cháº·t cháº½ vá»›i cÃ¢u há»i vÃ  dá»± kiáº¿n tráº£ lá»i (expected answer) hay khÃ´ng.
- **Context Recall (Äá»™ phá»§ ngá»¯ cáº£nh):** ÄÃ¡nh giÃ¡ xem retriever cÃ³ láº¥y Ä‘á»§ cÃ¡c báº±ng chá»©ng/ngá»¯ cáº£nh cáº§n thiáº¿t hay khÃ´ng.
- **Context Precision (Äá»™ chÃ­nh xÃ¡c ngá»¯ cáº£nh):** ÄÃ¡nh giÃ¡ tá»· lá»‡ cÃ¡c chunk tÃ i liá»‡u tÃ¬m Ä‘Æ°á»£c thá»±c sá»± cÃ³ Ã­ch cho cÃ¢u há»i.

---

## LÆ°u Ã½: HÃ£y giá»¯ láº¡i repo nÃ y náº¿u nhÆ° báº¡n há»c track 3 giai Ä‘oáº¡n 2, chÃºng ta sáº½ phÃ¡t triá»ƒn tiáº¿p dá»± Ã¡n lÃªn knowledge graph Ä‘á»ƒ kháº¯c phá»¥c cÃ¡c cÃ¢u há»i hÃ³c bÃºa khi cÃ³ cÃ¡c cÃ¢u há»i khÃ³.

---

## NÃ¢ng Cáº¥p Multi-Agent: LangGraph + MCP + A2A

Báº£n hiá»‡n táº¡i Ä‘Ã£ Ä‘Æ°á»£c nÃ¢ng tá»« chatbot RAG Ä‘Æ¡n sang kiáº¿n trÃºc Ä‘a tÃ¡c tá»­ trong `api/multi_agent.py`.

```text
React UI
  |
  | POST /chat
  v
FastAPI api/main.py
  |
  v
LangGraph StateGraph
  |-- Router Agent: phÃ¢n loáº¡i cÃ¢u há»i legal / news / general
  |-- Retrieval MCP Agent: gá»i tool local `rag.generate_with_citation`
  |-- Law Agent / News Agent / General Agent: rÃ  soÃ¡t theo intent
  |-- Citation Guard: kiá»ƒm tra cÃ¢u tráº£ lá»i cÃ³ citation khi cÃ³ nguá»“n
  v
Response: answer + sources + agent trace + MCP tools + A2A handoff messages
```

### MCP trong báº£n demo

Repo dÃ¹ng adapter MCP ná»™i bá»™ `LocalMCPToolbox` Ä‘á»ƒ trÃ¡nh phá»¥ thuá»™c server ngoÃ i khi demo. Tool chÃ­nh lÃ  `rag.generate_with_citation`, tÃ¡i sá»­ dá»¥ng pipeline Task 10 vÃ  tráº£ vá» answer, sources, retrieval_source.

### A2A trong báº£n demo

Má»—i láº§n chuyá»ƒn viá»‡c giá»¯a agent Ä‘Æ°á»£c Ä‘Ã³ng gÃ³i báº±ng envelope `a2a.local/v1`, gá»“m sender, receiver, task, payload vÃ  timestamp. Frontend hiá»ƒn thá»‹ cÃ¡c handoff nÃ y trong panel â€œA2A Messagesâ€.

### Giao diá»‡n má»›i

`web/src/App.jsx` vÃ  `web/src/styles.css` Ä‘Ã£ Ä‘Æ°á»£c lÃ m láº¡i theo dáº¡ng dashboard:
- Khu vá»±c chat chÃ­nh hiá»ƒn thá»‹ cÃ¢u tráº£ lá»i, intent, runtime, tráº¡ng thÃ¡i citation vÃ  nguá»“n.
- Sidebar hiá»ƒn thá»‹ Agent Flow, MCP Tools vÃ  A2A Messages.
- ToÃ n bá»™ text tiáº¿ng Viá»‡t trong UI Ä‘Ã£ Ä‘Æ°á»£c sá»­a lá»—i encoding.

### A2A Supervisor Pattern

A2A hiện dùng mẫu Supervisor thay vì worker gọi trực tiếp worker khác:

```text
UserProxy -> Supervisor
Supervisor -> Router -> Supervisor
Supervisor -> Retrieval MCP -> Supervisor
Supervisor -> Specialist Agent -> Supervisor
Supervisor -> Citation Guard -> Supervisor
Supervisor -> UserProxy
```

Trong payload trả về UI, mỗi message có `protocol = a2a.supervisor.local/v1`, `message_type` (`request`, `delegate`, `result`, `control`, `response`), `sender`, `receiver`, `task` và `payload`. Điều này giúp phần demo thể hiện rõ Supervisor là agent điều phối trung tâm.
