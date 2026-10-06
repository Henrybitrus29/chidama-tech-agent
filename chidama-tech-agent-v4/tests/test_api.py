import importlib.util
import unittest

HAVE_API = bool(importlib.util.find_spec("fastapi") and importlib.util.find_spec("httpx"))

if HAVE_API:
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from app.main import create_app
    from tests.helpers import make_runtime, say

SID = "session-abcdefghijkl"


@unittest.skipUnless(HAVE_API, "fastapi/httpx not installed (CI installs them)")
class ApiTests(unittest.TestCase):
    def client(self, script=(), **overrides):
        rt, _ = make_runtime(list(script) or [say("Hello!")] * 20)
        settings = replace(rt.settings, **overrides)
        return TestClient(create_app(settings, rt), raise_server_exceptions=False), rt

    def test_health_and_public_config(self):
        c, _ = self.client()
        h = c.get("/api/health").json()
        self.assertEqual((h["status"], h["tenant"]), ("ok", "brightside-solar"))
        self.assertTrue(c.get("/api/config").json()["booking_enabled"])

    def test_chat_round_trip(self):
        c, _ = self.client()
        r = c.post("/api/chat", json={"message": "hi", "session_id": SID})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["answer"], "Hello!")
        self.assertEqual(r.headers["x-content-type-options"], "nosniff")

    def test_input_validation(self):
        c, _ = self.client()
        self.assertEqual(c.post("/api/chat", json={"message": "hi", "session_id": "short"}).status_code, 422)
        self.assertEqual(c.post("/api/chat", json={"message": "", "session_id": SID}).status_code, 422)
        self.assertEqual(c.post("/api/chat", json={"message": "x" * 5000, "session_id": SID}).status_code, 422)
        self.assertEqual(c.post("/api/chat", content=b"x" * 20000, headers={"content-type": "application/json"}).status_code, 413)

    def test_rate_limit_returns_429_with_retry_after(self):
        c, _ = self.client(rate_limit_session_per_min=2, rate_limit_ip_per_min=50)
        codes = [c.post("/api/chat", json={"message": "hi", "session_id": SID}).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
        limited = c.post("/api/chat", json={"message": "hi", "session_id": SID})
        self.assertIn("retry-after", limited.headers)

    def test_spoofed_forwarded_for_cannot_dodge_the_ip_limit(self):
        c, _ = self.client(trust_proxy=True, trusted_proxy_hops=1, rate_limit_ip_per_min=2, rate_limit_session_per_min=50)
        codes = []
        for i in range(3):   # new session id and a fresh fake client address each time; the proxy-added entry stays the same
            r = c.post("/api/chat", json={"message": "hi", "session_id": f"session-spoof-{i:08d}"},
                       headers={"X-Forwarded-For": f"10.0.0.{i}, 203.0.113.9"})
            codes.append(r.status_code)
        self.assertEqual(codes, [200, 200, 429])

    def test_forwarded_for_is_ignored_unless_proxy_is_trusted(self):
        c, _ = self.client(trust_proxy=False, rate_limit_ip_per_min=2, rate_limit_session_per_min=50)
        codes = [c.post("/api/chat", json={"message": "hi", "session_id": f"session-ign-{i:09d}"},
                        headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    def test_daily_ip_cap_stops_session_rotation(self):
        c, _ = self.client(rate_limit_ip_per_day=3, rate_limit_ip_per_min=50, rate_limit_session_per_min=50)
        codes = [c.post("/api/chat", json={"message": "hi", "session_id": f"session-day-{i:010d}"}).status_code for i in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])

    def test_global_daily_cap_returns_503_with_retry_after(self):
        c, _ = self.client(daily_turn_cap=2, rate_limit_ip_per_min=50, rate_limit_session_per_min=50, rate_limit_ip_per_day=50)
        codes = [c.post("/api/chat", json={"message": "hi", "session_id": f"session-cap-{i:010d}"}).status_code for i in range(3)]
        self.assertEqual(codes, [200, 200, 503])
        self.assertIn("retry-after", c.post("/api/chat", json={"message": "hi", "session_id": "session-cap-final-00"}).headers)
        self.assertEqual(c.get("/api/health").status_code, 200)   # the cap only gates chat

    def test_errors_do_not_leak_internals(self):
        rt, _ = make_runtime([])
        rt.handle_message = lambda *a, **k: (_ for _ in ()).throw(KeyError("MONGO_URI=mongodb://user:pass@host"))
        c = TestClient(create_app(rt.settings, rt), raise_server_exceptions=False)
        r = c.post("/api/chat", json={"message": "hi", "session_id": SID})
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("mongodb", r.text)

    def test_missing_llm_gives_503(self):
        c, rt = self.client()
        rt.llm = None
        self.assertEqual(c.post("/api/chat", json={"message": "hi", "session_id": SID}).status_code, 503)

    def test_admin_is_disabled_without_token_and_protected_with_one(self):
        c, _ = self.client()
        self.assertEqual(c.get("/api/admin/leads").status_code, 404)
        c, _ = self.client(admin_token="s3cret")
        self.assertEqual(c.get("/api/admin/leads").status_code, 401)
        self.assertEqual(c.get("/api/admin/leads", headers={"X-Admin-Token": "wrong"}).status_code, 401)
        self.assertEqual(c.get("/api/admin/stats", headers={"X-Admin-Token": "s3cret"}).status_code, 200)
        self.assertEqual(c.get("/api/admin/handoffs", headers={"X-Admin-Token": "s3cret"}).json(), {"items": []})
        self.assertEqual(c.post("/api/admin/handoffs/nope/resolve", headers={"X-Admin-Token": "s3cret"}).status_code, 404)

    def test_cors_only_for_listed_origins_and_never_with_credentials(self):
        c, _ = self.client(allowed_origins=("https://demo.example",))
        ok = c.options("/api/chat", headers={"Origin": "https://demo.example", "Access-Control-Request-Method": "POST"})
        self.assertEqual(ok.headers.get("access-control-allow-origin"), "https://demo.example")
        self.assertNotIn("access-control-allow-credentials", ok.headers)
        bad = c.options("/api/chat", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        self.assertNotIn("access-control-allow-origin", bad.headers)

    def test_api_docs_are_off_by_default(self):
        c, _ = self.client()
        self.assertEqual(c.get("/docs").status_code, 404)
        self.assertEqual(c.get("/openapi.json").status_code, 404)


if __name__ == "__main__":
    unittest.main()
