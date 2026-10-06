#!/usr/bin/env python3
"""Check a DEPLOYED backend end to end. Standard library only.

  python scripts/smoke_test.py --api https://your-agent.onrender.com --origin https://your-site.vercel.app
  add --admin-token TOKEN to check staff endpoints, --rate-test to confirm 429s (uses a few Groq calls)
"""
import argparse
import json
import secrets
import sys
import time
import urllib.error
import urllib.request


def call(method, url, body=None, headers=None, raw=None, timeout=90):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--origin", required=True, help="your site's origin, e.g. https://you.vercel.app")
    ap.add_argument("--admin-token", default="")
    ap.add_argument("--rate-test", action="store_true")
    a = ap.parse_args()
    api, results = a.api.rstrip("/"), []

    def check(name, ok, detail=""):
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail and not ok else ""))

    t0 = time.time()
    s, _, b = call("GET", api + "/api/health", timeout=120)   # a sleeping free instance can take ~30-60 s
    health = json.loads(b) if s == 200 else {}
    check("health responds (cold start %.0fs)" % (time.time() - t0), s == 200 and health.get("status") == "ok", f"HTTP {s}")
    check("GROQ_API_KEY is configured", health.get("llm_configured") is True, "set GROQ_API_KEY on the server")
    check("durable store is on (STORE=mongo)", health.get("store") == "mongo", "leads and chats vanish on restart with STORE=memory")

    s, _, b = call("GET", api + "/api/config")
    cfg = json.loads(b) if s == 200 else {}
    check("public config has welcome message and suggestions", bool(cfg.get("welcome_message")) and bool(cfg.get("suggested_questions")))

    pre = {"Origin": a.origin, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    s, h, _ = call("OPTIONS", api + "/api/chat", headers=pre)
    check("CORS allows your site", {k.lower(): v for k, v in h.items()}.get("access-control-allow-origin") == a.origin,
          "add your site URL to ALLOWED_ORIGINS and redeploy")
    s, h, _ = call("OPTIONS", api + "/api/chat", headers={**pre, "Origin": "https://evil.example"})
    check("CORS blocks other origins", "access-control-allow-origin" not in {k.lower() for k in h})

    sid = secrets.token_hex(18)
    q = (cfg.get("suggested_questions") or ["What are your opening hours?"])[0]
    s, _, b = call("POST", api + "/api/chat", {"message": q, "session_id": sid}, headers={"Origin": a.origin})
    chat = json.loads(b) if s == 200 else {}
    check("chat round trip returns an answer", s == 200 and bool(chat.get("answer")), f"HTTP {s}: {b[:120]}")
    print(f"      answer: {str(chat.get('answer', ''))[:110]!r}  sources: {len(chat.get('sources', []))}")
    s, _, b = call("POST", api + "/api/chat", {"message": "What is the capital of France?", "session_id": sid})
    ans = (json.loads(b).get("answer", "") if s == 200 else "").lower()
    check("off-topic question is declined, not answered", s == 200 and "paris" not in ans, f"answer: {ans[:80]}")

    check("bad session id rejected (422)", call("POST", api + "/api/chat", {"message": "hi", "session_id": "short"})[0] == 422)
    check("oversized body rejected (413)", call("POST", api + "/api/chat", raw=b"x" * 20000)[0] == 413)
    check("API docs are not public", call("GET", api + "/docs")[0] == 404)

    s, _, _ = call("GET", api + "/api/admin/stats")
    check("staff endpoints locked without token", s in (401, 404), f"HTTP {s}")
    if a.admin_token:
        s, _, b = call("GET", api + "/api/admin/stats", headers={"X-Admin-Token": a.admin_token})
        check("staff endpoints work with token", s == 200, f"HTTP {s}")
        print("      stats:", b[:200])

    if a.rate_test:
        codes = [call("POST", api + "/api/chat", {"message": "hi", "session_id": sid})[0] for _ in range(13)]
        check("rate limit returns 429", 429 in codes, f"codes: {codes}")

    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
