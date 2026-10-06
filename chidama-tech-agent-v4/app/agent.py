"""The agent runtime: one function per graph node, run by LangGraph (default) or an equivalent plain loop.

Messages are plain OpenAI-style dicts, so the same nodes work in both runners and in tests.
"""
from __future__ import annotations

import json
import logging
import operator
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Callable, TypedDict

import requests

from .config import Settings
from .prompts import build_system_prompt
from .rag.chunking import chunk_all, load_documents
from .rag.retriever import BM25Index, HybridRetriever
from .security import sanitize_output, sanitize_text, scan_injection
from .storage import create_store
from .tenant import Tenant, load_tenant
from .tools import ToolContext, execute_tool

log = logging.getLogger("concierge.agent")

FALLBACK = "Sorry, I'm having trouble answering right now. Please try again in a moment, or ask me to connect you with a team member."
_CITE = re.compile(r"\[(\d{1,2})\]")


class LLMNotConfigured(RuntimeError):
    pass


@dataclass
class TurnResult:
    answer: str
    sources: list = field(default_factory=list)
    escalated: bool = False
    flags: list = field(default_factory=list)
    tools_used: list = field(default_factory=list)
    searched: bool = False
    no_answer: bool = False
    fallback: bool = False
    blocked: int = 0
    latency_ms: float = 0.0
    tokens: int = 0


def finalize_answer(text: str, sources: list[dict]) -> tuple[str, list[dict]]:
    """Clean model output and keep only citations that point at passages retrieved in this turn."""
    answer = sanitize_output(text)
    valid = {s["n"] for s in sources}
    cited: list[int] = []

    def keep(m: re.Match) -> str:
        n = int(m.group(1))
        if n in valid:
            if n not in cited:
                cited.append(n)
            return m.group(0)
        return ""

    answer = _CITE.sub(keep, answer)
    answer = re.sub(r"[ \t]{2,}", " ", answer)
    answer = re.sub(r"\s+([.,;!?])", r"\1", answer).strip()
    public = [{k: s[k] for k in ("n", "title", "heading", "snippet", "doc")} for s in sources if s["n"] in cited]
    return answer, public


class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    steps: int


class Nodes:
    """Graph nodes bound to one request's context."""

    def __init__(self, llm, ctx: ToolContext, max_steps: int):
        self.llm, self.ctx, self.max_steps = llm, ctx, max_steps
        self.tokens = 0
        self.fallback = False

    def model(self, state: dict) -> dict:
        steps = state["steps"]
        if steps >= self.max_steps:
            self.fallback = True
            return {"messages": [{"role": "assistant", "content": FALLBACK}], "steps": steps + 1}
        reply = None
        for attempt in range(2):   # one retry covers transient provider errors and malformed tool calls
            try:
                reply = self.llm.chat(state["messages"], self.ctx.specs)
                break
            except Exception as exc:
                log.error("llm call failed (attempt %d): %s", attempt + 1, type(exc).__name__)
        if reply is None:
            self.fallback = True
            return {"messages": [{"role": "assistant", "content": FALLBACK}], "steps": steps + 1}
        self.tokens += int(reply.usage.get("total_tokens", 0) or 0)
        return {"messages": [reply.message], "steps": steps + 1}

    def tools(self, state: dict) -> dict:
        calls = state["messages"][-1].get("tool_calls") or []
        out = []
        for i, call in enumerate(calls):
            fn = call.get("function", {})
            result = "ERROR: too many tool calls in one step." if i >= 4 else execute_tool(self.ctx, fn.get("name", ""), fn.get("arguments"))
            out.append({"role": "tool", "tool_call_id": call.get("id", f"call_{i}"), "name": fn.get("name", ""), "content": result[:3000]})
        return {"messages": out}

    @staticmethod
    def route(state: dict) -> str:
        return "tools" if state["messages"][-1].get("tool_calls") else "end"


def run_simple(nodes: Nodes, messages: list[dict]) -> dict:
    state = {"messages": list(messages), "steps": 0}
    for _ in range(nodes.max_steps * 2 + 2):
        update = nodes.model(state)
        state["messages"] += update["messages"]
        state["steps"] = update["steps"]
        if nodes.route(state) == "end":
            break
        state["messages"] += nodes.tools(state)["messages"]
    return state


def run_langgraph(nodes: Nodes, messages: list[dict]) -> dict:
    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(AgentState)
    graph.add_node("model", lambda state: nodes.model(state))
    graph.add_node("tools", lambda state: nodes.tools(state))
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", nodes.route, {"tools": "tools", "end": END})
    graph.add_edge("tools", "model")
    app = graph.compile()
    return app.invoke({"messages": list(messages), "steps": 0}, {"recursion_limit": nodes.max_steps * 2 + 6})


class AgentRuntime:
    def __init__(self, settings: Settings, tenant: Tenant, store, retriever, llm,
                 clock: Callable[[], datetime] | None = None, http_post: Callable | None = None):
        self.settings, self.tenant, self.store, self.retriever, self.llm = settings, tenant, store, retriever, llm
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.http_post = http_post or requests.post
        self.orchestrator = settings.orchestrator
        if self.orchestrator == "langgraph":
            try:
                import langgraph  # noqa: F401
            except ImportError:
                log.warning("langgraph is not installed; using the plain-Python runner (same nodes)")
                self.orchestrator = "simple"

    def handle_message(self, session_id: str, text: str) -> TurnResult:
        if self.llm is None:
            raise LLMNotConfigured("GROQ_API_KEY is not set")
        started = time.perf_counter()
        message = sanitize_text(text, self.settings.max_message_chars)
        if not message:
            raise ValueError("empty message")
        flags = scan_injection(message)

        session = self.store.get_or_create_session(session_id)
        history = [m for m in session["history"][-self.settings.history_messages:] if m.get("role") in {"user", "assistant"}]
        ctx = ToolContext(settings=self.settings, tenant=self.tenant, store=self.store, retriever=self.retriever,
                          session_id=session_id, history=history, injection=bool(flags),
                          session_started=datetime.fromisoformat(session["created_at"]), now=self.clock, http_post=self.http_post)
        system = build_system_prompt(
            self.tenant, self.clock().astimezone(self.tenant.tz).strftime("%A %d %B %Y, %H:%M (%Z)"),
            session.get("unanswered_streak", 0), bool(flags), bool(session.get("escalated")),
            [s["function"]["name"] for s in ctx.specs],
        )
        messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": message}]
        nodes = Nodes(self.llm, ctx, self.settings.max_agent_steps)
        state = run_langgraph(nodes, messages) if self.orchestrator == "langgraph" else run_simple(nodes, messages)

        final = next((m for m in reversed(state["messages"]) if m.get("role") == "assistant" and not m.get("tool_calls")), None)
        content = (final or {}).get("content") or ""
        if not content.strip():
            nodes.fallback, content = True, FALLBACK
        answer, sources = finalize_answer(content, ctx.sources)
        no_answer = ctx.no_answer and not ctx.answered

        streak = session.get("unanswered_streak", 0)
        if ctx.searched:
            streak = streak + 1 if no_answer else 0
        # a message that tripped the tripwire is not replayed to the model on later turns
        self.store.append_history(session_id, "user", "[message removed by safety filter]" if flags else message)
        self.store.append_history(session_id, "assistant", answer)
        self.store.update_session(session_id, turns=session.get("turns", 0) + 1, unanswered_streak=streak)
        if flags:
            self.store.incr_session(session_id, "flags")
        escalated = bool(self.store.get_or_create_session(session_id).get("escalated"))

        result = TurnResult(answer=answer, sources=sources, escalated=escalated, flags=flags, tools_used=list(ctx.tools_used),
                            searched=ctx.searched, no_answer=no_answer, fallback=nodes.fallback, blocked=ctx.blocked,
                            latency_ms=round((time.perf_counter() - started) * 1000, 1), tokens=nodes.tokens)
        self.store.record_turn({"latency_ms": result.latency_ms, "tools": result.tools_used, "searched": result.searched,
                                "no_answer": result.no_answer, "fallback": result.fallback, "flags": flags,
                                "blocked": result.blocked, "tokens": result.tokens})
        log.info(json.dumps({"event": "turn", "session": session_id[:8], "latency_ms": result.latency_ms, "tools": result.tools_used,
                             "no_answer": result.no_answer, "fallback": result.fallback, "flags": flags, "blocked": result.blocked}))
        return result


def build_retriever(settings: Settings, tenant: Tenant):
    pack = Path(settings.knowledge_dir) / settings.tenant
    chunks = chunk_all(load_documents(pack))
    if not chunks:
        raise RuntimeError(f"no documents found in {pack}")
    bm25 = BM25Index(chunks, tenant.synonyms, min_coverage=settings.min_coverage, min_score=settings.min_score)
    if settings.retriever == "hybrid":
        from .rag.vector import FastEmbedder, VectorIndex

        return HybridRetriever(bm25, VectorIndex(chunks, FastEmbedder()), settings.vector_min_sim)
    return bm25


def build_runtime(settings: Settings, llm=None) -> AgentRuntime:
    tenant = load_tenant(settings.knowledge_dir, settings.tenant)
    retriever = build_retriever(settings, tenant)
    if llm is None and settings.groq_api_key:
        from .llm import GroqLLM

        llm = GroqLLM(settings.groq_api_key, settings.groq_model, settings.temperature, settings.max_tokens)
    return AgentRuntime(settings, tenant, create_store(settings), retriever, llm)
