# Competitive Landscape — AI Delivery Management (researched 2026-11-13)

Method: live fetches (server-rendered prices only; JS-gated flagged), via Hermes web search + omp GLM scout run.
Evidence: /var/tmp/hunt/html_da/ (fetched pages), /var/tmp/hunt/delivery_scout.jsonl (structured data).

## Confirmed pricing (from fetched HTML)

| Product | Telegram | Azure DevOps | Approval flow | Free tier | Paid |
|---|---|---|---|---|---|
| **Spryn** | ✗ | ✗ | ✓ (edit & lock) | ≤3 users | Cloud $6/user/mo · self-host $99 one-time |
| **TKTIDE** | ✗ | ✓ | ✓ (reviewable writeback) | 2 users, 3 integrations | $9/seat · $15/seat |
| **Eodly** | ✓ | ✗ | ✗ | ≤5 teammates | $29 · $49 · $89/mo |
| **Geekbot** (standups only) | ✗ | ✗ | ✗ | ≤10 users | $2.50/participant/mo |
| **Aimey** | ✗ (social widget false-positive) | ✗ | ✗ | — | $19.99 · $39.99/user/mo |
| **AI Delivery Manager** (aideliverymanager.com) | ✗ | ✓ | ✓ ("human approval before anything is created") | 7-day trial | Pro $49/mo · Enterprise custom — **JS-gated, from bundle** |
| Agent HQ (agent-hq.io) | ✗ | ✗ | ✓ | free to start | not published |
| Agent HQ (nordinit, OSS) | ✓ | ✗ | ✓ | MIT self-host | free |
| Staive / TPM Brain / Easentic / Agilion | ✗ | ✗ | ✗/— | — | JS-gated or not published |

Adjacent tiers (see chat summary 2026-11-13): LinearB $29–59/contributor (50–100 seat min), Jellyfish ~$36k/yr, Swarmia $45–55/dev — enterprise engineering intelligence, no standups/Telegram. Platform-native AI (Azure Boards MCP agent mode, Atlassian Revo, Copilot ADO extension) is the structural threat to individual features.

## The gap (zero products have this intersection)

**Telegram-first async standups + full delivery loop (planning → blockers → release) + human-approval gates + Azure DevOps/on-prem TFS sync.**

- Telegram: only Eodly (no planning/approval, standup-only) and nordinit OSS (different category)
- ADO: only TKTIDE and aidm.com; **on-prem TFS: nobody**
- Full 4-capability loop with approvals: nobody (closest: aidm.com — near-clone pitch, young product)

## Positioning options (decision pending)

A. **Telegram + ADO/TFS wedge** — "the delivery manager for teams outside the Slack bubble" (MENA/LATAM/EA, field teams, TFS enterprises). Least competition, matches built assets.
B. **Head-on AI delivery manager** (Slack+Jira global) — crowded T1, platform-AI pressure; execution-edge only.
C. **Self-host / on-prem privacy angle** (Spryn's $99 model proves appetite) — Telegram bot + docker-compose + BYO-LLM keys for enterprises that can't use SaaS.
