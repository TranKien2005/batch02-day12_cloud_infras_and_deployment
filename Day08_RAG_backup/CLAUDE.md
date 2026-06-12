# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

This repository is a Python teaching scaffold for Day 8: building an end-to-end RAG pipeline about Vietnamese drug law and news articles about artists related to drugs. The individual work is organized as ten sequential tasks in `src/task1_*.py` through `src/task10_*.py`, and the automated grader in `tests/test_individual.py` checks those task modules and required data artifacts.

The expected pipeline is:

1. collect raw legal documents into `data/landing/legal/`;
2. crawl news articles into `data/landing/news/` with source metadata;
3. convert raw files to Markdown under `data/standardized/` while preserving `legal/` and `news/` subfolders;
4. chunk Markdown, embed chunks, and index them into a vector store;
5. implement dense semantic search;
6. implement BM25 lexical search;
7. rerank or fuse retrieval candidates;
8. implement PageIndex vectorless fallback search;
9. combine semantic + lexical + reranking + fallback into `retrieve()`;
10. generate Vietnamese answers with citations and source chunks.

Most source files are starter templates with `TODO` blocks and `NotImplementedError`; future work should replace those with concrete implementations while keeping the public function names and return shapes expected by the tests.

## Setup and common commands

Use PowerShell on Windows from the repository root.

```powershell
# Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Create local environment file, then fill in API keys as needed
Copy-Item .env.example .env
```

Common test commands:

```powershell
# Run the full individual grading suite
pytest tests/ -v

# Run the single test module
pytest tests/test_individual.py -v

# Run one task's tests
pytest tests/test_individual.py::TestTask1 -v
pytest tests/test_individual.py::TestTask5 -v

# Run one specific test method
pytest tests/test_individual.py::TestTask10::test_format_context_includes_source -v
```

Task scripts can also be run directly while developing:

```powershell
python src/task1_collect_legal_docs.py
python src/task2_crawl_news.py
python src/task3_convert_markdown.py
python src/task4_chunking_indexing.py
python src/task9_retrieval_pipeline.py
python src/task10_generation.py
```

Group demo commands from the README, if an app is added later:

```powershell
streamlit run app.py
# or
chainlit run app.py
```

There is no dedicated lint, type-check, package build, or app entrypoint configured in the repository at the time this file was created.

## Environment variables

`.env.example` documents optional service keys used by the scaffold:

- `OPENAI_API_KEY`: Task 10 generation example.
- `JINA_API_KEY`: optional Task 7 reranking via Jina API.
- `PAGEINDEX_API_KEY`: Task 8 PageIndex vectorless RAG.
- `WEAVIATE_URL` and `WEAVIATE_API_KEY`: optional Weaviate Cloud for Task 4 indexing; local Docker Weaviate is also suggested in the README.

## Architecture notes

- `data/landing/` is the raw ingestion layer. The tests expect at least three non-empty PDF/DOC/DOCX legal files in `data/landing/legal/` and at least five non-empty article files in `data/landing/news/`.
- `data/standardized/` is the normalized Markdown layer consumed by indexing and search. Task 3 should preserve the source category by writing to `data/standardized/legal/` and `data/standardized/news/`.
- `src/task4_chunking_indexing.py` defines shared indexing configuration (`CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHUNKING_METHOD`, `EMBEDDING_MODEL`, `VECTOR_STORE`) plus `load_documents()`, `chunk_documents()`, `embed_chunks()`, and `index_to_vectorstore()`. Downstream retrieval modules should stay compatible with the chunk format `{'content': str, 'metadata': dict}`.
- `src/task5_semantic_search.py` and `src/task6_lexical_search.py` are independent retrieval modules. Both are expected to return a list of dictionaries with `content`, `score`, and metadata, sorted by descending score and respecting `top_k`.
- `src/task7_reranking.py` is both a reranking module and the intended place for RRF fusion. `src/task9_retrieval_pipeline.py` imports `rerank()` and `rerank_rrf()` from it, so keep those interfaces stable.
- `src/task8_pageindex_vectorless.py` provides the fallback retrieval path. Its results should include `source: 'pageindex'`.
- `src/task9_retrieval_pipeline.py` is the orchestration point for retrieval. Its `retrieve()` should merge semantic and lexical results, optionally rerank, mark hybrid results with `source: 'hybrid'`, and fallback to PageIndex when no result clears the score threshold.
- `src/task10_generation.py` depends on `retrieve()` and is responsible for lost-in-the-middle reordering, formatting citations from chunk metadata, calling the chosen LLM, and returning `{'answer': str, 'sources': list, 'retrieval_source': str}`.
- `group_project/evaluation/` contains placeholders for the group RAG evaluation deliverables: `golden_dataset.json`, `eval_pipeline.py`, and `results.md`.

## Assignment requirements to preserve

The README is the source of truth for grading. Key requirements include:

- Individual grading is 50 points and is run with `pytest tests/ -v`.
- Task 1 requires at least 3 legal source files in `data/landing/legal/`.
- Task 2 requires at least 5 news article files in `data/landing/news/`, with metadata such as source URL for JSON outputs.
- Task 4 should document the selected chunking strategy, chunk size, overlap, embedding model, dimensions, and vector store choice in code comments.
- Task 5 and Task 6 must return sorted search results in the expected dictionary format.
- Task 7 may use a cross-encoder, MMR, or RRF; if using alternatives such as RRF/BM25 variants, the mechanism should be explainable for demo/bonus.
- Task 9 must implement hybrid retrieval and PageIndex fallback logic.
- Task 10 must answer with citations in the form `[Nguồn, Năm]` or equivalent source labels and should state that information cannot be verified when the provided context is insufficient.
- Group work is either a RAG chatbot UI or an evaluation pipeline, with the common requirement to integrate individual pipelines, demo locally or deployed, include citation-bearing answers, and document architecture/assignment in `group_project/README.md`.
