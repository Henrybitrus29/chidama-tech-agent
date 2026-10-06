# Deploy guide: backend on Render, site on Vercel, data on MongoDB Atlas (all free tiers)

Free tiers change. Check current limits and sign-up requirements before you start. Budget about 45 minutes.

## 0. Repository layout
Put everything in one GitHub repo (replace the old contents). Delete the old `agent.py`, `main.py`, `facts.json`, `leads.csv` and `chidama-frontend/`; `site/` replaces the old React widget.
```
app/  knowledge/  tests/  evals/  scripts/  site/  widget/  Dockerfile  render.yaml  DEPLOY.md
```
If a `.env`, Mongo password or Discord webhook was ever committed, rotate it now.

## 1. Groq key
Create a free key at console.groq.com. Keep it for step 3.

## 2. MongoDB Atlas (durable leads, chats and handoffs)
1. Create a free cluster, then a database user with a strong password.
2. Network Access: allow `0.0.0.0/0`. Render's free plan has no fixed IP, so this is required; the database password is your protection, so keep it strong and unique.
3. Connect > Drivers > copy the connection string and put your password in it. Keep it for step 3.

## 3. Backend on Render
1. New > Blueprint > select your repo. Render reads `render.yaml`.
2. Fill the prompted values: `GROQ_API_KEY`, `MONGO_URI`. Leave `ALLOWED_ORIGINS` as a placeholder for now. `ADMIN_TOKEN` is generated for you; copy it from the Environment tab.
3. Wait for the deploy. Open `https://YOUR-SERVICE.onrender.com/api/health`. It should show `"llm_configured": true` and `"store": "mongo"`.

## 4. Site on Vercel
1. Edit `site/config.js`: set `api` to the Render URL, plus your name, email, Upwork and GitHub links, and the projects and stats you can back up.
2. Vercel > Add New Project > import the repo > **Root Directory: `site`** > Deploy. No build command needed.
3. Copy your site URL, e.g. `https://henry.vercel.app`.

## 5. Allow your site to call the backend
Render > Environment > `ALLOWED_ORIGINS` = your site URL (comma-separate more, e.g. a custom domain; no trailing slash). Save; Render redeploys.

## 6. Prove it works
```bash
python scripts/smoke_test.py --api https://YOUR-SERVICE.onrender.com --origin https://henry.vercel.app --admin-token YOUR_ADMIN_TOKEN
```
Every line should say PASS. The first call can take up to a minute while a sleeping free instance wakes up. Then open the site and chat with the agent. Run the live evaluation once with your own key:
```bash
export GROQ_API_KEY=...; python -m evals.run_eval --tenant chidama-tech --mode e2e --out evals/results/live.json
python -m evals.redteam --mode e2e --md evals/results/redteam.md --out evals/results/redteam.json   # about 60 turns; uses roughly 100 Groq requests, so run it on a quiet day
```

## 7. Keep it awake (optional)
Free Render instances sleep after idle time, and the site already wakes the backend when a visitor lands. For no delay, create a free monitor at cron-job.org hitting `/api/health` every 10 minutes. Check Render's current free-hours limit first.

## 8. Optional integrations
- **LeadFlow:** set `LEAD_WEBHOOK_URL` (your n8n `/webhook/lead-intake`) and `LEAD_WEBHOOK_TOKEN` on Render.
- **Discord alerts:** set `NOTIFY_WEBHOOK_URL`.
- **Handoff queue:** `curl -H "X-Admin-Token: TOKEN" https://YOUR-SERVICE.onrender.com/api/admin/handoffs`. Also `/leads`, `/bookings`, `/stats`.

## 9. Make it your own business
Follow "Use it for another business" in `README.md`, set `TENANT` on Render, and rerun the evaluation. For your own company, rewrite `knowledge/chidama-tech/` from your real facts first.

## Troubleshooting
| Symptom | Cause and fix |
|---|---|
| Chat shows "not configured" | `api` in `site/config.js` is still the placeholder |
| Browser console: blocked by CORS | Site URL missing from `ALLOWED_ORIGINS`, or it has a trailing slash |
| 503 from `/api/chat` | `GROQ_API_KEY` missing, or the global `DAILY_TURN_CAP` was reached (the body says which; the cap resets on a rolling 24 h window) |
| Everyone gets 429 at once | `TRUSTED_PROXY_HOPS` is too low and every visitor shares the proxy's address; raise it by one |
| 422 from `/api/chat` | A client is sending the wrong body. It needs `message` and a 16-64 character `session_id` |
| First reply takes 30+ seconds | Free instance was asleep; see step 7 |
| Leads disappear after a deploy | `STORE` is `memory`; set `STORE=mongo` and `MONGO_URI` |
| `/api/admin/*` returns 404 | `ADMIN_TOKEN` is not set |
| Render deploy fails | Open the deploy log; most often a missing dependency or a bad `MONGO_URI` |
