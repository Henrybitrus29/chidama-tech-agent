"""LLM client. The agent talks to this tiny interface, so tests can swap in a fake and the vendor can change."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class LLMReply:
    message: dict                      # OpenAI-style assistant message: {"role","content", optional "tool_calls"}
    usage: dict = field(default_factory=dict)


def _strip(node):
    """Drop JSON-schema keywords the provider does not need (we enforce limits ourselves in tools.py)."""
    if isinstance(node, dict):
        return {k: _strip(v) for k, v in node.items() if k != "maxLength"}
    if isinstance(node, list):
        return [_strip(v) for v in node]
    return node


class GroqLLM:
    def __init__(self, api_key: str, model: str, temperature: float = 0.2, max_tokens: int = 600):
        from groq import Groq

        self._client = Groq(api_key=api_key, timeout=30.0, max_retries=1)
        self.model, self.temperature, self.max_tokens = model, temperature, max_tokens

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply:
        kwargs = {"model": self.model, "messages": messages, "temperature": self.temperature, "max_tokens": self.max_tokens}
        if tools:
            kwargs.update(tools=_strip(tools), tool_choice="auto")
        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        out: dict = {"role": "assistant", "content": msg.content or ""}
        if getattr(msg, "tool_calls", None):
            out["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
                for tc in msg.tool_calls
            ]
        usage = getattr(resp, "usage", None)
        return LLMReply(out, {"total_tokens": getattr(usage, "total_tokens", 0) or 0})
