# Delivery Agent — Business Overview

*An AI delivery manager that helps software teams plan sprints, run standups,
catch blockers, and ship — while keeping humans in control of every decision.*

## The Problem

Running delivery for a software team is a grind of manual coordination:

- **Sprint planning** eats hours — pulling from the backlog, eyeballing team
  capacity, juggling priorities and dependencies.
- **Daily standups** are synchronous meetings that interrupt deep work, and the
  useful signal (who's blocked, what's at risk) often gets lost.
- **Blockers surface late** — work sits stuck for days before anyone notices.
- **Release readiness** is a manual scramble: what's done, what's blocking us,
  and what do we tell stakeholders?

A team lead / delivery manager spends much of their week chasing updates instead
of removing obstacles. That coordination work is repetitive, pattern-based, and a
strong fit for an AI agent — *if* the team can still trust the output.

## What It Does

Delivery Agent is an AI-powered delivery assistant with four core capabilities:

1. **Sprint planning** — analyzes the backlog and team capacity, then proposes a
   sprint composition that respects capacity, skills, and dependencies.
2. **Daily standups (automated, async)** — DMs each team member on Telegram with
   the three standard questions, collects answers, and synthesizes a team summary
   with blockers and risks.
3. **Blocker detection** — spots work that's stuck (from standup answers and task
   staleness) and suggests who could help unblock it.
4. **Release assessment** — judges release readiness (completion, blockers,
   testing), gives a go / no-go view, and auto-generates a changelog grouped by
   feature / bugfix / improvement.

## The Core Idea: "Agent Proposes, Human Approves"

The agent **never acts autonomously.** Every output is a *proposal* that moves
through a clear approval workflow:

```
draft → pending review → approved → executed
                       ↘ rejected (with reason)
```

A manager reviews each proposal — with the agent's reasoning and a confidence
level attached — and approves, rejects, or modifies it. This is the central
design bet: it makes the AI safe to adopt incrementally, keeps a human
accountable, and produces an audit trail of every decision.

## How It Works (in plain terms)

- A **web dashboard** is the home base: a Kanban board for work items, a backlog
  and capacity view, an "AI Agent" page to trigger the four capabilities, and a
  **Proposals queue** where a manager reviews and approves the agent's output.
- Team members answer standups **in Telegram** — no new app to learn. The bot
  asks the questions, remembers where each person left off, and closes the round
  on a timer so it never waits forever.
- It **syncs with Azure DevOps / TFS** (the team's existing tracker): it pulls
  work items in and pushes changes back, so the team isn't forced to abandon
  their current tooling.
- The AI reasoning runs through a **provider-agnostic layer** (today: Groq's
  `gpt-oss-120b`), so the underlying model can be swapped (OpenAI, Anthropic,
  Azure) without rewrites — no single-vendor lock-in.

## Who It's For

- **Primary:** delivery managers / team leads running 5–15 developers across
  multiple workstreams.
- **Secondary:** product managers who need to propose work and understand
  capacity.
- **Sweet spot today:** teams already on Azure DevOps + chat tools who prefer an
  on-premises / self-hosted deployment over SaaS.

## What's Actually Built (status — honest)

- **Backend: essentially complete.** Tasks, sprints, team, standups, proposals,
  and the four AI capabilities are implemented, with async background processing
  (Celery), scheduled standups, real-time updates (WebSocket), Telegram, and a
  working Azure DevOps/TFS integration. Runs as a Docker Compose stack
  (API, Postgres, Redis, Celery worker + scheduler, Telegram bot, frontend).
- **Frontend: in progress.** The Kanban board, AI Agent page, and Proposals
  queue exist; richer views (burndown, full standup UI, release dashboard) are
  mid-refactor.
- **Integrations:** Azure DevOps/TFS and Telegram are real; a mock provider
  exists for demos. Overall this is a **working prototype**, not yet a hardened
  product.

## Why It's Different

- **Trust-first, not autonomy-first** — the approval workflow + reasoning +
  audit trail is the product, not a footnote.
- **Meets teams where they are** — Telegram for standups, Azure DevOps for
  tracking; it augments existing tools instead of replacing them.
- **No model lock-in** — provider abstraction means the AI layer is swappable.
- **Self-hostable** — appealing to teams with data/compliance constraints that
  rule out SaaS PM tools.

## Open Questions to Think Through Together

*(the point of this doc — where a thinking partner is most useful)*

1. **Who feels this pain enough to pay?** Is the buyer the team lead, the eng
   manager, or the org? What's the wedge — standups, planning, or blockers?
2. **What's the smallest version that's genuinely useful** and provable in one
   sprint with one real team?
3. **Differentiation vs. incumbents** — Jira/Linear AI features, standup bots
   (Geekbot/Standuply), and "AI PM" startups. What do we own that they can't
   easily copy?
4. **Business model** — self-hosted license vs. SaaS vs. open-core? The
   on-prem/no-lock-in stance is a strength for some buyers and a friction for
   go-to-market.
5. **Trust & accuracy** — what happens to adoption when a proposal is wrong?
   How much does confidence scoring + reasoning actually move trust?
6. **Moat over time** — does value compound (learning a team's velocity,
   patterns, history), or does it stay a thin layer over an LLM?
7. **Beachhead** — lean into the Azure DevOps + Telegram + on-prem niche, or
   stay tool-agnostic from the start?
