"""LangGraph multi-agent orchestration for the group RAG chatbot.

This module uses a Supervisor pattern for A2A:
UserProxy -> Supervisor -> worker agents -> Supervisor -> UserProxy.
The existing RAG pipeline remains the MCP-style tool implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from src.task10_generation import generate_with_citation


Intent = Literal["legal", "news", "general"]


class AgentTrace(TypedDict):
    name: str
    role: str
    status: str
    detail: str


class MultiAgentState(TypedDict, total=False):
    query: str
    history: list[dict[str, str]]
    top_k: int
    intent: Intent
    next_agent: str
    supervisor_plan: list[str]
    retrieval_result: dict[str, Any]
    answer: str
    retrieval_source: str
    sources: list[dict[str, Any]]
    citations_ok: bool
    trace: list[AgentTrace]
    a2a_messages: list[dict[str, Any]]
    mcp_tools: list[dict[str, Any]]


@dataclass(frozen=True)
class A2AEnvelope:
    """Agent-to-Agent message envelope routed through the supervisor."""

    sender: str
    receiver: str
    task: str
    payload: dict[str, Any]
    message_type: str = "delegate"

    def as_dict(self) -> dict[str, Any]:
        return {
            "protocol": "a2a.supervisor.local/v1",
            "message_type": self.message_type,
            "sender": self.sender,
            "receiver": self.receiver,
            "task": self.task,
            "payload": self.payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }


class LocalMCPToolbox:
    """Local MCP-style tool registry used by the retrieval worker."""

    name = "local-rag-mcp"

    def manifest(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "rag.generate_with_citation",
                "description": "Retrieve local legal/news context and generate a cited Vietnamese answer.",
                "input_schema": {"query": "str", "history": "list", "top_k": "int"},
            }
        ]

    def call(self, tool_name: str, *, query: str, history: list[dict[str, str]], top_k: int) -> dict[str, Any]:
        if tool_name != "rag.generate_with_citation":
            raise ValueError(f"Unknown MCP tool: {tool_name}")
        return generate_with_citation(query, history=history, top_k=top_k)


MCP = LocalMCPToolbox()
SUPERVISOR = "Supervisor"


def _append_trace(state: MultiAgentState, name: str, role: str, status: str, detail: str) -> list[AgentTrace]:
    return [*state.get("trace", []), {"name": name, "role": role, "status": status, "detail": detail}]


def _append_a2a(
    state: MultiAgentState,
    sender: str,
    receiver: str,
    task: str,
    payload: dict[str, Any],
    message_type: str = "delegate",
) -> list[dict[str, Any]]:
    envelope = A2AEnvelope(sender, receiver, task, payload, message_type)
    return [*state.get("a2a_messages", []), envelope.as_dict()]


def _classify_intent(query: str) -> Intent:
    normalized = query.lower()
    legal_terms = [
        "luat",
        "dieu",
        "nghi dinh",
        "hinh phat",
        "toi",
        "cai nghien",
        "ma tuy",
        "luật",
        "điều",
        "nghị định",
        "hình phạt",
        "tội",
        "cai nghiện",
        "ma túy",
    ]
    news_terms = [
        "bai bao",
        "tin",
        "nghe si",
        "vu",
        "bat",
        "truyen thong",
        "su kien",
        "bài báo",
        "nghệ sĩ",
        "vụ",
        "bắt",
        "truyền thông",
        "sự kiện",
    ]

    legal_score = sum(term in normalized for term in legal_terms)
    news_score = sum(term in normalized for term in news_terms)
    if news_score > legal_score:
        return "news"
    if legal_score > 0:
        return "legal"
    return "general"


def supervisor_agent(state: MultiAgentState) -> MultiAgentState:
    plan = ["router", "retrieval", "specialist", "guard", "finalize"]
    trace = _append_trace(
        state,
        SUPERVISOR,
        "A2A supervisor",
        "running",
        "Received the user task, created the agent plan, and will route all A2A messages.",
    )
    messages = _append_a2a(
        {**state, "trace": trace},
        "UserProxy",
        SUPERVISOR,
        "submit_user_question",
        {"top_k": state.get("top_k", 5), "plan": plan},
        "request",
    )
    messages = [
        *messages,
        A2AEnvelope(SUPERVISOR, "Router", "classify_intent", {"query_preview": state["query"][:120]}, "delegate").as_dict(),
    ]
    return {**state, "supervisor_plan": plan, "next_agent": "router", "trace": trace, "a2a_messages": messages}


def router_agent(state: MultiAgentState) -> MultiAgentState:
    intent = _classify_intent(state["query"])
    trace = _append_trace(state, "Router", "Intent worker", "done", f"Classified the question as {intent}.")
    messages = _append_a2a(
        {**state, "trace": trace},
        "Router",
        SUPERVISOR,
        "intent_report",
        {"intent": intent},
        "result",
    )
    messages = [
        *messages,
        A2AEnvelope(
            SUPERVISOR,
            "Retrieval MCP",
            "retrieve_and_generate",
            {"tool": "rag.generate_with_citation", "top_k": state.get("top_k", 5), "intent": intent},
            "delegate",
        ).as_dict(),
    ]
    return {**state, "intent": intent, "next_agent": "retrieval", "trace": trace, "a2a_messages": messages}


def retrieval_agent(state: MultiAgentState) -> MultiAgentState:
    result = MCP.call(
        "rag.generate_with_citation",
        query=state["query"],
        history=state.get("history", []),
        top_k=state.get("top_k", 5),
    )
    sources = result.get("sources", [])
    trace = _append_trace(
        state,
        "Retrieval MCP",
        "MCP tool worker",
        "done",
        f"Called rag.generate_with_citation and returned {len(sources)} sources.",
    )
    specialist = _choose_specialist({**state, "intent": state.get("intent", "general")})
    specialist_name = {"law": "Law Agent", "news": "News Agent", "general": "General Agent"}[specialist]
    messages = _append_a2a(
        {**state, "trace": trace},
        "Retrieval MCP",
        SUPERVISOR,
        "retrieval_report",
        {"sources": len(sources), "retrieval_source": result.get("retrieval_source", "none")},
        "result",
    )
    messages = [
        *messages,
        A2AEnvelope(SUPERVISOR, specialist_name, "specialist_review", {"intent": state.get("intent", "general")}, "delegate").as_dict(),
    ]
    return {
        **state,
        "retrieval_result": result,
        "answer": result.get("answer", ""),
        "retrieval_source": result.get("retrieval_source", "none"),
        "sources": sources,
        "mcp_tools": MCP.manifest(),
        "next_agent": specialist,
        "trace": trace,
        "a2a_messages": messages,
    }


def legal_specialist_agent(state: MultiAgentState) -> MultiAgentState:
    detail = "Reviewed the answer with a legal lens: statutes, obligations, and citation boundaries."
    return _specialist_done(state, "Law Agent", "Legal specialist", detail)


def news_specialist_agent(state: MultiAgentState) -> MultiAgentState:
    detail = "Reviewed the answer with a news lens: event context, source attribution, and no extra speculation."
    return _specialist_done(state, "News Agent", "News specialist", detail)


def general_specialist_agent(state: MultiAgentState) -> MultiAgentState:
    detail = "Reviewed the answer for a friendly response and useful follow-up direction."
    return _specialist_done(state, "General Agent", "General assistant", detail)


def _specialist_done(state: MultiAgentState, name: str, role: str, detail: str) -> MultiAgentState:
    trace = _append_trace(state, name, role, "done", detail)
    messages = _append_a2a({**state, "trace": trace}, name, SUPERVISOR, "specialist_report", {"reviewed_by": name}, "result")
    messages = [
        *messages,
        A2AEnvelope(SUPERVISOR, "Citation Guard", "grounding_check", {"has_sources": bool(state.get("sources", []))}, "delegate").as_dict(),
    ]
    return {**state, "next_agent": "guard", "trace": trace, "a2a_messages": messages}


def citation_guard_agent(state: MultiAgentState) -> MultiAgentState:
    answer = state.get("answer", "")
    sources = state.get("sources", [])
    citations_ok = not sources or ("[" in answer and "]" in answer)
    detail = "Citation check passed." if citations_ok else "Citation check needs review because the answer has sources but no bracketed citation."
    trace = _append_trace(state, "Citation Guard", "Grounding worker", "done", detail)
    messages = _append_a2a(
        {**state, "trace": trace},
        "Citation Guard",
        SUPERVISOR,
        "grounding_report",
        {"citations_ok": citations_ok},
        "result",
    )
    messages = [
        *messages,
        A2AEnvelope(SUPERVISOR, SUPERVISOR, "finalize_response", {"citations_ok": citations_ok}, "control").as_dict(),
    ]
    return {**state, "citations_ok": citations_ok, "next_agent": "finalize", "trace": trace, "a2a_messages": messages}


def supervisor_finalize_agent(state: MultiAgentState) -> MultiAgentState:
    trace = _append_trace(
        state,
        SUPERVISOR,
        "A2A supervisor",
        "done",
        "Collected worker results and returned the final response to the user.",
    )
    messages = _append_a2a(
        {**state, "trace": trace},
        SUPERVISOR,
        "UserProxy",
        "final_answer_ready",
        {
            "intent": state.get("intent", "general"),
            "citations_ok": state.get("citations_ok", False),
            "sources": len(state.get("sources", [])),
        },
        "response",
    )
    return {**state, "trace": trace, "a2a_messages": messages}


def _choose_specialist(state: MultiAgentState) -> str:
    intent = state.get("intent", "general")
    if intent == "legal":
        return "law"
    if intent == "news":
        return "news"
    return "general"


def _build_langgraph_app():
    try:
        from langgraph.graph import END, StateGraph
    except Exception:
        return None

    graph = StateGraph(MultiAgentState)
    graph.add_node("supervisor", supervisor_agent)
    graph.add_node("router", router_agent)
    graph.add_node("retrieval", retrieval_agent)
    graph.add_node("law", legal_specialist_agent)
    graph.add_node("news", news_specialist_agent)
    graph.add_node("general", general_specialist_agent)
    graph.add_node("guard", citation_guard_agent)
    graph.add_node("finalize", supervisor_finalize_agent)

    graph.set_entry_point("supervisor")
    graph.add_edge("supervisor", "router")
    graph.add_edge("router", "retrieval")
    graph.add_conditional_edges("retrieval", _choose_specialist, {"law": "law", "news": "news", "general": "general"})
    graph.add_edge("law", "guard")
    graph.add_edge("news", "guard")
    graph.add_edge("general", "guard")
    graph.add_edge("guard", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


LANGGRAPH_APP = _build_langgraph_app()


def _run_fallback(initial_state: MultiAgentState) -> MultiAgentState:
    supervised = supervisor_agent(initial_state)
    routed = router_agent(supervised)
    retrieved = retrieval_agent(routed)
    specialist = _choose_specialist(retrieved)
    if specialist == "law":
        reviewed = legal_specialist_agent(retrieved)
    elif specialist == "news":
        reviewed = news_specialist_agent(retrieved)
    else:
        reviewed = general_specialist_agent(retrieved)
    guarded = citation_guard_agent(reviewed)
    return supervisor_finalize_agent(guarded)


def run_multi_agent_chat(query: str, history: list[dict[str, str]] | None = None, top_k: int = 5) -> dict[str, Any]:
    """Run one supervised multi-agent turn and return UI-friendly payload."""
    initial_state: MultiAgentState = {
        "query": query,
        "history": history or [],
        "top_k": top_k,
        "trace": [],
        "a2a_messages": [],
        "mcp_tools": MCP.manifest(),
    }

    if LANGGRAPH_APP is not None:
        final_state = LANGGRAPH_APP.invoke(initial_state)
        graph_runtime = "langgraph-supervisor"
    else:
        final_state = _run_fallback(initial_state)
        graph_runtime = "supervisor-fallback"

    return {
        "answer": final_state.get("answer", ""),
        "retrieval_source": final_state.get("retrieval_source", "none"),
        "sources": final_state.get("sources", []),
        "intent": final_state.get("intent", "general"),
        "citations_ok": final_state.get("citations_ok", False),
        "trace": final_state.get("trace", []),
        "a2a_messages": final_state.get("a2a_messages", []),
        "mcp_tools": final_state.get("mcp_tools", MCP.manifest()),
        "graph_runtime": graph_runtime,
    }
