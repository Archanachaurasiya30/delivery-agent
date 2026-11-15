# Contributing to Delivery Agent

Thanks for your interest! Delivery Agent is an AI delivery manager — it drafts
sprints, runs async standups over Telegram, detects blockers, and assesses
release readiness. Every proposal goes through a human approval gate.

## Quick start

```bash
git clone https://github.com/mahmoudsegni/delivery-agent.git
cd delivery-agent
docker compose up -d          # postgres, redis, backend, worker, beat, bot, frontend
docker compose exec backend python -m app.seed   # demo data (fictional Northwind team)
# frontend: http://localhost:3000
```

No Azure DevOps instance needed for local dev — the seed data and mock provider
cover the UI. Real sync is opt-in via `TFS_URL` / `TFS_PAT` env vars (see
TFS-SYNC.md).

## Stack

- **Backend**: FastAPI, SQLAlchemy, Alembic, Celery (worker + beat), PostgreSQL, Redis
- **Frontend**: React + Vite + TypeScript + Tailwind
- **Bot**: Telegram (aiogram), standup collection + digests

## Making changes

1. Fork, create a feature branch (`feat/...`, `fix/...`).
2. Backend changes: `cd backend && python -m pytest tests -q` — keep the suite green.
3. Frontend changes: `cd frontend && npm ci && npm run build` must pass.
4. Migrations: add a numbered Alembic revision; never edit an applied one.
5. Open a PR with what + why. Screenshots for UI changes.

## Ground rules

- **All sample data stays fictional** (the Northwind Dynamics team). Never commit
  real people, companies, hosts, or work items — PRs adding real-world data will
  be rejected.
- Keep the "agent proposes, human approves" invariant: no autonomous writes to
  the tracker or Telegram without an approval path.
- English everywhere (code, comments, docs).
