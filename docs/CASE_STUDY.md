# Case study template: grounded support agent

Fill every `[ ]` from a real run. Do not publish a number you did not measure.

## The problem
A small business answers the same customer questions all day, loses leads outside office hours, and cannot trust a generic chatbot not to invent prices or promises.

## The solution
A support agent that answers only from the company's own documents with citations, refuses what it cannot support, books appointments, captures leads into the existing pipeline, and hands off to a person with a summary.

## Design choices worth explaining
- **Code decides, the model suggests.** Tools validate emails, dates and slots, cap actions per conversation, and refuse record-creating actions when a message looks like manipulation.
- **Refusal is a feature.** A coverage gate counts unknown words against the question, so off-topic questions are refused instead of answered from a loosely related passage.
- **Per-visitor memory** with a TTL, and flagged messages are never replayed to the model.
- **Evaluation as a regression test.** The knowledge base has its own question set; CI fails if an edit breaks an answer.

## Results (from my own run on [business / document set])
| Measure | Result |
|---|---|
| Documents / chunks | [ ] / [ ] |
| Evaluation questions (answerable / off-topic / injection / action) | [ ] / [ ] / [ ] / [ ] |
| Answerable questions answered with a correct citation | [ ]% |
| Off-topic or unsupported questions correctly refused | [ ]% |
| Red-team attacks resisted by the live model (46 attacks, 9 categories; `evals/results/redteam.md`) | [ ] of 46 |
| Code-layer attacks blocked with a fully compromised model (offline) | 25 of 25 |
| Normal requests wrongly flagged by the tripwire | 0 of 18 |
| Normal requests still handled correctly during the live run | [ ] of 8 |
| Median / p95 response time (live, free tier) | [ ] s / [ ] s |
| Known failures and why | [ ] |

## Security testing
See `docs/REDTEAM.md`. Two layers are tested separately because they fail differently: code that no prompt can talk out of its rules, and a model that sometimes can be talked into things. The suite found real gaps in the first version of my tripwire (the first patterns flagged 9 of 25 code-layer attacks; after the fix all 25 are flagged and none creates a record), which is why it is in CI.

## What I would do next
Calendar integration, hybrid retrieval evaluated on the client's real questions, a staff dashboard for the handoff queue, and a shared rate limiter for multi-instance deployment.

## Stack
Python, FastAPI, LangGraph, Groq, MongoDB Atlas (optional), n8n (LeadFlow), Render and Vercel free tiers.
