# Supervisor Assessment: Delivery Agent vs. "Can Replace a Project Manager"

*Assessment date: 2026-08-04. Based on a full codebase inventory (backend API/services/
tasks, executive/autopilot/coding layers, integrations, frontend) checked against the
claims in BUSINESS.md.*

## Verdict

**Today this cannot replace a PM — but not for the reason you'd guess.** The engineering
is genuinely strong in places (metrics, the coding-agent loop, the autopilot design). The
blocker is that the *PM-facing loop never closes*: the agent observes and writes reports,
but it cannot listen, its flagship AI features run on fake data, its approvals change
nothing in the real world, and there is no accountable human behind the "human approves"
gate. Meanwhile the most differentiated thing built — an AI workforce that ships real
PRs behind a human merge gate — is underplayed in the business doc.

## What's real vs. claimed (the honest ledger)

| Capability (per BUSINESS.md) | Reality |
|---|---|
| AI sprint planning | **Demo facade.** Runs in the React frontend on hardcoded `DEMO_WORK_ITEMS`/`AGENT_MEMBERS` (`frontend/src/features/agent/agentData.ts`); never reads the real backlog. Backend `/agent/analyze` is a stateless Groq proxy. |
| Automated standups | Backend is real (models, beat schedule, LLM synthesis) but **cannot collect a single answer**: questions go out via Webex, the only inbound handler is the dormant Telegram poller, and the Redis conversation state is keyed by email while the reader looks up by chat_id. Every round closes after 30 min with empty entries. |
| Blocker detection | The "AI" version is demo data. A real (heuristic, non-LLM) stale-task detector + escalation exists in the autopilot — it works, but escalations only land in the DB queue, never pushed to chat. |
| Release assessment | AI narrative is frontend demo data (hardcoded version "2.1.0"). A real heuristic readiness score exists in the dashboard. |
| "Agent proposes, human approves" | Approve/reject flips a DB flag with `reviewed_by="system"`. **Only 2 of 7 proposal types execute anything** (`autopilot_dispatch`, `coding_pr`). Approving a sprint plan creates no sprint, assigns nothing, pushes nothing to ADO. |
| ADO/TFS sync | Pull is real; push only for locally-created tasks (echo guard); **no conflict handling** (local edits to imported tasks are silently lost); scheduled sync disabled; no webhooks. |
| Metrics | **The strongest part of the codebase.** Confidence blend, burndown, velocity, flow metrics (cycle/lead time, CFD, aging WIP), honest about missing data. But no forecasting. |
| Coding agent + autopilot | **Real and well-engineered** (PAT isolation, env allowlist, diff guardrails, revise loop, merge gate). Caveats: CI gate is a no-op (no `AZURE_PIPELINE_ID` → instant "success"), spec grooming degraded to templates (litellm has no Groq branch). Autopilot defaults to `auto`. |
| Security/auth | **Nonexistent.** No login, no roles, no identity. Anyone reaching the API can approve and merge a PR. Live Groq key hardcoded in git-tracked `docker-compose.yml`. |
| Tests / git state | ~1% coverage (one test file). **~137 files of the actual product are uncommitted** working-tree code. |

## The five gaps blocking the "replace a PM" claim

A PM's job is: **decide, communicate two-way, commit to dates, and be accountable.**
The product today can **observe, summarize, and (uniquely) code.** The missing middle:

1. **Decisions don't execute.** A PM's output is changed state in the world — a sprint
   exists in ADO, people are assigned, stakeholders informed. Here approval is a DB flag.
   Until `sprint_planning` approval creates/assigns/pushes the sprint, the approval
   workflow is record-keeping, not management.
2. **The AI runs on fake data.** The flagship demo would collapse the moment a real team
   compares the "proposed sprint" to their actual backlog. The real DB tools already exist
   (`backend/app/agents/tools.py`) — they're just never wired to the four capabilities.
3. **The agent can't listen.** All communication is outbound (brief, standup questions,
   nudges). No Webex webhook route exists, so no standup answers, no "I'm blocked" replies,
   no negotiation. A PM who only broadcasts is a newsletter.
4. **No accountable human gate.** The entire differentiation is "trust-first, human
   approves, audit trail" — but with zero auth there is no *who* in the audit trail. The
   central design bet is currently unenforceable.
5. **No forward-looking answers.** The #1 stakeholder question — "when will it ship?" —
   has no answer anywhere. Velocity mean/sigma is computed but never projected into a
   completion forecast, and stored velocity never feeds back into planning.

Plus the trust substrate: ~1% tests around the exact state machines that must not fail
(proposal, standup, autopilot, coding run), the product uncommitted in git, and a live
API key in a tracked file.

## What you CAN honestly claim today (positioning)

- **Don't sell "replaces the PM" — sell PM leverage.** "One delivery manager runs 3×
  the streams" is provable and doesn't trigger the trust objection. A staged-autonomy
  ladder is the story: L1 visibility (works today) → L2 async coordination (needs inbound
  chat) → L3 decision execution (needs executors) → L4 autonomous delivery (weirdly
  *ahead* here with the coding loop).
- **The wedge answer (BUSINESS.md Q1/Q3): the autopilot→coding-agent→PR→human-merge loop
  is the moat.** Geekbot/Standuply can't copy it; Jira AI doesn't do it; it compounds
  (run history, cost/outcome data already tracked in `workforce` stats). Standups are a
  commodity feature — the AI workforce with a merge gate is not.
- The metrics/confidence layer is credible enough to demo to an exec today.

## Roadmap to close the gap

### P0 — Stop the bleeding (days)
1. **Commit the product.** ~137 files including all of phases 5–13 exist only in the
   working tree. Branch, commit in coherent chunks.
2. **Rotate + remove the Groq key** hardcoded in `docker-compose.yml` (tracked by git);
   move to `.env` like the other secrets.
3. **Fix the standup loop** — decide the transport (recommend: finish Webex inbound since
   convo state is already keyed by email): add a `POST /webhooks/webex` route validating
   `WEBEX_WEBHOOK_SECRET`, feed `personEmail` into `record_answer`, gate
   `members_to_prompt` on linked/reachable members.
4. **Minimal identity on the approval gate:** even a simple API-key/user header (or ADO
   extension identity in the hub build) recorded into `reviewed_by`, replacing the two
   `TODO: Get reviewer from auth context` in `backend/app/api/v1/agent.py`.

### P1 — Make the four capabilities real (1–3 weeks)
5. **Move sprint planning / blockers / release assessment to backend services** running on
   live DB data. The pieces exist: real tools in `app/agents/tools.py`, working
   `groq_client.py`, proposal persistence. Delete the `agentData.ts` demo constants and
   the silent mock fallbacks.
6. **Proposal executors:** approving `sprint_planning` creates the sprint, assigns tasks,
   sets `sprint_id`, pushes to ADO; approving `stale_blocker` escalation sends the Webex
   message to the named unblocker. One executor registry keyed by proposal type.
7. **Wire the real CI gate** (set `AZURE_PIPELINE_ID`, or explicitly surface "no CI
   configured" in the PR proposal instead of silently reporting success).

### P2 — PM-grade capabilities (weeks)
8. **Forecasting:** velocity-based completion projection per sprint/stream ("finishes
   ~Nov 12 ± 4 days"), fed by the mean/sigma already computed; feed `Sprint.velocity`
   back into sprint-planning capacity.
9. **Conflict-safe two-way sync:** compare ADO `System.ChangedDate`/rev before overwrite,
   push local edits to imported tasks, ADO service hooks instead of polling, re-enable
   scheduled sync against the real provider.
10. **Escalations to humans, not just the DB:** push `stale_blocker`/decision-queue items
    to Webex with deep links back to the decision.

### P3 — Hardening (ongoing)
11. Tests for the four state machines (proposal, standup round, autopilot tick, coding
    run) — these are the trust-critical paths.
12. Frontend: auth plumbing (the `apiFetch` injection point is already marked), routing/
    deep-links, error boundary, remove dead deps (axios, react-router-dom), remove
    hardcoded names/versions from `mockData`/AgentPage.

## Verification: the pilot that proves the claim

Run **one real sprint with the real team** and measure:
- Standup round completes with ≥80% response rate collected via chat (P0.3 proves itself).
- Sprint proposal generated from the live backlog, approved by a named human, and the
  sprint + assignments appear in Azure DevOps (P1.5–6).
- At least one blocker escalation reaches the right person in Webex before a human noticed
  it manually.
- Morning brief accuracy spot-checked daily; count corrections.
- "Hours saved" tile backed by the run/outcome data, not an estimate.

If those five hold for one sprint, there's a defensible "PM leverage" pitch and a staged
path to the bigger claim.
