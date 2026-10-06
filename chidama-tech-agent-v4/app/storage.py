"""Persistence behind one small interface. MemoryStore for dev/tests/free hosting, MongoStore for durability."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def lead_key(lead: dict) -> str:
    email = (lead.get("email") or "").strip().lower()
    return f"e:{email}" if email else f"p:{lead.get('phone', '')}"


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[min(len(ordered) - 1, int(len(ordered) * pct))], 1)


def summarize_turns(turns: list[dict], extra: dict) -> dict:
    n = len(turns)
    latencies = [t["latency_ms"] for t in turns if "latency_ms" in t]
    searched = [t for t in turns if t.get("searched")]
    return {
        "turns": n,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "searched_turns": len(searched),
        "no_answer_rate": round(sum(1 for t in searched if t.get("no_answer")) / len(searched), 3) if searched else None,
        "fallback_turns": sum(1 for t in turns if t.get("fallback")),
        "flagged_turns": sum(1 for t in turns if t.get("flags")),
        "blocked_actions": sum(t.get("blocked", 0) for t in turns),
        "tokens": sum(t.get("tokens", 0) for t in turns),
        **extra,
    }


class MemoryStore:
    def __init__(self, ttl_days: int = 7, max_sessions: int = 5000):
        self._lock = threading.RLock()
        self._ttl = timedelta(days=ttl_days)
        self._max_sessions = max_sessions
        self.sessions: dict[str, dict] = {}
        self.leads: dict[str, dict] = {}
        self.lead_keys: dict[str, str] = {}
        self.handoffs: dict[str, dict] = {}
        self.bookings: dict[str, dict] = {}
        self.slots: dict[str, str] = {}
        self.turns: list[dict] = []

    # sessions
    def get_or_create_session(self, sid: str) -> dict:
        with self._lock:
            self._prune()
            s = self.sessions.get(sid)
            if s is None:
                now = iso(utcnow())
                s = {"id": sid, "created_at": now, "last_seen": now, "turns": 0, "history": [],
                     "escalated": False, "unanswered_streak": 0, "leads": 0, "bookings": 0, "flags": 0}
                self.sessions[sid] = s
            return {**s, "history": list(s["history"])}

    def update_session(self, sid: str, **fields) -> None:
        with self._lock:
            if sid in self.sessions:
                self.sessions[sid].update(fields)
                self.sessions[sid]["last_seen"] = iso(utcnow())

    def incr_session(self, sid: str, field: str, by: int = 1) -> None:
        with self._lock:
            if sid in self.sessions:
                self.sessions[sid][field] = self.sessions[sid].get(field, 0) + by

    def append_history(self, sid: str, role: str, content: str, keep: int = 40) -> None:
        with self._lock:
            if sid in self.sessions:
                h = self.sessions[sid]["history"]
                h.append({"role": role, "content": content})
                del h[:-keep]

    def _prune(self) -> None:
        cutoff = utcnow() - self._ttl
        if len(self.sessions) > self._max_sessions // 2 or len(self.sessions) % 50 == 0:
            for sid in [k for k, v in self.sessions.items() if datetime.fromisoformat(v["last_seen"]) < cutoff]:
                del self.sessions[sid]
        while len(self.sessions) > self._max_sessions:
            oldest = min(self.sessions, key=lambda k: self.sessions[k]["last_seen"])
            del self.sessions[oldest]

    # leads
    def add_lead(self, lead: dict) -> tuple[str, bool]:
        with self._lock:
            key = lead_key(lead)
            if key in self.lead_keys:
                return self.lead_keys[key], False
            lid = new_id("lead")
            self.leads[lid] = {**lead, "id": lid, "created_at": iso(utcnow())}
            self.lead_keys[key] = lid
            return lid, True

    def list_leads(self, limit: int = 100) -> list[dict]:
        with self._lock:
            return sorted(self.leads.values(), key=lambda x: x["created_at"], reverse=True)[:limit]

    # handoffs
    def add_handoff(self, handoff: dict) -> str:
        with self._lock:
            hid = new_id("handoff")
            self.handoffs[hid] = {**handoff, "id": hid, "status": "open", "created_at": iso(utcnow())}
            return hid

    def list_handoffs(self, status: str | None = None, limit: int = 100) -> list[dict]:
        with self._lock:
            items = [h for h in self.handoffs.values() if status in (None, h["status"])]
            return sorted(items, key=lambda x: x["created_at"], reverse=True)[:limit]

    def resolve_handoff(self, hid: str) -> bool:
        with self._lock:
            if hid in self.handoffs:
                self.handoffs[hid]["status"] = "resolved"
                return True
            return False

    # bookings (atomic: a slot can be booked once)
    def book_slot(self, slot_key: str, booking: dict) -> str | None:
        with self._lock:
            if slot_key in self.slots:
                return None
            bid = new_id("bk")
            self.bookings[bid] = {**booking, "id": bid, "slot": slot_key, "created_at": iso(utcnow())}
            self.slots[slot_key] = bid
            return bid

    def taken_slots(self, prefix: str) -> set[str]:
        with self._lock:
            return {s for s in self.slots if s.startswith(prefix)}

    def list_bookings(self, limit: int = 100) -> list[dict]:
        with self._lock:
            return sorted(self.bookings.values(), key=lambda x: x["created_at"], reverse=True)[:limit]

    # metrics
    def record_turn(self, metrics: dict) -> None:
        with self._lock:
            self.turns.append(metrics)
            del self.turns[:-5000]

    def stats(self) -> dict:
        with self._lock:
            extra = {
                "sessions": len(self.sessions), "leads": len(self.leads), "bookings": len(self.bookings),
                "handoffs_open": sum(1 for h in self.handoffs.values() if h["status"] == "open"),
                "handoffs_total": len(self.handoffs),
            }
            return summarize_turns(list(self.turns), extra)


class MongoStore:
    """Same interface on MongoDB (Atlas free tier works). Needs `pymongo`."""

    def __init__(self, uri: str, db_name: str = "concierge", ttl_days: int = 7):
        from pymongo import ASCENDING, MongoClient

        self._client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = self._client[db_name]
        self.sessions, self.leads, self.handoffs = db["sessions"], db["leads"], db["handoffs"]
        self.bookings, self.turns = db["bookings"], db["turns"]
        self.sessions.create_index([("last_seen_dt", ASCENDING)], expireAfterSeconds=ttl_days * 86400)
        self.turns.create_index([("at", ASCENDING)], expireAfterSeconds=30 * 86400)
        self.leads.create_index("dedupe_key", unique=True)
        self.bookings.create_index("slot", unique=True)

    def get_or_create_session(self, sid: str) -> dict:
        from pymongo import ReturnDocument

        now = utcnow()
        doc = self.sessions.find_one_and_update(
            {"_id": sid},
            {"$setOnInsert": {"id": sid, "created_at": iso(now), "turns": 0, "history": [], "escalated": False,
                              "unanswered_streak": 0, "leads": 0, "bookings": 0, "flags": 0},
             "$set": {"last_seen": iso(now), "last_seen_dt": now}},
            upsert=True, return_document=ReturnDocument.AFTER,
        )
        doc.pop("_id", None)
        return doc

    def update_session(self, sid: str, **fields) -> None:
        now = utcnow()
        self.sessions.update_one({"_id": sid}, {"$set": {**fields, "last_seen": iso(now), "last_seen_dt": now}})

    def incr_session(self, sid: str, field: str, by: int = 1) -> None:
        self.sessions.update_one({"_id": sid}, {"$inc": {field: by}})

    def append_history(self, sid: str, role: str, content: str, keep: int = 40) -> None:
        self.sessions.update_one({"_id": sid}, {"$push": {"history": {"$each": [{"role": role, "content": content}], "$slice": -keep}}})

    def add_lead(self, lead: dict) -> tuple[str, bool]:
        from pymongo.errors import DuplicateKeyError

        key = lead_key(lead)
        lid = new_id("lead")
        try:
            self.leads.insert_one({**lead, "_id": lid, "id": lid, "dedupe_key": key, "created_at": iso(utcnow())})
            return lid, True
        except DuplicateKeyError:
            existing = self.leads.find_one({"dedupe_key": key}) or {}
            return existing.get("id", lid), False

    def list_leads(self, limit: int = 100) -> list[dict]:
        return [{k: v for k, v in d.items() if k != "_id"} for d in self.leads.find().sort("created_at", -1).limit(limit)]

    def add_handoff(self, handoff: dict) -> str:
        hid = new_id("handoff")
        self.handoffs.insert_one({**handoff, "_id": hid, "id": hid, "status": "open", "created_at": iso(utcnow())})
        return hid

    def list_handoffs(self, status: str | None = None, limit: int = 100) -> list[dict]:
        query = {"status": status} if status else {}
        return [{k: v for k, v in d.items() if k != "_id"} for d in self.handoffs.find(query).sort("created_at", -1).limit(limit)]

    def resolve_handoff(self, hid: str) -> bool:
        return self.handoffs.update_one({"_id": hid}, {"$set": {"status": "resolved"}}).matched_count == 1

    def book_slot(self, slot_key: str, booking: dict) -> str | None:
        from pymongo.errors import DuplicateKeyError

        bid = new_id("bk")
        try:
            self.bookings.insert_one({**booking, "_id": bid, "id": bid, "slot": slot_key, "created_at": iso(utcnow())})
            return bid
        except DuplicateKeyError:
            return None

    def taken_slots(self, prefix: str) -> set[str]:
        return {d["slot"] for d in self.bookings.find({"slot": {"$regex": f"^{prefix}"}}, {"slot": 1})}

    def list_bookings(self, limit: int = 100) -> list[dict]:
        return [{k: v for k, v in d.items() if k != "_id"} for d in self.bookings.find().sort("created_at", -1).limit(limit)]

    def record_turn(self, metrics: dict) -> None:
        self.turns.insert_one({**metrics, "at": utcnow()})

    def stats(self) -> dict:
        turns = list(self.turns.find().sort("at", -1).limit(5000))
        extra = {
            "sessions": self.sessions.estimated_document_count(), "leads": self.leads.estimated_document_count(),
            "bookings": self.bookings.estimated_document_count(),
            "handoffs_open": self.handoffs.count_documents({"status": "open"}),
            "handoffs_total": self.handoffs.estimated_document_count(),
        }
        return summarize_turns(turns, extra)


def create_store(settings) -> MemoryStore | MongoStore:
    if settings.store == "mongo":
        if not settings.mongo_uri:
            raise RuntimeError("STORE=mongo needs MONGO_URI")
        return MongoStore(settings.mongo_uri, settings.mongo_db, settings.session_ttl_days)
    return MemoryStore(ttl_days=settings.session_ttl_days)
