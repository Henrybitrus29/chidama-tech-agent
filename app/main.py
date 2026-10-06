"""FastAPI app. All business logic lives in agent.py; this file is HTTP, limits and auth."""
from __future__ import annotations

import json
import logging

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .agent import AgentRuntime, LLMNotConfigured, build_runtime
from .config import Settings
from .security import RateLimiter, check_admin


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()
        if msg.startswith("{"):
            return msg
        return json.dumps({"level": record.levelname, "logger": record.name, "message": msg})


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str = Field(..., pattern=r"^[A-Za-z0-9_-]{16,64}$")


def client_ip(request: Request, trust_proxy: bool, hops: int = 1) -> str:
    """Real client address. X-Forwarded-For is client-controlled at its left end: a visitor can send any value there and
    each proxy appends what it saw. So read from the RIGHT, counting only proxies you run or trust (`hops`)."""
    if trust_proxy:
        parts = [p.strip() for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "unknown"


def create_app(settings: Settings | None = None, runtime: AgentRuntime | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging()
    rt = runtime or build_runtime(settings)
    docs = {} if settings.enable_docs else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="Concierge Agent", version="1.0.0", **docs)
    app.state.runtime = rt
    ip_limiter = RateLimiter(settings.rate_limit_ip_per_min)
    session_limiter = RateLimiter(settings.rate_limit_session_per_min)
    ip_day_limiter = RateLimiter(settings.rate_limit_ip_per_day, window_seconds=86400.0)
    global_limiter = RateLimiter(settings.daily_turn_cap, window_seconds=86400.0, max_keys=4)

    if settings.allowed_origins:
        app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_credentials=False,
                           allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["Content-Type"], max_age=600)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > 16_384:
            return JSONResponse({"detail": "Request too large."}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logging.getLogger("concierge.api").exception("unhandled error")
        return JSONResponse({"detail": "Something went wrong. Please try again."}, status_code=500)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "tenant": rt.tenant.slug, "chunks": len(rt.retriever), "llm_configured": rt.llm is not None,
                "orchestrator": rt.orchestrator, "store": settings.store}

    @app.get("/api/config")
    def public_config():
        t = rt.tenant
        return {"business_name": t.business_name, "assistant_name": t.assistant_name, "welcome_message": t.welcome_message,
                "suggested_questions": list(t.suggested_questions), "booking_enabled": t.booking.enabled,
                "privacy_notice": t.privacy_notice}

    @app.post("/api/chat")
    def chat(req: ChatRequest, request: Request):
        ip = client_ip(request, settings.trust_proxy, settings.trusted_proxy_hops)
        for limiter, key in ((ip_limiter, ip), (session_limiter, req.session_id), (ip_day_limiter, ip)):
            allowed, retry_after = limiter.allow(key)
            if not allowed:
                return JSONResponse({"detail": "Too many messages. Please wait a moment."}, status_code=429,
                                    headers={"Retry-After": str(retry_after)})
        if not global_limiter.allow("all")[0]:   # the free LLM quota is shared, so one busy day must not take the site down for good
            return JSONResponse({"detail": "The assistant has reached its daily limit. Please try again tomorrow or email the team."},
                                status_code=503, headers={"Retry-After": "3600"})
        try:
            result = rt.handle_message(req.session_id, req.message)
        except LLMNotConfigured:
            raise HTTPException(503, "The assistant is not available right now.")
        except ValueError:
            raise HTTPException(422, "Message is empty.")
        return {"answer": result.answer, "sources": result.sources, "escalated": result.escalated, "session_id": req.session_id}

    # ---- staff endpoints (X-Admin-Token); disabled entirely when ADMIN_TOKEN is not set
    def require_admin(token: str | None) -> None:
        if not settings.admin_token:
            raise HTTPException(404, "Not found")
        if not check_admin(token, settings.admin_token):
            raise HTTPException(401, "Unauthorized")

    @app.get("/api/admin/handoffs")
    def handoffs(status: str | None = "open", x_admin_token: str | None = Header(default=None)):
        require_admin(x_admin_token)
        return {"items": rt.store.list_handoffs(None if status == "all" else status)}

    @app.post("/api/admin/handoffs/{handoff_id}/resolve")
    def resolve(handoff_id: str, x_admin_token: str | None = Header(default=None)):
        require_admin(x_admin_token)
        if not rt.store.resolve_handoff(handoff_id):
            raise HTTPException(404, "Not found")
        return {"status": "resolved"}

    @app.get("/api/admin/leads")
    def leads(x_admin_token: str | None = Header(default=None)):
        require_admin(x_admin_token)
        return {"items": rt.store.list_leads()}

    @app.get("/api/admin/bookings")
    def bookings(x_admin_token: str | None = Header(default=None)):
        require_admin(x_admin_token)
        return {"items": rt.store.list_bookings()}

    @app.get("/api/admin/stats")
    def stats(x_admin_token: str | None = Header(default=None)):
        require_admin(x_admin_token)
        return rt.store.stats()

    return app
