# Delivery Agent

## What This Is

An AI-powered delivery manager that runs a dev team's daily operations — morning standups, sprint planning, blocker resolution, and release coordination. It lives in a web dashboard where team leads and devs interact with it. The agent reasons about tasks, capacity, and blockers to make intelligent delivery decisions, replacing much of the manual coordination a human delivery engineer or PM does.

## Core Value

The agent makes smart delivery decisions — proposing sprints that respect capacity, catching blockers early, and keeping the team moving without a human constantly chasing updates.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Dashboard UI where the agent lives and users interact with it
- [ ] AI-powered morning standup — asks each dev for status, compiles a team summary
- [ ] Sprint planning — takes backlog items + manually input capacity, proposes sprint contents for human approval
- [ ] Task tracking — view and manage tasks, track progress per developer
- [ ] Blocker detection and routing — identifies stuck work, suggests who can help, escalates
- [ ] Release management — generates changelog from completed work, communicates release readiness
- [ ] Flexible LLM provider support (OpenAI, Anthropic, Azure OpenAI, etc.)
- [ ] Manual data entry for tasks and sprints (mocked integration layer for v1)

### Out of Scope

- Webex integration — deferred to v2, v1 uses dashboard for all communication
- Azure DevOps integration — deferred to v2, v1 uses manual/imported task data
- Historical velocity learning — deferred to v2, v1 uses manually input capacity
- Mobile app — web dashboard first
- Multi-tenant / SaaS — single team deployment for now
- CI/CD pipeline management — agent focuses on delivery coordination, not build pipelines

## Context

- Team uses Azure DevOps for task tracking and Webex for communication today
- Business team proposes features; the agent should lead planning and decide what fits in a sprint
- Agent proposes, human approves — the agent doesn't have unilateral authority
- Team size is 5-15 developers across multiple workstreams
- Capacity is manually input (who's available, how much) — not derived from historical data in v1
- The v1 strategy is to prove the AI reasoning works with mocked integrations, then connect real systems in v2

## Constraints

- **Tech stack**: Python + LangGraph (agent framework) + FastAPI (backend) + React (frontend) + PostgreSQL
- **LLM provider**: Must support multiple providers (OpenAI, Anthropic, Azure OpenAI) — no vendor lock-in
- **Deployment**: On-premises / local infrastructure
- **Interface**: Web dashboard as primary UI
- **Trust boundary**: Agent proposes decisions, human approves — no autonomous actions on production systems

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Mock integrations in v1 | Prove AI reasoning before investing in Webex/Azure DevOps plumbing | — Pending |
| Dashboard-first interface | Gives full control over UX, Webex is just a notification channel later | — Pending |
| Agent proposes, human approves | Building trust incrementally — autonomous decisions can come later | — Pending |
| Flexible LLM provider | Avoid vendor lock-in, allow switching based on cost/quality/policy | — Pending |
| LangGraph as agent framework | User preference — state machine approach fits proposal/approval workflows, supports human-in-the-loop patterns | — Pending |

---
*Last updated: 2026-02-05 after requirements definition*
