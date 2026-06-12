"""FastAPI backend for the group multi-agent RAG chatbot."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.multi_agent import run_multi_agent_chat


class ChatMessage(BaseModel):
    """Message structure for history."""

    role: str = Field(..., description="Role of message author (user or assistant)")
    content: str = Field(..., description="Text content of the message")


class ChatRequest(BaseModel):
    """Request body for chatbot questions."""

    message: str = Field(..., min_length=1, description="User question")
    history: list[ChatMessage] = Field(default_factory=list, description="Conversation history")
    top_k: int = Field(default=5, ge=1, le=10, description="Number of context chunks to retrieve")


class SourceChunk(BaseModel):
    """Sanitized source chunk returned to the web UI."""

    content: str
    score: float | None = None
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTraceItem(BaseModel):
    """One visible step in the multi-agent workflow."""

    name: str
    role: str
    status: str
    detail: str


class ChatResponse(BaseModel):
    """Response body for chatbot answers."""

    answer: str
    retrieval_source: str
    sources: list[SourceChunk]
    intent: str
    citations_ok: bool
    graph_runtime: str
    trace: list[AgentTraceItem]
    a2a_messages: list[dict[str, Any]]
    mcp_tools: list[dict[str, Any]]


app = FastAPI(
    title="Drug Law Multi-Agent RAG API",
    description="LangGraph + MCP-style tools + A2A trace wrapper around the Day 8 RAG pipeline.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        *[f"http://localhost:{port}" for port in range(5173, 5181)],
        *[f"http://127.0.0.1:{port}" for port in range(5173, 5181)],
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _sanitize_sources(sources: list[dict], max_chars: int = 700) -> list[SourceChunk]:
    """Limit source payload size for browser rendering."""
    sanitized = []
    for item in sources:
        content = " ".join(str(item.get("content", "")).split())
        if len(content) > max_chars:
            content = content[:max_chars].rstrip() + "..."

        score = item.get("score")
        sanitized.append(
            SourceChunk(
                content=content,
                score=float(score) if score is not None else None,
                source=item.get("source"),
                metadata=item.get("metadata", {}) or {},
            )
        )
    return sanitized


@app.get("/health")
def health() -> dict[str, str]:
    """Simple readiness endpoint for the Node.js UI."""
    return {"status": "ok", "architecture": "langgraph+mcp+a2a", "version": "2.0.0"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    """Run one multi-agent RAG turn for a user message."""
    try:
        history_list = [{"role": msg.role, "content": msg.content} for msg in request.history]
        result = run_multi_agent_chat(request.message, history=history_list, top_k=request.top_k)
    except Exception as exc:  # Keep API errors readable for the UI.
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ChatResponse(
        answer=result.get("answer", ""),
        retrieval_source=result.get("retrieval_source", "none"),
        sources=_sanitize_sources(result.get("sources", [])),
        intent=result.get("intent", "general"),
        citations_ok=bool(result.get("citations_ok", False)),
        graph_runtime=result.get("graph_runtime", "unknown"),
        trace=result.get("trace", []),
        a2a_messages=result.get("a2a_messages", []),
        mcp_tools=result.get("mcp_tools", []),
    )
