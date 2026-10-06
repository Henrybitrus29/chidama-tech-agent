"""Input cleaning, prompt-injection tripwires, rate limiting and output sanitizing. Standard library only."""
from __future__ import annotations

import hmac
import re
import threading
import time
from collections import deque

# control characters, zero-width and bidi-override characters (keeps \t and \n)
_INVISIBLE = re.compile(r"[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F\u200B-\u200F\u202A-\u202E\u2060-\u2064\uFEFF]")
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
_EMAIL = re.compile(r"^[^\s@<>\"']+@[^\s@<>\"']+\.[^\s@<>\"']{2,}$")
_TAGS = re.compile(r"<[^>]{0,200}>")
_BAD_LINK = re.compile(r"\]\((?!https?://)\S*\)", re.I)
_IMAGE = re.compile(r"!\[([^\]]{0,200})\]\([^)]{0,500}\)")

INJECTION_PATTERNS = [
    ("ignore_instructions", re.compile(r"ignore\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|earlier|your)\s+(instructions|rules|prompts?)", re.I)),
    ("disregard", re.compile(r"disregard\s+(all\s+|any\s+)?(the\s+)?(previous|prior|above|system|your)", re.I)),
    ("reveal_prompt", re.compile(r"(reveal|show|print|repeat|output)\s+(me\s+)?(your|the)\s+(system\s+|hidden\s+|initial\s+)?(prompt|instructions|rules)", re.I)),
    ("system_prompt_ref", re.compile(r"\b(system|developer)\s+(prompt|message)\b", re.I)),
    ("role_reassign", re.compile(r"\byou\s+are\s+(now|no\s+longer)\b|\bact\s+as\s+(an?\s+)?(admin|administrator|developer|dan)\b|\bpretend\s+(to\s+be|you\s+are)\b", re.I)),
    ("jailbreak", re.compile(r"\b(jailbreak|developer\s+mode|dan\s+mode|do\s+anything\s+now)\b", re.I)),
    ("tool_coercion", re.compile(r"\b(call|use|run|invoke|execute)\s+(the\s+)?(tool|function)\b", re.I)),
    ("suppress", re.compile(r"do\s+not\s+(tell|warn|flag|mention|report)\b", re.I)),
    ("ignore_given", re.compile(r"ignore\s+(all\s+|any\s+|the\s+)?(\w+\s+){0,2}(instructions|rules|guidelines|prompts?)\s+(you|that\s+you|above|given|before)", re.I)),
    ("forget_context", re.compile(r"forget\s+(everything|all|what)\s+(above|before|you\s+(were|have\s+been)\s+(told|given))|forget\s+(all\s+|your\s+|the\s+)?(previous|prior|earlier)\s+(instructions|rules|context)", re.I)),
    ("new_instructions", re.compile(r"\b(new|updated|override)\s+(instructions|rules|directives?)\s*:", re.I)),
    ("repeat_above", re.compile(r"(repeat|print|output|copy|paste|recite)\s+(everything|all(\s+of)?|the\s+text|the\s+words?)\s+(above|before)", re.I)),
    ("tool_name_ref", re.compile(r"\b(capture_lead|escalate_to_human|book_appointment|search_knowledge_base|get_available_slots)\b", re.I)),
    ("fake_role_marker", re.compile(r"(^|\n)\s*(system|developer|assistant)\s*:\s*(you|the\s+user|ignore|your|from\s+now|disable|grant|enable|new)", re.I)),
    ("chat_template", re.compile(r"<\|?(im_start|im_end|endoftext|system)\|?>|\[/?INST\]|<<SYS>>", re.I)),
    ("forged_message", re.compile(r'"role"\s*:\s*"(system|tool|assistant)"', re.I)),
    ("letter_spacing", re.compile(r"(?:\b[a-z0-9]\b[ .\-_]+){8,}\b[a-z0-9]\b", re.I)),   # "i g n o r e ..." evasion; nobody types eight single letters in a row
    ("ignore_other_languages", re.compile(r"ignora\w*\s+(todas\s+)?(las\s+)?instrucciones|ignore[rz]?\s+(toutes\s+)?(les|vos|tes)\s+instructions|ignoriere?\s+(alle\s+)?(vorherigen\s+)?anweisungen", re.I)),
]



def sanitize_text(text: object, max_chars: int, multiline: bool = True) -> str:
    s = _INVISIBLE.sub("", str(text if text is not None else "")).replace("\r", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s) if multiline else re.sub(r"\s+", " ", s)
    return s.strip()[:max_chars]


def scan_injection(text: str) -> list[str]:
    return [name for name, rx in INJECTION_PATTERNS if rx.search(text)]


def valid_session_id(value: str) -> bool:
    return bool(_SESSION_ID.match(value or ""))


def valid_email(value: str) -> bool:
    return bool(value) and len(value) <= 254 and bool(_EMAIL.match(value))


def normalize_phone(value: str) -> str | None:
    digits = re.sub(r"[^\d+]", "", value or "")
    plain = digits.lstrip("+")
    return digits if 7 <= len(plain) <= 15 and plain.isdigit() else None


def sanitize_output(text: str, max_chars: int = 2000) -> str:
    """Model output is untrusted too: remove HTML tags, markdown images and non-http(s) markdown link targets."""
    s = _INVISIBLE.sub("", text or "")
    s = _TAGS.sub("", s)
    s = _IMAGE.sub(lambda m: m.group(1), s)   # a markdown image is a zero-click data channel if a host ever renders markdown
    s = _BAD_LINK.sub("](#)", s)
    return s.strip()[:max_chars]


def discord_safe(text: str) -> str:
    """Stop @everyone / @here / role pings that originate in user-supplied text."""
    return text.replace("@", "@\u200b")


def check_admin(provided: str | None, expected: str) -> bool:
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided.encode(), expected.encode())


class RateLimiter:
    """Sliding-window limiter, in memory. Fine for a single process; use Redis or a proxy to scale out."""

    def __init__(self, limit: int, window_seconds: float = 60.0, max_keys: int = 20000, clock=time.monotonic):
        self.limit, self.window, self.max_keys, self._clock = limit, window_seconds, max_keys, clock
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = self._clock()
        with self._lock:
            if len(self._hits) > self.max_keys:
                self._hits = {k: q for k, q in self._hits.items() if q and now - q[-1] < self.window}
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                return False, max(1, int(self.window - (now - q[0])) + 1)
            q.append(now)
            return True, 0
