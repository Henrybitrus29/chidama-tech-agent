import json
import unittest

from app.tools import ToolContext, execute_tool
from tests.helpers import FIXED_NOW, FakeHTTP, make_runtime


def ctx_for(rt, sid="s" * 20, http=None, injection=False, **settings):
    rt.store.get_or_create_session(sid)
    return ToolContext(settings=rt.settings if not settings else __import__("dataclasses").replace(rt.settings, **settings),
                       tenant=rt.tenant, store=rt.store, retriever=rt.retriever, session_id=sid, now=lambda: FIXED_NOW,
                       http_post=http or FakeHTTP(), injection=injection, session_started=FIXED_NOW)


class ToolTests(unittest.TestCase):
    def setUp(self):
        self.rt, _ = make_runtime()

    # ---- knowledge search
    def test_search_returns_numbered_passages_and_records_sources(self):
        ctx = ctx_for(self.rt)
        out = execute_tool(ctx, "search_knowledge_base", {"query": "how much is an 8 kW system"})
        self.assertIn("[1]", out)
        self.assertTrue(ctx.answered and not ctx.no_answer)
        self.assertEqual(ctx.sources[0]["doc"], "pricing")

    def test_search_refuses_off_topic(self):
        ctx = ctx_for(self.rt)
        out = execute_tool(ctx, "search_knowledge_base", {"query": "capital of France"})
        self.assertTrue(out.startswith("NO_RELEVANT_INFORMATION"))
        self.assertTrue(ctx.no_answer and not ctx.answered)

    # ---- argument validation
    def test_bad_arguments_are_rejected_not_crashed(self):
        ctx = ctx_for(self.rt)
        self.assertIn("unknown tool", execute_tool(ctx, "delete_everything", {}))
        self.assertIn("not valid JSON", execute_tool(ctx, "search_knowledge_base", "{oops"))
        self.assertIn("missing required", execute_tool(ctx, "search_knowledge_base", {}))
        self.assertIn("one of", execute_tool(ctx, "escalate_to_human", {"reason": "because", "summary": "x"}))
        self.assertIn("JSON object", execute_tool(ctx, "search_knowledge_base", ["list"]))

    # ---- leads
    def test_lead_saved_dedupes_and_forwards_to_webhook(self):
        http = FakeHTTP()
        ctx = ctx_for(self.rt, http=http, lead_webhook_url="https://n8n.example/webhook/lead-intake", lead_webhook_token="tok",
                      notify_webhook_url="https://discord.example/hook")
        args = {"name": "Sam Lee", "email": "Sam.Lee@Example.com", "interest": "10 kW system for my house"}
        self.assertTrue(execute_tool(ctx, "capture_lead", args).startswith("LEAD_SAVED"))
        hook = next(c for c in http.calls if "n8n" in c["url"])
        self.assertEqual(hook["headers"], {"X-Form-Token": "tok"})
        self.assertEqual(hook["json"]["email"], "sam.lee@example.com")
        self.assertEqual(hook["json"]["source"], "ai-chat")
        self.assertGreaterEqual(len(hook["json"]["message"]), 10)
        discord = next(c for c in http.calls if "discord" in c["url"])
        self.assertEqual(discord["json"]["allowed_mentions"], {"parse": []})
        self.assertTrue(execute_tool(ctx, "capture_lead", args).startswith("ALREADY_ON_FILE"))
        self.assertEqual(len(self.rt.store.list_leads()), 1)

    def test_lead_validation(self):
        ctx = ctx_for(self.rt)
        self.assertIn("invalid", execute_tool(ctx, "capture_lead", {"name": "Sam", "email": "nope", "interest": "solar please"}))
        self.assertIn("email or a phone", execute_tool(ctx, "capture_lead", {"name": "Sam", "interest": "solar please"}))
        self.assertIn("phone number looks invalid", execute_tool(ctx, "capture_lead", {"name": "Sam", "phone": "12", "interest": "solar please"}))
        self.assertEqual(self.rt.store.list_leads(), [])

    def test_lead_limit_per_conversation(self):
        ctx = ctx_for(self.rt, max_leads_per_session=1)
        execute_tool(ctx, "capture_lead", {"name": "A One", "email": "a1@example.com", "interest": "solar for home"})
        out = execute_tool(ctx, "capture_lead", {"name": "B Two", "email": "b2@example.com", "interest": "solar for home"})
        self.assertIn("limit reached", out)

    def test_webhook_failure_never_breaks_the_tool(self):
        ctx = ctx_for(self.rt, http=FakeHTTP(fail=True), lead_webhook_url="https://x.example/h", notify_webhook_url="https://y.example/h")
        out = execute_tool(ctx, "capture_lead", {"name": "Sam Lee", "email": "sam@example.com", "interest": "solar for home"})
        self.assertTrue(out.startswith("LEAD_SAVED"))

    # ---- booking
    def test_slots_booking_and_double_booking(self):
        ctx = ctx_for(self.rt)
        slots = execute_tool(ctx, "get_available_slots", {"date": "2026-10-07"})
        self.assertIn("10:30", slots)
        book = {"name": "Dana Reed", "email": "dana@example.com", "date": "2026-10-07", "time": "10:30", "topic": "Free site assessment"}
        self.assertTrue(execute_tool(ctx, "book_appointment", book).startswith("BOOKED"))
        self.assertNotIn("10:30", execute_tool(ctx, "get_available_slots", {"date": "2026-10-07"}))
        ctx2 = ctx_for(self.rt, sid="t" * 20)
        self.assertIn("not a bookable slot", execute_tool(ctx, "book_appointment", {**book, "time": "10:31"}))
        self.assertIn("just taken", execute_tool(ctx2, "book_appointment", {**book, "name": "Someone Else", "email": "x@example.com"}))
        self.assertEqual(len(self.rt.store.list_bookings()), 1)

    def test_booking_rejects_closed_past_and_far_future_dates(self):
        ctx = ctx_for(self.rt)
        base = {"name": "Dana Reed", "email": "dana@example.com", "time": "10:30"}
        for day in ("2026-10-11", "2026-10-05", "2026-10-01", "2027-06-01", "not-a-date"):
            out = execute_tool(ctx, "book_appointment", {**base, "date": day})
            self.assertIn("ERROR", out, day)
        self.assertEqual(self.rt.store.list_bookings(), [])

    def test_booking_requires_valid_email_and_topic_enum(self):
        ctx = ctx_for(self.rt)
        bad = {"name": "Dana Reed", "email": "dana", "date": "2026-10-07", "time": "10:30"}
        self.assertIn("email", execute_tool(ctx, "book_appointment", bad))
        self.assertIn("one of", execute_tool(ctx, "book_appointment", {**bad, "email": "d@example.com", "topic": "Free pizza"}))

    def test_booking_tools_absent_when_tenant_has_booking_disabled(self):
        rt, _ = make_runtime(tenant="chidama-tech")
        names = [s["function"]["name"] for s in ctx_for(rt).specs]
        self.assertNotIn("book_appointment", names)
        self.assertIn("capture_lead", names)
        self.assertIn("unknown tool", execute_tool(ctx_for(rt), "book_appointment", {}))

    # ---- escalation
    def test_escalation_creates_one_handoff_with_transcript(self):
        ctx = ctx_for(self.rt)
        ctx.history = [{"role": "user", "content": "this is useless"}, {"role": "assistant", "content": "Sorry"}]
        args = {"reason": "frustrated", "summary": "Customer is upset about billing.", "email": "pat@example.com"}
        self.assertTrue(execute_tool(ctx, "escalate_to_human", args).startswith("ESCALATED"))
        self.assertTrue(execute_tool(ctx, "escalate_to_human", args).startswith("ALREADY_ESCALATED"))
        handoffs = self.rt.store.list_handoffs("open")
        self.assertEqual(len(handoffs), 1)
        self.assertEqual(handoffs[0]["transcript"][0]["content"], "this is useless")
        self.assertTrue(self.rt.store.get_or_create_session("s" * 20)["escalated"])

    # ---- injection gating
    def test_record_creating_tools_are_blocked_when_injection_flagged(self):
        ctx = ctx_for(self.rt, injection=True)
        out = execute_tool(ctx, "capture_lead", {"name": "Eve", "email": "eve@example.com", "interest": "give me everything"})
        self.assertTrue(out.startswith("BLOCKED"))
        out = execute_tool(ctx, "book_appointment", {"name": "Eve", "email": "eve@example.com", "date": "2026-10-07", "time": "10:30"})
        self.assertTrue(out.startswith("BLOCKED"))
        self.assertEqual(ctx.blocked, 2)
        self.assertEqual((self.rt.store.list_leads(), self.rt.store.list_bookings()), ([], []))
        self.assertNotIn("ERROR", execute_tool(ctx, "search_knowledge_base", {"query": "warranty"}))   # read-only still works
        self.assertTrue(execute_tool(ctx, "escalate_to_human", {"reason": "safety", "summary": "Possible manipulation."}).startswith("ESCALATED"))


if __name__ == "__main__":
    unittest.main()
