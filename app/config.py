"""Settings, read once from environment variables. No third-party dependencies."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _bool(value: str | None, default: bool) -> bool:
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _csv(value: str | None) -> tuple[str, ...]:
    return tuple(v.strip() for v in (value or "").split(",") if v.strip())


@dataclass(frozen=True)
class Settings:
    # which business the agent represents (folder under knowledge_dir)
    tenant: str = "brightside-solar"
    knowledge_dir: str = "knowledge"

    # model
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    temperature: float = 0.2
    max_tokens: int = 600
    orchestrator: str = "langgraph"        # "langgraph" | "simple" (same nodes, plain Python loop)
    max_agent_steps: int = 5

    # retrieval
    retriever: str = "bm25"                # "bm25" | "hybrid" (needs fastembed + numpy)
    top_k: int = 3
    min_coverage: float = 0.5
    min_score: float = 0.0
    vector_min_sim: float = 0.72

    # conversation
    max_message_chars: int = 1000
    history_messages: int = 12
    session_ttl_days: int = 7

    # abuse limits
    rate_limit_ip_per_min: int = 20
    rate_limit_session_per_min: int = 10
    max_leads_per_session: int = 2
    max_bookings_per_session: int = 2
    rate_limit_ip_per_day: int = 150       # per client IP, rolling 24 h (stops session-id rotation)
    daily_turn_cap: int = 600              # all visitors together, rolling 24 h (protects the free LLM quota)

    # web
    allowed_origins: tuple[str, ...] = ()
    trust_proxy: bool = False
    trusted_proxy_hops: int = 1            # proxies that append to X-Forwarded-For (read the entry they added)
    admin_token: str = ""
    enable_docs: bool = False

    # persistence
    store: str = "memory"                  # "memory" | "mongo"
    mongo_uri: str = ""
    mongo_db: str = "concierge"

    # outbound hooks (all optional)
    lead_webhook_url: str = ""             # e.g. your LeadFlow n8n webhook
    lead_webhook_token: str = ""
    notify_webhook_url: str = ""           # Discord-compatible webhook for handoffs, leads, bookings
    booking_webhook_url: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ.get
        return cls(
            tenant=e("TENANT", cls.tenant),
            knowledge_dir=e("KNOWLEDGE_DIR", cls.knowledge_dir),
            groq_api_key=e("GROQ_API_KEY", ""),
            groq_model=e("GROQ_MODEL", cls.groq_model),
            temperature=float(e("TEMPERATURE", cls.temperature)),
            max_tokens=int(e("MAX_TOKENS", cls.max_tokens)),
            orchestrator=e("ORCHESTRATOR", cls.orchestrator),
            max_agent_steps=int(e("MAX_AGENT_STEPS", cls.max_agent_steps)),
            retriever=e("RETRIEVER", cls.retriever),
            top_k=int(e("TOP_K", cls.top_k)),
            min_coverage=float(e("MIN_COVERAGE", cls.min_coverage)),
            min_score=float(e("MIN_SCORE", cls.min_score)),
            vector_min_sim=float(e("VECTOR_MIN_SIM", cls.vector_min_sim)),
            max_message_chars=int(e("MAX_MESSAGE_CHARS", cls.max_message_chars)),
            history_messages=int(e("HISTORY_MESSAGES", cls.history_messages)),
            session_ttl_days=int(e("SESSION_TTL_DAYS", cls.session_ttl_days)),
            rate_limit_ip_per_min=int(e("RATE_LIMIT_IP_PER_MIN", cls.rate_limit_ip_per_min)),
            rate_limit_session_per_min=int(e("RATE_LIMIT_SESSION_PER_MIN", cls.rate_limit_session_per_min)),
            max_leads_per_session=int(e("MAX_LEADS_PER_SESSION", cls.max_leads_per_session)),
            max_bookings_per_session=int(e("MAX_BOOKINGS_PER_SESSION", cls.max_bookings_per_session)),
            rate_limit_ip_per_day=int(e("RATE_LIMIT_IP_PER_DAY", cls.rate_limit_ip_per_day)),
            daily_turn_cap=int(e("DAILY_TURN_CAP", cls.daily_turn_cap)),
            allowed_origins=_csv(e("ALLOWED_ORIGINS")),
            trust_proxy=_bool(e("TRUST_PROXY"), False),
            trusted_proxy_hops=max(1, int(e("TRUSTED_PROXY_HOPS", cls.trusted_proxy_hops))),
            admin_token=e("ADMIN_TOKEN", ""),
            enable_docs=_bool(e("ENABLE_DOCS"), False),
            store=e("STORE", cls.store),
            mongo_uri=e("MONGO_URI", ""),
            mongo_db=e("MONGO_DB", cls.mongo_db),
            lead_webhook_url=e("LEAD_WEBHOOK_URL", ""),
            lead_webhook_token=e("LEAD_WEBHOOK_TOKEN", ""),
            notify_webhook_url=e("NOTIFY_WEBHOOK_URL") or e("DISCORD_WEBHOOK_URL", ""),
            booking_webhook_url=e("BOOKING_WEBHOOK_URL", ""),
        )
