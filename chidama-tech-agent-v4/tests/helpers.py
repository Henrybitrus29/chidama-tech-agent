"""Shared test fixtures: a scripted fake LLM, a fixed clock and a runtime factory. No network, no API key."""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from app.agent import AgentRuntime, build_retriever
from app.config import Settings
from app.llm import LLMReply
from app.storage import MemoryStore
from app.tenant import load_tenant

ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE = str(ROOT / "knowledge")
FIXED_NOW = datetime(2026, 10, 5, 15, 0, tzinfo=timezone.utc)   # Monday 10:00 in Houston


class FakeLLM:
    """Replays scripted assistant messages. An item may be a dict, or a callable(messages) -> dict, or an Exception."""

    def __init__(self, script):
        self.script, self.calls = list(script), []

    def chat(self, messages, tools):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        item = self.script.pop(0) if self.script else {"role": "assistant", "content": "done"}
        if isinstance(item, Exception):
            raise item
        if callable(item):
            item = item(messages)
        return LLMReply(item, {"total_tokens": 10})


def say(text: str) -> dict:
    return {"role": "assistant", "content": text}


def call(name: str, args: dict, call_id: str = "call_1") -> dict:
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def make_runtime(script=(), tenant="brightside-solar", http_post=None, **overrides):
    fields = {"knowledge_dir": KNOWLEDGE, "tenant": tenant, "orchestrator": "simple", **overrides}
    settings = replace(Settings(), **fields)
    t = load_tenant(KNOWLEDGE, tenant)
    llm = FakeLLM(script)
    rt = AgentRuntime(settings, t, MemoryStore(), build_retriever(settings, t), llm, clock=lambda: FIXED_NOW, http_post=http_post)
    return rt, llm


class FakeHTTP:
    def __init__(self, fail=False):
        self.calls, self.fail = [], fail

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers or {}})
        if self.fail:
            raise ConnectionError("boom")

        class R:
            status_code = 200
        return R()
