import os
import unittest
from datetime import date, datetime, timezone

from app.storage import MemoryStore
from app.tenant import TenantError, load_tenant, parse_tenant
from tests.helpers import FIXED_NOW, KNOWLEDGE


class StoreContract:
    """Run against every store implementation."""

    def make(self):
        raise NotImplementedError

    def test_session_history_is_capped_and_isolated(self):
        s = self.make()
        s.get_or_create_session("a" * 20)
        s.get_or_create_session("b" * 20)
        for i in range(60):
            s.append_history("a" * 20, "user", f"m{i}", keep=40)
        self.assertEqual(len(s.get_or_create_session("a" * 20)["history"]), 40)
        self.assertEqual(s.get_or_create_session("b" * 20)["history"], [])

    def test_leads_dedupe_by_email_case_insensitively_and_by_phone(self):
        s = self.make()
        _, created = s.add_lead({"name": "A", "email": "a@x.com", "phone": ""})
        _, again = s.add_lead({"name": "A2", "email": "A@X.com", "phone": ""})
        self.assertTrue(created)
        self.assertFalse(again)
        _, p1 = s.add_lead({"name": "P", "email": "", "phone": "+17135550142"})
        _, p2 = s.add_lead({"name": "P", "email": "", "phone": "+17135550142"})
        self.assertTrue(p1)
        self.assertFalse(p2)
        self.assertEqual(len(s.list_leads()), 2)

    def test_a_slot_can_only_be_booked_once(self):
        s = self.make()
        self.assertIsNotNone(s.book_slot("2026-10-07T10:30", {"name": "A"}))
        self.assertIsNone(s.book_slot("2026-10-07T10:30", {"name": "B"}))
        self.assertEqual(s.taken_slots("2026-10-07"), {"2026-10-07T10:30"})

    def test_handoff_queue(self):
        s = self.make()
        hid = s.add_handoff({"reason": "frustrated"})
        self.assertEqual(len(s.list_handoffs("open")), 1)
        self.assertTrue(s.resolve_handoff(hid))
        self.assertEqual(s.list_handoffs("open"), [])
        self.assertFalse(s.resolve_handoff("nope"))

    def test_stats(self):
        s = self.make()
        s.record_turn({"latency_ms": 100.0, "searched": True, "no_answer": True, "flags": [], "blocked": 0, "tokens": 5})
        s.record_turn({"latency_ms": 300.0, "searched": True, "no_answer": False, "flags": ["x"], "blocked": 1, "tokens": 7})
        st = s.stats()
        self.assertEqual(st["turns"], 2)
        self.assertEqual(st["avg_latency_ms"], 200.0)
        self.assertEqual(st["no_answer_rate"], 0.5)
        self.assertEqual((st["flagged_turns"], st["blocked_actions"], st["tokens"]), (1, 1, 12))


class MemoryStoreTests(StoreContract, unittest.TestCase):
    def make(self):
        return MemoryStore()

    def test_expired_sessions_are_pruned(self):
        s = MemoryStore(ttl_days=1)
        s.get_or_create_session("a" * 20)
        s.sessions["a" * 20]["last_seen"] = datetime(2020, 1, 1, tzinfo=timezone.utc).isoformat()
        s._max_sessions = 1
        s.get_or_create_session("b" * 20)
        self.assertNotIn("a" * 20, s.sessions)


@unittest.skipUnless(os.environ.get("MONGO_URI"), "set MONGO_URI to run the MongoDB contract tests")
class MongoStoreTests(StoreContract, unittest.TestCase):
    def make(self):
        from app.storage import MongoStore

        store = MongoStore(os.environ["MONGO_URI"], "concierge_test")
        for coll in (store.sessions, store.leads, store.handoffs, store.bookings, store.turns):
            coll.delete_many({})
        return store


class TenantTests(unittest.TestCase):
    def test_both_packs_load(self):
        for slug in ("brightside-solar", "chidama-tech"):
            t = load_tenant(KNOWLEDGE, slug)
            self.assertTrue(t.business_name and t.assistant_name)
        self.assertTrue(load_tenant(KNOWLEDGE, "brightside-solar").booking.enabled)
        self.assertFalse(load_tenant(KNOWLEDGE, "chidama-tech").booking.enabled)

    def test_slots_respect_hours_notice_and_closed_days(self):
        t = load_tenant(KNOWLEDGE, "brightside-solar")
        wed = t.slots_for(date(2026, 10, 7), FIXED_NOW)
        self.assertEqual(wed[0].strftime("%H:%M"), "09:00")
        self.assertEqual(wed[-1].strftime("%H:%M"), "15:45")
        self.assertEqual(t.slots_for(date(2026, 10, 11), FIXED_NOW), [])           # Sunday
        self.assertEqual(t.slots_for(date(2026, 10, 5), FIXED_NOW), [])            # today: inside 24h notice
        self.assertEqual(t.slots_for(date(2027, 3, 1), FIXED_NOW), [])             # beyond booking window

    def test_validation_errors_are_clear(self):
        base = {"business_name": "X", "assistant_name": "Y", "about": "Z", "welcome_message": "W"}
        parse_tenant("ok", base)
        with self.assertRaises(TenantError):
            parse_tenant("t", {**base, "timezone": "Mars/Base"})
        with self.assertRaises(TenantError):
            parse_tenant("t", {**base, "booking": {"enabled": True, "hours": {"mon": ["17:00", "09:00"]}}})
        with self.assertRaises(TenantError):
            parse_tenant("t", {**base, "booking": {"hours": {"funday": ["09:00", "10:00"]}}})
        with self.assertRaises(TenantError):
            parse_tenant("t", {"business_name": "X"})


if __name__ == "__main__":
    unittest.main()
